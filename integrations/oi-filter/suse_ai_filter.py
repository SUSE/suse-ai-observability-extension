"""
title: SUSE AI Monitoring Pipeline
author: Thiago Bertoldi (SUSE)
date: 2025-05-30
version: 1.0
license: Apache 2.0
description: A pipeline for monitoring Open WebUI inside SUSE AI
requirements:  opentelemetry-distro[otlp]==0.54b1
"""

from typing import Optional, List
from pydantic import BaseModel

import json
import uuid
import os

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import context
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
# from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.propagate import inject, extract


class Pipeline:
    class Valves(BaseModel):
        pipelines: List[str] = []
        priority: int = 0
        otlp_service_name: str = "OI Filter"
        otlp_endpoint: str = "http://opentelemetry-collector.observability.svc.cluster.local:4318/v1/traces"
        pass

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
        self.chat_traces = {}
        pass

    def setup_client(self):
        self.log("Setting up client")

        # Configure tracer provider
        resource = Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: self.valves.otlp_service_name,
                ResourceAttributes.SERVICE_VERSION: "1.0",
                "telemetry.sdk.name": "openlit",
                "deployment.environment": "default"
            }
        )
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=self.valves.otlp_endpoint
                )
            )
        )
        self.tracer = tracer_provider.get_tracer("openlit.otel.tracing")

    async def on_startup(self):
        self.log(f"on_startup:{__name__}")
        self.setup_client()

    async def on_shutdown(self):
        self.log(f"on_shutdown:{__name__}")

    async def on_valves_updated(self):
        self.log(f"on_valves_updated:{__name__}")
        self.setup_client()

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        self.log(f"Inlet function called with body: {body} and user: {user}")
        self.log(json.dumps(body, indent=2))
        metadata = body.get("metadata", {})
        task = metadata.get("task", "")

        if task:
            self.log(f"Skipping {task} task.")
            return body
        if "chat_id" not in metadata:
            chat_id = str(uuid.uuid4())  # Regular chat messages
            self.log(f"Assigned normal chat_id: {chat_id}")

            metadata["chat_id"] = chat_id
            body["metadata"] = metadata
        else:
            chat_id = metadata["chat_id"]

        user_email = "undefined"
        if user is not None:
            user_email = user.get("email")

        self.log(f"Creating new chat trace for chat_id: {chat_id}")

        span_metadata = metadata.copy()
        span_metadata.update({"interface": "open-webui"})

        # Extract the model and provider from metadata
        model = body.get("model") or "undefined"
        provider = "ollama"

        with self.tracer.start_as_current_span(f"inlet: {chat_id}") as span:
            # Set attributes on the span
            span.set_attribute("gen_ai.application_name", self.valves.otlp_service_name)
            span.set_attribute("gen_ai.endpoint", f"{provider}.chat")
            span.set_attribute("gen_ai.environment", "default")
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.response.finish_reasons", list("stop",))
            span.set_attribute("gen_ai.system", provider)
            span.set_attribute("gen_ai.usage.cost", 0.01)
            span.set_attribute("gen_ai.usage.input_tokens", 100)
            span.set_attribute("gen_ai.usage.output_tokens", 200)
            span.set_attribute("gen_ai.usage.total_tokens", 300)
            span.set_attribute("gen_ai.environment", "default")
            span.set_attribute("gen_ai.request.is_stream", "true")
            span.set_attribute("telemetry.sdk.name", "openlit")
            span.set_attribute("user_email", user_email)
            span.set_attribute("chat_id", chat_id)

            # Add event with body information
            span.add_event("request_body", attributes=body)
            span.set_status(Status(StatusCode.OK))

        return body

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        self.log(f"Outlet function called with body: {body}")
        model = body.get("model") or "undefined"
        provider = "ollama"
        user_email = "some"
        chat_id = "some"
        with self.tracer.start_as_current_span("outlet") as span:
            # Set attributes on the span
            span.set_attribute("gen_ai.application_name", self.valves.otlp_service_name)
            span.set_attribute("gen_ai.endpoint", f"{provider}.chat")
            span.set_attribute("gen_ai.environment", "default")
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.response.finish_reasons", ["stop",])
            span.set_attribute("gen_ai.system", provider)
            span.set_attribute("gen_ai.usage.cost", 0.01)
            span.set_attribute("gen_ai.usage.input_tokens", 100)
            span.set_attribute("gen_ai.usage.output_tokens", 200)
            span.set_attribute("gen_ai.usage.total_tokens", 300)
            span.set_attribute("gen_ai.environment", "default")
            span.set_attribute("gen_ai.request.is_stream", "true")
            span.set_attribute("telemetry.sdk.name", "openlit")
            span.set_attribute("user_email", user_email)
            span.set_attribute("chat_id", chat_id)
            span.set_status(Status(StatusCode.OK))
        return body

    def log(self, message: str):
        print(f"[DEBUG] {message}")
