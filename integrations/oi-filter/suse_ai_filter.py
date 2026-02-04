"""
title: SUSE AI Monitoring Pipeline
author: opencode
date: 2026-02-04
version: 1.2.1
license: Apache 2.0
description: A pipeline for generating chat telemetry data for SUSE AI, aligned with OTel GenAI Semantic Conventions.
"""

from typing import Optional, List, Set, Dict, Any
from pydantic import BaseModel

import urllib.request
import json
import os
import uuid

# Mocking for local development/LSP if needed, but in production these are available
try:
    from utils.pipelines.main import get_last_user_message, get_last_assistant_message
except ImportError:
    def get_last_user_message(messages): return messages[-1]["content"] if messages else ""
    def get_last_assistant_message(messages): return messages[-1]["content"] if messages else ""

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
        self.name = "SUSE AI"
        self.valves = self.Valves(
            **{
                "pipelines": ["*"],
            }
        )
        self.client = None
        self.tracer = None
        self.meter = None
        self.chats = {}
        self.chat_model_provider = {}
        self.metrics = {}
        self.cost_estimation = fetch_json_from_url_stdlib(
            self.valves.pricing_information
        )
        self.local_sdk_name = "suse-ai"
        self.discovered_models: Set[str] = set()

    def get_chat_model_cost(self, model, prompt, completion):
        if not self.cost_estimation or "chat" not in self.cost_estimation:
            return 0
        try:
            model_pricing = self.cost_estimation["chat"].get(model)
            if not model_pricing:
                raise UndefinedPriceError
            
            cost = (
                (prompt / 1000) * model_pricing["promptPrice"]
            ) + (
                (completion / 1000) * model_pricing["completionPrice"]
            )
            return cost
        except KeyError:
            raise UndefinedPriceError
        except Exception:
            return 0

    def capture_messages(self):
        return self.valves.capture_message_content

    def setup(self):
        models_str = ",".join(sorted(list(self.discovered_models))) if self.discovered_models else "none"
        resource_attributes = {
            ResourceAttributes.SERVICE_NAME: self.valves.otlp_service_name,
            ResourceAttributes.SERVICE_VERSION: "1.2.1",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: "default",
            ResourceAttributes.TELEMETRY_SDK_NAME: self.local_sdk_name,
            "gen_ai.app": "true",
            "stackpack": "suse-ai",
            "gen_ai.models": models_str
        }
        
        resource = Resource.create(attributes=resource_attributes)
        self._setup_meter(resource)
        self._setup_tracer(resource)

    def _setup_tracer(self, resource):
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=self.valves.otlp_endpoint + "/v1/traces")
            )
        )
        self.tracer = tracer_provider.get_tracer("suse-ai.otel.tracing")

    def _setup_meter(self, resource):
        metric_exporter = OTLPMetricExporter(
            endpoint=self.valves.otlp_endpoint + "/v1/metrics"
        )

        metric_reader = PeriodicExportingMetricReader(metric_exporter)

        meter_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader]
        )

        self.meter = meter_provider.get_meter(__name__, version="1.2.1")

        self.metrics = {
            "genai_client_usage_tokens": self.meter.create_histogram(
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
            "genai_requests": self.meter.create_counter(
                name="gen_ai.client.requests",
                description="Number of requests to GenAI",
                unit="1",
            ),
            "genai_cost": self.meter.create_histogram(
                name="gen_ai.client.cost",
                description="The distribution of GenAI request costs.",
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
        
        model = body.get("model", "default")
        
        if model not in self.discovered_models:
            self.discovered_models.add(model)
            self.setup()

        parent = self.chats.get(chat_id, None)
        if parent is None and self.tracer:
            parent = self.tracer.start_span(f"chat {model}")
        self.chats[chat_id] = parent
        self.chat_model_provider[(chat_id, model)] = provider

        if self.tracer and parent:
            parent_context = trace.set_span_in_context(parent)
            with self.tracer.start_as_current_span("request", context=parent_context) as span:
                span.set_attribute(SemanticConvention.GEN_AI_OPERATION, "chat")
                span.set_attribute(SemanticConvention.GEN_AI_PROVIDER, provider)
                span.set_attribute(SemanticConvention.GEN_AI_SYSTEM, provider)
                span.set_attribute(SemanticConvention.GEN_AI_REQUEST_MODEL, model)
                span.set_attribute(SemanticConvention.GEN_AI_CONVERSATION_ID, chat_id)
                span.set_attribute("gen_ai.app.name", self.valves.otlp_service_name)
                span.set_attribute("telemetry.sdk.name", self.local_sdk_name)

                if self.capture_messages():
                    message = get_last_user_message(body.get("messages", []))
                    span.set_attribute(SemanticConvention.GEN_AI_USER_MESSAGE, message)
                
                span.set_status(Status(StatusCode.OK))
        return body

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        self.log(f"Outlet function called with body: {body} and user {user}")
        token_counts_available = True
        model = body.get("model") or "undefined"
        chat_id = body.get("chat_id", None)
        
        assistant_message_obj = get_last_assistant_message_obj(body.get("messages", []))
        info = assistant_message_obj.get("usage", {}) if assistant_message_obj else {}
        
        input_tokens = info.get("prompt_eval_count") or info.get("prompt_tokens")
        output_tokens = info.get("eval_count") or info.get("completion_tokens")
        
        if input_tokens is None or output_tokens is None:
            token_counts_available = False
        
        total_tokens = (input_tokens or 0) + (output_tokens or 0) if token_counts_available else 0
        
        if parent := self.chats.get(chat_id, None):
            provider = self.chat_model_provider.get((chat_id, model), "default")
            if self.tracer:
                context = trace.set_span_in_context(parent)
                with self.tracer.start_as_current_span("response", context=context) as span:
                    span.set_attribute(SemanticConvention.GEN_AI_OPERATION, "chat")
                    span.set_attribute(SemanticConvention.GEN_AI_PROVIDER, provider)
                    span.set_attribute(SemanticConvention.GEN_AI_SYSTEM, provider)
                    span.set_attribute(SemanticConvention.GEN_AI_RESPONSE_MODEL, model)
                    
                    if token_counts_available:
                        cost = 0
                        try:
                            cost = self.get_chat_model_cost(model, input_tokens, output_tokens)
                        except UndefinedPriceError:
                            self.log(f"Undefined price for model {model}")
                        
                        span.set_attribute("gen_ai.usage.cost", cost)
                        span.set_attribute(SemanticConvention.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
                        span.set_attribute(SemanticConvention.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)
                        span.set_attribute("gen_ai.usage.total_tokens", total_tokens)
                    
                    span.set_attribute("telemetry.sdk.name", self.local_sdk_name)
                    
                    if self.capture_messages():
                        message = get_last_assistant_message(body.get("messages", []))
                        span.set_attribute(SemanticConvention.GEN_AI_ASSISTANT_MESSAGE, message)
                    
                    span.set_status(Status(StatusCode.OK))
            
            parent.set_status(Status(StatusCode.OK))
            parent.end()
            
            self.chats.pop(chat_id, None)
            for key in [k for k in self.chat_model_provider if k[0] == chat_id]:
                self.chat_model_provider.pop(key, None)
        else:
            self.log("No parent span")
            return body

        metrics_attributes = {
            ResourceAttributes.SERVICE_NAME: self.valves.otlp_service_name,
            SemanticConvention.GEN_AI_OPERATION: "chat",
            SemanticConvention.GEN_AI_PROVIDER: provider,
            SemanticConvention.GEN_AI_REQUEST_MODEL: model,
            SemanticConvention.GEN_AI_RESPONSE_MODEL: model,
            "telemetry.sdk.name": self.local_sdk_name
        }

        if token_counts_available and self.metrics:
            self.metrics["genai_client_usage_tokens"].record(
                input_tokens, {**metrics_attributes, "gen_ai.token.type": "input"}
            )
            self.metrics["genai_client_usage_tokens"].record(
                output_tokens, {**metrics_attributes, "gen_ai.token.type": "output"}
            )
            
            cost = 0
            try:
                cost = self.get_chat_model_cost(model, input_tokens, output_tokens)
            except UndefinedPriceError:
                pass
            self.metrics["genai_cost"].record(cost, metrics_attributes)
            
            duration_s = (info.get("total_duration") or 0) / 1e9
            self.metrics["genai_client_operation_duration"].record(
                duration_s, metrics_attributes
            )
            
        if self.metrics:
            self.metrics["genai_requests"].add(1, metrics_attributes)
        return body

    def log(self, message: str):
        if self.valves.debug_log_enabled:
            print(f"[DEBUG] {message}")


def fetch_json_from_url_stdlib(url):
    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except:
        return None


def get_last_assistant_message_obj(messages: List[dict]) -> dict:
    for message in reversed(messages or []):
        if message.get("role") == "assistant":
            return message
    return {}


class SemanticConvention:
    GEN_AI_OPERATION = "gen_ai.operation.name"
    GEN_AI_PROVIDER = "gen_ai.provider.name"
    GEN_AI_SYSTEM = "gen_ai.system"
    GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
    GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
    GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
    GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
    GEN_AI_USER_MESSAGE = "gen_ai.user.message"
    GEN_AI_ASSISTANT_MESSAGE = "gen_ai.assistant.message"
    
    GEN_AI_CLIENT_TOKEN_USAGE = "gen_ai.client.token.usage"
    GEN_AI_CLIENT_OPERATION_DURATION = "gen_ai.client.operation.duration"


_GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS = [
    0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92
]

_GEN_AI_CLIENT_TOKEN_USAGE_BUCKETS = [
    1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864
]
