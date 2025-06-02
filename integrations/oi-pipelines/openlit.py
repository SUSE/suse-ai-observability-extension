"""
title: SUSE AI Monitoring Pipeline
author: Thiago Bertoldi (SUSE)
date: 2025-05-30
version: 1.0
license: Apache 2.0
description: A pipeline for monitoring Open WebUI with OpenLIT
requirements: openlit==1.33.8, openai==1.61.1
"""

from typing import List, Union, Generator, Iterator
from pydantic import Field, BaseModel
from openai import OpenAI
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
            default="http://ollama.suse-private-ai.svc.cluster.local:11434/v1",
            description="Endpoint for Ollama API"
        )
        OLLAMA_API_KEY: str = Field(
            default="ignored",
            description="Key for OpenAI compatible API"
        )
        MODEL: str = Field(
            default="gemma:2b",
            description="Sets the model in use"
        )
        pass

    def __init__(self):
        self.name = "Instrumentation"
        self.valves = self.Valves()
        pass

    def setup_openlit(self):
        #TODO: Handle configuration changes
        openlit.init(
            otlp_endpoint=self.valves.OTEL_ENDPOINT,
            disable_batch=True,
            trace_content=True,
            application_name=self.valves.OTEL_SERVICE_NAME,
            collect_gpu_stats=False,
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

        client = OpenAI(
            base_url=self.valves.OLLAMA_ENDPOINT,
            api_key=self.valves.OLLAMA_API_KEY
        )

        #TODO: Handle model memory
        completion = client.chat.completions.create(
            model=self.valves.MODEL,
            messages=[{"role": "user", "content": user_message}],
        )

        print(completion.choices[0].message.content)

        return completion.choices[0].message.content
