"""
title: SUSE AI Monitoring Pipeline
author: Thiago Bertoldi (SUSE)
date: 2025-05-30
version: 1.0
license: Apache 2.0
description: A pipeline for monitoring Open WebUI with OpenLIT
requirements: openlit==1.33.8, ollama==0.3.3
"""

from typing import List, Union, Generator, Iterator
from pydantic import Field, BaseModel
from ollama import Client
import openlit


class Pipeline:
    class Valves(BaseModel):
        OTEL_ENDPOINT: str = Field(
            default="http://opentelemetry-collector.observability.svc.cluster.local:4318",
            description="Endpoint for OTEL Collector"
        )
        OTEL_SERVICE_NAME: str = Field(
            default="Open WebUI",
            description="Sets service.name resource attribute for OpenTelemetry"
        )
        OLLAMA_ENDPOINT: str = Field(
            default="http://ollama.suse-private-ai.svc.cluster.local:11434",
            description="Endpoint for Ollama API"
        )
        MODEL: str = Field(
            default="gemma:2b",
            description="Sets the model in use"
        )
        PRICING: str = Field(
            default="https://raw.githubusercontent.com/thbertoldi/oi-openlit/refs/heads/main/pricing.json",
            description="Pricing file"
        )

        pass

    def __init__(self):
        self.name = "Instrumentation"
        self.valves = self.Valves()
        pass

    def setup_openlit(self):
        #TODO: Handle configuration changes
        global __name__
        __name__ = self.valves.MODEL
        openlit.init(
            otlp_endpoint=self.valves.OTEL_ENDPOINT,
            disable_batch=True,
            trace_content=True,
            application_name=self.valves.OTEL_SERVICE_NAME,
            collect_gpu_stats=False,
            pricing_json=self.valves.PRICING,
        )

    async def on_startup(self):
        print(f"on_startup:{__name__}")
        self.setup_openlit()
        pass

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")
        pass

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")

        client = Client(
            host=self.valves.OLLAMA_ENDPOINT,
        )

        #TODO: Handle model memory
        completion = client.chat(
            model=self.valves.MODEL,
            messages=[{"role": "user", "content": user_message}],
        )

        return completion['message']['content']
