"""
title: SUSE AI Monitoring Pipeline
author: Thiago Bertoldi (SUSE)
date: 2026-03-06
version: 1.2.1
license: Apache 2.0
description: A pipeline for generating chat telemetry data for SUSE AI, aligned with OpenTelemetry GenAI semantic conventions
Fixed for Open WebUI 0.6.41+ compatibility with immediate initialization and graceful fallback
"""

from typing import Optional, List
from pydantic import BaseModel

import urllib.request
import json
import os
import uuid
import time
import threading

from utils.pipelines.main import get_last_user_message, get_last_assistant_message

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
)


class UndefinedPriceError(Exception):
    pass


class Pipeline:
    class Valves(BaseModel):
        pipelines: List[str] = []
        priority: int = 0
        otlp_service_name: str = os.getenv("OTEL_SERVICE_NAME", "Open WebUI")
        otlp_endpoint: str = os.getenv(
            "OTEL_EXPORTER_HTTP_OTLP_ENDPOINT",
            "http://opentelemetry-collector.observability.svc.cluster.local:4318",
        )
        capture_message_content: bool = True
        debug_log_enabled: bool = False
        pricing_information: str = os.getenv(
            "PRICING_JSON",
            "https://raw.githubusercontent.com/SUSE/suse-ai-observability-extension/refs/heads/main/integrations/oi-filter/pricing.json",
        )

    def __init__(self):
        self.type = "filter"
        self.name = "SUSE"
        self.valves = self.Valves(
            **{
                "pipelines": ["*"],
            }
        )
        self.client = None
        self.tracer = None
        self.meter = None
        self.chats = {}
        self.chat_timestamps = {}
        self.chat_model_provider = {}
        self.metrics = {}
        self._lock = threading.Lock()
        self.cost_estimation = fetch_json_from_url_stdlib(
            self.valves.pricing_information
        )
        self.local_sdk_name = "suse-ai"

        # Initialize telemetry immediately to handle Open WebUI 0.6.41+ lifecycle
        self.setup()

    def get_chat_model_cost(self, model, prompt, completion):
        try:
            cost = (
                (prompt / 1000) * self.cost_estimation["chat"][model]["promptPrice"]
            ) + (
                (completion / 1000)
                * self.cost_estimation["chat"][model]["completionPrice"]
            )
        except KeyError:
            raise UndefinedPriceError
        except Exception:
            cost = 0
        return cost

    def capture_messages(self):
        return self.valves.capture_message_content

    def setup(self):
        try:
            resource = Resource.create(
                attributes={
                    ResourceAttributes.SERVICE_NAME: self.valves.otlp_service_name,
                    ResourceAttributes.SERVICE_VERSION: "1.0",
                    ResourceAttributes.DEPLOYMENT_ENVIRONMENT: "default",
                    ResourceAttributes.TELEMETRY_SDK_NAME: self.local_sdk_name,
                    "suse.ai.managed": "true",
                    "suse.ai.component.name": "open-webui",
                    "suse.ai.component.type": "ui",
                }
            )
            self._setup_meter(resource)
            self._setup_tracer(resource)
            self.log("Telemetry setup completed successfully")
        except Exception as e:
            print(f"[ERROR] Failed to initialize telemetry: {e}")
            # Set to None to indicate failure
            self.tracer = None
            self.meter = None
            self.metrics = {}

    def _setup_tracer(self, resource):
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=self.valves.otlp_endpoint + "/v1/traces")
            )
        )
        self.tracer = tracer_provider.get_tracer(self.local_sdk_name)

    def _setup_meter(self, resource):
        metric_exporter = OTLPMetricExporter(
            endpoint=self.valves.otlp_endpoint + "/v1/metrics"
        )

        metric_reader = PeriodicExportingMetricReader(metric_exporter)

        meter_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader]
        )

        self.meter = meter_provider.get_meter(self.local_sdk_name)

        self.metrics = {
            # OTel Semconv - Standard Metrics
            "genai_client_token_usage": self.meter.create_histogram(
                name=SemanticConvention.GEN_AI_CLIENT_TOKEN_USAGE,
                description="Measures number of input and output tokens used",
                unit="{token}",
                explicit_bucket_boundaries_advisory=_GEN_AI_CLIENT_TOKEN_USAGE_BUCKETS,
            ),
            "genai_client_operation_duration": self.meter.create_histogram(
                name=SemanticConvention.GEN_AI_CLIENT_OPERATION_DURATION,
                description="GenAI operation duration",
                unit="s",
                explicit_bucket_boundaries_advisory=_GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS,
            ),
            # Custom Metrics - SUSE AI Extensions
            "genai_requests": self.meter.create_counter(
                name="gen_ai.client.request.count",
                description="Number of requests to GenAI providers",
                unit="{request}",
            ),
            "genai_cost": self.meter.create_histogram(
                name="gen_ai.client.operation.cost",
                description="Cost of GenAI operations in USD",
                unit="USD",
            ),
        }

    async def on_startup(self):
        self.log(f"on_startup:{__name__}")
        self.setup()

    async def on_shutdown(self):
        self.log(f"on_shutdown:{__name__}")

    async def on_valves_updated(self):
        self.log(f"on_valves_updated:{__name__}")
        self.setup()

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        self.log(f"Inlet function called with body: {body} and user: {user}")

        if self.tracer is None or self.meter is None:
            self.log("Telemetry not initialized, calling setup()")
            self.setup()

        metadata = body.get("metadata", {})
        task = metadata.get("task", "")

        if task:
            self.log(f"Skipping {task} task.")
            return body

        chat_id = metadata.get("chat_id", "")
        if chat_id == "":
            chat_id = str(uuid.uuid4())
            metadata["chat_id"] = chat_id
            body["metadata"] = metadata

        provider = "unknown"
        try:
            provider = body["metadata"]["model"]["owned_by"]
        except:
            pass
        if provider == "openai":
            try:
                provider = body["metadata"]["model"]["openai"]["owned_by"]
            except:
                pass

        model = body.get("model", "default")

        if self.tracer is None:
            self.log("Tracer not available, skipping telemetry in inlet")
            return body

        self.chat_model_provider[(chat_id, model)] = provider

        start_time = time.time()

        span_name = f"chat {model}"
        span = self.tracer.start_span(span_name)
        span.set_attribute(SemanticConvention.GEN_AI_OPERATION, "chat")
        span.set_attribute(SemanticConvention.GEN_AI_PROVIDER_NAME, provider)
        span.set_attribute(SemanticConvention.GEN_AI_CONVERSATION_ID, chat_id)
        span.set_attribute(SemanticConvention.GEN_AI_REQUEST_MODEL, model)
        span.set_attribute(SemanticConvention.GEN_AI_REQUEST_IS_STREAM, body.get("stream", False))

        if self.capture_messages():
            messages = body.get("messages", [])
            formatted_messages = [format_message_for_otel(msg) for msg in messages]
            span.set_attribute(
                SemanticConvention.GEN_AI_INPUT_MESSAGES,
                json.dumps(formatted_messages)
            )

        with self._lock:
            self.chats[chat_id] = span
            self.chat_timestamps[chat_id] = start_time

        return body

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        self.log(f"Outlet function called with body: {body} and user {user}")

        if self.tracer is None or self.meter is None:
            self.log("Telemetry not initialized in outlet, calling setup()")
            self.setup()

        model = body.get("model") or "undefined"
        chat_id = body.get("chat_id", None)
        assistant_message_obj = get_last_assistant_message_obj(body["messages"])
        info = assistant_message_obj.get("usage", {})
        input_tokens = info.get("prompt_eval_count") or info.get("prompt_tokens")
        output_tokens = info.get("eval_count") or info.get("completion_tokens")
        
        token_counts_available = input_tokens is not None and output_tokens is not None

        if self.tracer is None or self.meter is None:
            self.log("Tracer/Meter not available, skipping telemetry in outlet")
            return body

        span = None
        start_time = None
        
        with self._lock:
            span = self.chats.pop(chat_id, None)
            start_time = self.chat_timestamps.pop(chat_id, None)

        if span:
            provider = self.chat_model_provider.get((chat_id, model), "default")
            
            span.set_attribute(SemanticConvention.GEN_AI_RESPONSE_MODEL, model)

            response_id = assistant_message_obj.get("id") or body.get("id") or ""
            if response_id:
                span.set_attribute(SemanticConvention.GEN_AI_RESPONSE_ID, response_id)

            finish_reason = assistant_message_obj.get("finish_reason") or "stop"
            span.set_attribute(
                SemanticConvention.GEN_AI_RESPONSE_FINISH_REASON,
                format_finish_reason(finish_reason)
            )

            if token_counts_available:
                span.set_attribute(SemanticConvention.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
                span.set_attribute(SemanticConvention.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)

                cost = 0
                try:
                    cost = self.get_chat_model_cost(model, input_tokens, output_tokens)
                except UndefinedPriceError:
                    self.log(f"Undefined price for model {model}")
                if cost > 0:
                    span.set_attribute("gen_ai.usage.cost", cost)

            if self.capture_messages():
                formatted_output = format_message_for_otel(assistant_message_obj)
                formatted_output["finish_reason"] = finish_reason
                span.set_attribute(
                    SemanticConvention.GEN_AI_OUTPUT_MESSAGES,
                    json.dumps([formatted_output])
                )

            span.set_status(Status(StatusCode.OK))
            span.end()
            
            with self._lock:
                for key in [k for k in self.chat_model_provider if k[0] == chat_id]:
                    self.chat_model_provider.pop(key, None)
        else:
            self.log("No span found for chat_id")
            return body

        base_attrs = create_metrics_attributes(
            operation=SemanticConvention.GEN_AI_OPERATION_TYPE_CHAT,
            provider=provider,
            request_model=model,
            response_model=model,
        )

        if token_counts_available:
            input_attrs = create_metrics_attributes(
                operation=SemanticConvention.GEN_AI_OPERATION_TYPE_CHAT,
                provider=provider,
                request_model=model,
                response_model=model,
                token_type="input",
            )
            self.metrics["genai_client_token_usage"].record(input_tokens, input_attrs)

            output_attrs = create_metrics_attributes(
                operation=SemanticConvention.GEN_AI_OPERATION_TYPE_CHAT,
                provider=provider,
                request_model=model,
                response_model=model,
                token_type="output",
            )
            self.metrics["genai_client_token_usage"].record(output_tokens, output_attrs)

            cost = 0
            try:
                cost = self.get_chat_model_cost(model, input_tokens, output_tokens)
                self.log(f"Calculated cost {cost} for model {model}")
            except UndefinedPriceError:
                self.log(f"Undefined price for model '{model}' - not in pricing.json")
            except Exception as e:
                self.log(f"Error calculating cost for model '{model}': {e}")
            if cost > 0:
                self.metrics["genai_cost"].record(cost, base_attrs)
            else:
                self.log(f"Cost is 0 or negative ({cost}) for model '{model}', not recording")

        duration_seconds = None
        duration_ns = assistant_message_obj.get("total_duration", 0)
        if duration_ns and duration_ns > 0:
            duration_seconds = duration_ns / 1_000_000_000.0
        elif start_time is not None:
            end_time = time.time()
            duration_seconds = end_time - start_time
            self.log(f"Calculated duration from timestamps: {duration_seconds}s")

        if duration_seconds is not None and duration_seconds > 0:
            self.metrics["genai_client_operation_duration"].record(duration_seconds, base_attrs)

        self.metrics["genai_requests"].add(1, base_attrs)
        return body

    def log(self, message: str):
        if self.valves.debug_log_enabled:
            print(f"[DEBUG] {message}")


def fetch_json_from_url_stdlib(url):
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                return None
            response_bytes = response.read()
            response_string = response_bytes.decode("utf-8")
            data_dict = json.loads(response_string)
            return data_dict

    except:
        return None


def get_last_assistant_message_obj(messages: List[dict]) -> dict:
    """Retrieve the last assistant message from the message list."""
    for message in reversed(messages):
        if message["role"] == "assistant":
            return message
    return {}


def format_message_for_otel(message: dict) -> dict:
    """
    Format a single message according to OTel GenAI input/output message schema.
    
    Args:
        message: A message dict with 'role' and 'content' keys
        
    Returns:
        dict with 'role' and 'parts' keys following OTel spec
    """
    role = message.get("role", "user")
    content = message.get("content", "")
    
    formatted = {
        "role": role,
        "parts": [
            {
                "type": "text",
                "content": content
            }
        ]
    }
    
    if "tool_calls" in message and message["tool_calls"]:
        formatted["parts"] = []
        for tc in message["tool_calls"]:
            tc_part = {
                "type": "tool_call",
                "id": tc.get("id", ""),
                "name": tc.get("function", {}).get("name", ""),
                "arguments": tc.get("function", {}).get("arguments", {})
            }
            formatted["parts"].append(tc_part)
    
    if role == "tool":
        tool_call_id = message.get("tool_call_id", "")
        formatted["parts"] = [
            {
                "type": "tool_call_response",
                "id": tool_call_id,
                "result": content
            }
        ]
    
    return formatted


def format_finish_reason(reason: str) -> list:
    """Format finish reason as a list per OTel spec."""
    return [reason] if reason else ["stop"]


def create_metrics_attributes(
    operation: str,
    provider: str,
    request_model: str,
    response_model: str,
    token_type: str = None,
):
    """
    Returns OTel metrics attributes following GenAI semantic conventions.

    Args:
        operation: GenAI operation name (e.g., "chat")
        provider: GenAI provider name (e.g., "openai", "ollama", "vllm")
        request_model: Model name requested
        response_model: Model name that responded
        token_type: Token type for token.usage metric ("input" or "output")
    """
    attrs = {
        SemanticConvention.GEN_AI_OPERATION: operation,
        SemanticConvention.GEN_AI_PROVIDER_NAME: provider,
        SemanticConvention.GEN_AI_REQUEST_MODEL: request_model,
        SemanticConvention.GEN_AI_RESPONSE_MODEL: response_model,
        # Add component name as metric attribute so it appears as Prometheus label
        "suse.ai.component.name": "open-webui",
    }

    # Add token type for token usage metrics
    if token_type:
        attrs[SemanticConvention.GEN_AI_TOKEN_TYPE] = token_type

    return attrs


# Credits to OpenLIT SDK
class SemanticConvention:
    """
    The SemanticConvention class provides a centralized repository of constant values that
    represent the keys for various semantic conventions within AI applications. These
    conventions cover a broad range of areas including general AI configurations, request
    parameters, usage metrics, response attributes, and integrations with external AI and
    database systems. It is designed to facilitate consistency and understandability across
    the application's data logging and processing functionalities.
    """

    # General Attributes (OTel Semconv)
    SERVER_PORT = "server.port"
    SERVER_ADDRESS = "server.address"
    ERROR_TYPE = "error.type"

    # GenAI Metric Names (OTel Semconv)
    GEN_AI_CLIENT_TOKEN_USAGE = "gen_ai.client.token.usage"
    GEN_AI_CLIENT_OPERATION_DURATION = "gen_ai.client.operation.duration"
    GEN_AI_SERVER_REQUEST_DURATION = "gen_ai.server.request.duration"
    GEN_AI_SERVER_TBT = "gen_ai.server.time_per_output_token"
    GEN_AI_SERVER_TTFT = "gen_ai.server.time_to_first_token"

    # GenAI Event Names (OTel Semconv)
    GEN_AI_USER_MESSAGE = "gen_ai.user.message"
    GEN_AI_SYSTEM_MESSAGE = "gen_ai.system.message"
    GEN_AI_ASSISTANT_MESSAGE = "gen_ai.assistant.message"
    GEN_AI_TOOL_MESSAGE = "gen_ai.tools.message"
    GEN_AI_CHOICE = "gen_ai.choice"

    # GenAI Request Attributes (OTel Semconv)
    GEN_AI_OPERATION = "gen_ai.operation.name"
    GEN_AI_SYSTEM = "gen_ai.provider.name"  # Deprecated: use GEN_AI_PROVIDER_NAME
    GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
    GEN_AI_OUTPUT_TYPE = "gen_ai.output.type"
    GEN_AI_ENDPOINT = "gen_ai.endpoint"
    GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
    GEN_AI_REQUEST_SEED = "gen_ai.request.seed"
    GEN_AI_REQUEST_ENCODING_FORMATS = "gen_ai.request.encoding_formats"
    GEN_AI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
    GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    GEN_AI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
    GEN_AI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
    GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    GEN_AI_REQUEST_TOP_K = "gen_ai.request.top_k"
    GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
    GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"

    # GenAI Response Attributes (OTel Semconv)
    GEN_AI_TOKEN_TYPE = "gen_ai.token.type"
    GEN_AI_RESPONSE_FINISH_REASON = "gen_ai.response.finish_reasons"
    GEN_AI_RESPONSE_ID = "gen_ai.response.id"
    GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
    GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
    GEN_AI_USAGE_REASONING_TOKENS = "gen_ai.usage.reasoning_tokens"
    GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
    GEN_AI_TOOL_NAME = "gen_ai.tool.name"
    GEN_AI_TOOL_ARGS = "gen_ai.tool.args"

    # GenAI Operation Types (OTel Semconv)
    GEN_AI_OPERATION_TYPE_CHAT = "chat"
    GEN_AI_OPERATION_TYPE_TOOLS = "execute_tool"
    GEN_AI_OPERATION_TYPE_EMBEDDING = "embeddings"
    GEN_AI_OPERATION_TYPE_IMAGE = "image"
    GEN_AI_OPERATION_TYPE_AUDIO = "audio"
    GEN_AI_OPERATION_TYPE_VECTORDB = "vectordb"
    GEN_AI_OPERATION_TYPE_FRAMEWORK = "framework"
    GEN_AI_OPERATION_TYPE_AGENT = "agent"
    GEN_AI_OPERATION_TYPE_CREATE_AGENT = "create_agent"
    GEN_AI_OPERATION_TYPE_EXECUTE_AGENT_TASK = "execute_task"

    # GenAI Output Types (OTel Semconv)
    GEN_AI_OUTPUT_TYPE_IMAGE = "image"
    GEN_AI_OUTPUT_TYPE_JSON = "json"
    GEN_AI_OUTPUT_TYPE_SPEECH = "speech"
    GEN_AI_OUTPUT_TYPE_TEXT = "text"

    # GenAI System Names (OTel Semconv)
    GEN_AI_SYSTEM_ANTHROPIC = "anthropic"
    GEN_AI_SYSTEM_AWS_BEDROCK = "aws.bedrock"
    GEN_AI_SYSTEM_AZURE_AI_INFERENCE = "az.ai.inference"
    GEN_AI_SYSTEM_AZURE_OPENAI = "az.ai.openai"
    GEN_AI_SYSTEM_COHERE = "cohere"
    GEN_AI_SYSTEM_DEEPSEEK = "deepseek"
    GEN_AI_SYSTEM_GEMINI = "gemini"
    GEN_AI_SYSTEM_GROQ = "groq"
    GEN_AI_SYSTEM_IBM_WATSON = "ibm.watson.ai"
    GEN_AI_SYSTEM_MISTRAL = "mistral_ai"
    GEN_AI_SYSTEM_OPENAI = "openai"
    GEN_AI_SYSTEM_PERPLEXITY = "perplexity"
    GEN_AI_SYSTEM_VERTEXAI = "vertex_ai"
    GEN_AI_SYSTEM_XAI = "xai"

    # GenAI OpenAI Attributes (OTel Semconv)
    GEN_AI_REQUEST_SERVICE_TIER = "gen_ai.request.service_tier"
    GEN_AI_RESPONSE_SERVICE_TIER = "gen_ai.response.service_tier"
    GEN_AI_RESPONSE_SYSTEM_FINGERPRINT = "gen_ai.response.system_fingerprint"

    # GenAI System Names (Extra)
    GEN_AI_SYSTEM_HUGGING_FACE = "huggingface"
    GEN_AI_SYSTEM_OLLAMA = "ollama"
    GEN_AI_SYSTEM_GPT4ALL = "gpt4all"
    GEN_AI_SYSTEM_ELEVENLABS = "elevenlabs"
    GEN_AI_SYSTEM_VLLM = "vLLM"
    GEN_AI_SYSTEM_GOOGLE_AI_STUDIO = "google.ai.studio"
    GEN_AI_SYSTEM_REKAAI = "rekaai"
    GEN_AI_SYSTEM_PREMAI = "premai"
    GEN_AI_SYSTEM_LANGCHAIN = "langchain"
    GEN_AI_SYSTEM_LLAMAINDEX = "llama_index"
    GEN_AI_SYSTEM_HAYSTACK = "haystack"
    GEN_AI_SYSTEM_EMBEDCHAIN = "embedchain"
    GEN_AI_SYSTEM_MEM0 = "mem0"
    GEN_AI_SYSTEM_LITELLM = "litellm"
    GEN_AI_SYSTEM_CREWAI = "crewai"
    GEN_AI_SYSTEM_AG2 = "ag2"
    GEN_AI_SYSTEM_MULTION = "multion"
    GEN_AI_SYSTEM_DYNAMIQ = "dynamiq"
    GEN_AI_SYSTEM_PHIDATA = "phidata"
    GEN_AI_SYSTEM_JULEP = "julep"
    GEN_AI_SYSTEM_AI21 = "ai21"
    GEN_AI_SYSTEM_CONTROLFLOW = "controlflow"
    GEN_AI_SYSTEM_ASSEMBLYAI = "assemblyai"
    GEN_AI_SYSTEM_CRAWL4AI = "crawl4ai"
    GEN_AI_SYSTEM_FIRECRAWL = "firecrawl"
    GEN_AI_SYSTEM_LETTA = "letta"
    GEN_AI_SYSTEM_TOGETHER = "together"
    GEN_AI_SYSTEM_PYDANTIC_AI = "pydantic_ai"

    # GenAI Request Attributes (Extra)
    GEN_AI_REQUEST_IS_STREAM = "gen_ai.request.is_stream"
    GEN_AI_REQUEST_USER = "gen_ai.request.user"
    GEN_AI_REQUEST_EMBEDDING_DIMENSION = "gen_ai.request.embedding_dimension"
    GEN_AI_REQUEST_TOOL_CHOICE = "gen_ai.request.tool_choice"
    GEN_AI_REQUEST_AUDIO_VOICE = "gen_ai.request.audio_voice"
    GEN_AI_REQUEST_AUDIO_RESPONSE_FORMAT = "gen_ai.request.audio_response_format"
    GEN_AI_REQUEST_AUDIO_SPEED = "gen_ai.request.audio_speed"
    GEN_AI_REQUEST_AUDIO_SETTINGS = "gen_ai.request.audio_settings"
    GEN_AI_REQUEST_AUDIO_DURATION = "gen_ai.request.audio_duration"
    GEN_AI_REQUEST_IMAGE_SIZE = "gen_ai.request.image_size"
    GEN_AI_REQUEST_IMAGE_QUALITY = "gen_ai.request.image_quality"
    GEN_AI_REQUEST_IMAGE_STYLE = "gen_ai.request.image_style"
    GEN_AI_HUB_OWNER = "gen_ai.hub.owner"
    GEN_AI_HUB_REPO = "gen_ai.hub.repo"
    GEN_AI_RETRIEVAL_SOURCE = "gen_ai.retrieval.source"
    GEN_AI_REQUESTS = "gen_ai.total.requests"
    GEN_AI_DATA_SOURCES = "gen_ai.data_source_count"
    GEN_AI_ENVIRONMENT = "gen_ai.environment"
    GEN_AI_APPLICATION_NAME = "gen_ai.application_name"
    GEN_AI_SDK_VERSION = "gen_ai.sdk.version"

    # GenAI Response Attributes (Extra)
    GEN_AI_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"
    GEN_AI_USAGE_COST = "gen_ai.usage.cost"
    GEN_AI_RESPONSE_IMAGE = "gen_ai.response.image"
    GEN_AI_TOOL_CALLS = "gen_ai.response.tool_calls"

    # GenAI Input/Output Messages (Opt-In per OTel spec)
    GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
    GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"

    # GenAI Content
    CONTENT = "content"
    GEN_AI_CONTENT_PROMPT_EVENT = "gen_ai.content.prompt"
    GEN_AI_CONTENT_PROMPT = "gen_ai.prompt"
    GEN_AI_CONTENT_COMPLETION_EVENT = "gen_ai.content.completion"
    GEN_AI_CONTENT_COMPLETION = "gen_ai.completion"
    GEN_AI_CONTENT_REVISED_PROMPT = "gen_ai.content.revised_prompt"

    # GenAI Rag
    GEN_AI_RAG_MAX_SEGMENTS = "gen_ai.rag.max_segments"
    GEN_AI_RAG_STRATEGY = "gen_ai.rag.strategy"
    GEN_AI_RAG_SIMILARITY_THRESHOLD = "gen_ai.rag.similarity_threshold"
    GEN_AI_RAG_MAX_NEIGHBORS = "gen_ai.rag.max_neighbors"
    GEN_AI_RAG_DOCUMENTS_PATH = "gen_ai.rag.documents_path"
    GEN_AI_RAG_FILE_IDS = "gen_ai.rag.file_ids"

    # GenAI Evaluation Metrics
    GEN_AI_EVAL_CONTEXT_RELEVANCY = "gen_ai.eval.context_relevancy"
    GEN_AI_EVAL_ANSWER_RELEVANCY = "gen_ai.eval.answer_relevancy"
    GEN_AI_EVAL_GROUNDEDNESS = "gen_ai.eval.groundedness"

    # VectorDB Metrics (OTel Semconv)
    DB_CLIENT_OPERATION_DURATION = "db.client.operation.duration"

    # Vector DB Attributes (OTel Semconv)
    DB_SYSTEM_NAME = "db.system.name"
    DB_COLLECTION_NAME = "db.collection.name"
    DB_NAMESPACE = "db.namespace"
    DB_OPERATION_NAME = "db.operation.name"
    DB_QUERY_TEXT = "db.query.text"
    DB_RESPONSE_RETURNED_ROWS = "db.response.returned_rows"

    # Vector DB Attributes (Extras)
    DB_SDK_VERSION = "db.sdk.version"
    DB_OPERATION_API_ENDPOINT = "db.operation.api_endpoint"
    DB_REQUESTS = "db.total.requests"
    DB_OPERATION_ID = "db.operation.id"
    DB_OPERATION_STATUS = "db.operation.status"
    DB_OPERATION_COST = "db.operation.cost"
    DB_OPERATION_CREATE_INDEX = "create_index"
    DB_OPERATION_GET_COLLECTION = "get_collection"
    DB_OPERATION_CREATE_COLLECTION = "create_collection"
    DB_OPERATION_UPDATE_COLLECTION = "update_collection"
    DB_OPERATION_DELETE_COLLECTION = "delete_collection"
    DB_OPERATION_INSERT = "INSERT"
    DB_OPERATION_SELECT = "SELECT"
    DB_OPERATION_QUERY = "QUERY"
    DB_OPERATION_REPLACE = "findAndModify"
    DB_OPERATION_FIND_AND_DELETE = "findAndDelete"
    DB_OPERATION_DELETE = "DELETE"
    DB_OPERATION_UPDATE = "UPDATE"
    DB_OPERATION_UPSERT = "UPSERT"
    DB_OPERATION_GET = "GET"
    DB_OPERATION_ADD = "ADD"
    DB_OPERATION_PEEK = "peePEEKk"
    DB_ID_COUNT = "db.ids_count"
    DB_VECTOR_COUNT = "db.vector_count"
    DB_METADATA = "db.metadata"
    DB_METADATA_COUNT = "db.metadatas_count"
    DB_DOCUMENTS_COUNT = "db.documents_count"
    DB_PAYLOAD_COUNT = "db.payload_count"
    DB_QUERY_LIMIT = "db.limit"
    DB_OFFSET = "db.offset"
    DB_WHERE_DOCUMENT = "db.where_document"
    DB_FILTER = "db.filter"
    DB_STATEMENT = "db.statement"
    DB_N_RESULTS = "db.n_results"
    DB_DELETE_ALL = "db.delete_all"
    DB_INDEX_NAME = "db.index.name"
    DB_INDEX_DIMENSION = "db.index.dimension"
    DB_COLLECTION_DIMENSION = "db.collection.dimension"
    DB_INDEX_METRIC = "db.create_index.metric"
    DB_INDEX_SPEC = "db.create_index.spec"
    DB_NAMESPACE = "db.query.namespace"
    DB_UPDATE_METADATA = "db.update.metadata"
    DB_UPDATE_VALUES = "db.update.values"
    DB_UPDATE_ID = "db.update.id"
    DB_DELETE_ID = "db.delete.id"

    DB_SYSTEM_CHROMA = "chroma"
    DB_SYSTEM_PINECONE = "pinecone"
    DB_SYSTEM_QDRANT = "qdrant"
    DB_SYSTEM_MILVUS = "milvus"
    DB_SYSTEM_ASTRA = "astra"

    # GenAI Request Attributes (OTel Semconv)
    GEN_AI_AGENT_ID = "gen_ai.agent.id"
    GEN_AI_AGENT_NAME = "gen_ai.agent.name"
    GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"

    GEN_AI_AGENT_TYPE = "gen_ai.agent.type"
    GEN_AI_AGENT_TASK_ID = "gen_ai.agent.task.id"
    GEN_AI_AGENT_ROLE = "gen_ai.agent.role"
    GEN_AI_AGENT_GOAL = "gen_ai.agent.goal"
    GEN_AI_AGENT_CONTEXT = "gen_ai.agent.context"
    GEN_AI_AGENT_ENABLE_CACHE = "gen_ai.agent.enable_cache"
    GEN_AI_AGENT_ENABLE_HISTORY = "gen_ai.agent.enable_history"
    GEN_AI_AGENT_ALLOW_DELEGATION = "gen_ai.agent.allow_delegation"
    GEN_AI_AGENT_ALLOW_CODE_EXECUTION = "gen_ai.agent.allow_code_execution"
    GEN_AI_AGENT_MAX_RETRY_LIMIT = "gen_ai.agent.max_retry_limit"
    GEN_AI_AGENT_TOOLS = "gen_ai.agent.tools"
    GEN_AI_AGENT_TOOL_RESULTS = "gen_ai.agent.tool_results"
    GEN_AI_AGENT_TASK = "gen_ai.agent.task"
    GEN_AI_AGENT_PARAMS = "gen_ai.agent.params"
    GEN_AI_AGENT_INSTRUCTIONS = "gen_ai.agent.instructions"
    GEN_AI_AGENT_STORAGE = "gen_ai.agent.storage"
    GEN_AI_AGENT_EXPECTED_OUTPUT = "gen_ai.agent.expected_output"
    GEN_AI_AGENT_ACTUAL_OUTPUT = "gen_ai.agent.actual_output"
    GEN_AI_AGENT_HUMAN_INPUT = "gen_ai.agent.human_input"
    GEN_AI_AGENT_SCHEMA = "gen_ai.agent.schema"
    GEN_AI_AGENT_TASK_ASSOCIATION = "gen_ai.agent.task_associations"
    GEN_AI_AGENT_BROWSE_URL = "gen_ai.agent.browse_url"
    GEN_AI_AGENT_STEP_COUNT = "gen_ai.agent.step_count"
    GEN_AI_AGENT_RESPONSE_TIME = "gen_ai.agent.response_time"
    GEN_AI_AGENT_STRATEGY = "gen_ai.agent.strategy"

    GEN_AI_AGENT_TYPE_BROWSER = "browser"

    # GPU
    GPU_INDEX = "gpu.index"
    GPU_UUID = "gpu.uuid"
    GPU_NAME = "gpu.name"

    GPU_UTILIZATION = "gpu.utilization"
    GPU_UTILIZATION_ENC = "gpu.enc.utilization"
    GPU_UTILIZATION_DEC = "gpu.dec.utilization"
    GPU_TEMPERATURE = "gpu.temperature"
    GPU_FAN_SPEED = "gpu.fan_speed"
    GPU_MEMORY_AVAILABLE = "gpu.memory.available"
    GPU_MEMORY_TOTAL = "gpu.memory.total"
    GPU_MEMORY_USED = "gpu.memory.used"
    GPU_MEMORY_FREE = "gpu.memory.free"
    GPU_POWER_DRAW = "gpu.power.draw"
    GPU_POWER_LIMIT = "gpu.power.limit"

    # Guard
    GUARD_REQUESTS = "guard.requests"
    GUARD_VERDICT = "guard.verdict"
    GUARD_SCORE = "guard.score"
    GUARD_CLASSIFICATION = "guard.classification"
    GUARD_VALIDATOR = "guard.validator"
    GUARD_EXPLANATION = "guard.explanation"

    # Evals
    EVAL_REQUESTS = "evals.requests"
    EVAL_VERDICT = "evals.verdict"
    EVAL_SCORE = "evals.score"
    EVAL_CLASSIFICATION = "evals.classification"
    EVAL_VALIDATOR = "evals.validator"
    EVAL_EXPLANATION = "evals.explanation"


_GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS = [
    0.01,
    0.02,
    0.04,
    0.08,
    0.16,
    0.32,
    0.64,
    1.28,
    2.56,
    5.12,
    10.24,
    20.48,
    40.96,
    81.92,
]

_GEN_AI_SERVER_TBT = [
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.15,
    0.2,
    0.3,
    0.4,
    0.5,
    0.75,
    1.0,
    2.5,
]

_GEN_AI_SERVER_TFTT = [
    0.001,
    0.005,
    0.01,
    0.02,
    0.04,
    0.06,
    0.08,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
]

_GEN_AI_CLIENT_TOKEN_USAGE_BUCKETS = [
    1,
    4,
    16,
    64,
    256,
    1024,
    4096,
    16384,
    65536,
    262144,
    1048576,
    4194304,
    16777216,
    67108864,
]
