"""
title: SUSE AI Ollama observability
author: SUSE
version: 0.1.1
description: Correlated provider telemetry for Open WebUI 0.6.41 and Ollama.
required_open_webui_version: 0.6.41
"""

import asyncio
from contextvars import ContextVar
from functools import wraps
import inspect
import json
import time
from urllib.parse import urlsplit

from opentelemetry import metrics, trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from pydantic import BaseModel, Field


SCOPE = "suse.ai.open_webui.ollama"
VERSION = "0.1.1"


class Endpoint(BaseModel):
    """Explicit association with an already discovered canonical OTel service."""

    cluster: str
    kubernetes_namespace: str
    kubernetes_service: str
    port: int
    service_namespace: str
    service_name: str
    dns_domain: str = "cluster.local"


def resolve_endpoint(host, port, cluster, namespace, endpoints):
    """Resolve only configured Kubernetes service addresses in the caller cluster.

    A short name is local to the caller namespace. Duplicate, conflicting entries
    are ambiguous and produce no peer identity. An address or provider name alone
    is never treated as the destination's OTel service name.
    """
    if not host or not cluster or not namespace:
        return None
    host = host.lower().rstrip(".")
    matches = set()
    for target in endpoints:
        if target.cluster != cluster or target.port != port:
            continue
        if not all((target.service_namespace, target.service_name,
                    target.kubernetes_namespace, target.kubernetes_service)):
            continue
        name = target.kubernetes_service
        ns = target.kubernetes_namespace
        aliases = {f"{name}.{ns}", f"{name}.{ns}.svc",
                   f"{name}.{ns}.svc.{target.dns_domain}"}
        if ns == namespace:
            aliases.add(name)
        if host in aliases:
            matches.add((target.service_namespace, target.service_name))
    if len(matches) != 1:
        return None
    service_namespace, service_name = matches.pop()
    return {"suse.ai.peer.service.namespace": service_namespace,
            "suse.ai.peer.service.name": service_name,
            "suse.ai.peer.cluster": cluster}


def endpoint_attributes(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return {}
        return {"server.address": parsed.hostname.lower().rstrip("."),
                "server.port": parsed.port or (443 if parsed.scheme == "https" else 80)}
    except ValueError:
        return {}


class Operation:
    """One provider invocation, independent of chat IDs and UI callbacks."""

    def __init__(self, payload, url, settings, tracer, meter):
        self.started = time.monotonic()
        self.finished = False
        self.complete = False
        self.response = {}
        self.buffer = b""
        self.discard_line = False
        self.attributes = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "ollama",
            "gen_ai.request.model": payload["model"],
            **endpoint_attributes(url),
        }
        peer = resolve_endpoint(
            self.attributes.get("server.address"), self.attributes.get("server.port"),
            settings.caller_cluster, settings.caller_namespace, settings.endpoints,
        )
        self.span = tracer.start_span(
            f"chat {payload['model']}", kind=SpanKind.CLIENT,
            attributes={**self.attributes, **(peer or {})},
        )
        # Reuse the application's providers and export pipeline. No second SDK or
        # resource identity is created by this extension.
        self.duration = meter.create_histogram(
            "gen_ai.client.operation.duration", unit="s",
            description="Time from provider request to completion, failure or cancellation.",
            explicit_bucket_boundaries_advisory=(
                .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60, 120,
            ),
        )
        self.tokens = meter.create_histogram("gen_ai.client.token.usage", unit="{token}")

    def observe(self, value):
        if not isinstance(value, dict):
            return
        # Do not store prompts, generated content, IDs or exception messages.
        for key in ("model", "prompt_eval_count", "eval_count", "done_reason"):
            if key in value:
                self.response[key] = value[key]
        if value.get("error"):
            self.response["error"] = True
        if value.get("done") is True:
            self.complete = True

    def chunk(self, data):
        """Read bounded NDJSON lines without altering the forwarded stream."""
        data = data.encode() if isinstance(data, str) else data
        for part in data.splitlines(keepends=True):
            ending = part.endswith(b"\n")
            if self.discard_line:
                if ending:
                    self.discard_line = False
                continue
            if len(self.buffer) + len(part) > 65536:
                self.buffer = b""
                self.discard_line = not ending
                continue
            self.buffer += part
            if ending:
                self.flush_line()

    def flush_line(self):
        if self.buffer:
            try:
                self.observe(json.loads(self.buffer))
            except (ValueError, UnicodeError):
                pass
            self.buffer = b""

    def finish(self, error=None):
        if self.finished:
            return
        self.finished = True
        self.flush_line()
        attrs = dict(self.attributes)
        model = self.response.get("model")
        if isinstance(model, str) and model:
            attrs["gen_ai.response.model"] = model
            self.span.set_attribute("gen_ai.response.model", model)
        error = error or ("provider_error" if self.response.get("error") else None)
        if not error and not self.complete:
            error = "incomplete_response"
        if error:
            attrs["error.type"] = error
            self.span.set_attribute("error.type", error)
            self.span.set_status(Status(StatusCode.ERROR))
        else:
            self.span.set_status(Status(StatusCode.OK))
        reason = self.response.get("done_reason")
        if isinstance(reason, str) and reason:
            self.span.set_attribute("gen_ai.response.finish_reasons", [reason])
        # Only provider-reported nonnegative integer usage is recorded. An absent
        # usage record (including cancellation) is not a zero-token observation.
        for key, token_type in (("prompt_eval_count", "input"), ("eval_count", "output")):
            count = self.response.get(key)
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                self.span.set_attribute(f"gen_ai.usage.{token_type}_tokens", count)
                self.tokens.record(count, {**attrs, "gen_ai.token.type": token_type})
        self.duration.record(time.monotonic() - self.started, attrs)
        self.span.end()


def error_type(error):
    if isinstance(error, (asyncio.CancelledError, GeneratorExit)):
        return "cancelled"
    code = getattr(error, "status_code", None)
    return f"http_{code}" if isinstance(code, int) else type(error).__name__


def wrap_provider(original, current, tracer=None, meter=None):
    signature = inspect.signature(original)

    @wraps(original)
    async def send_post_request(*args, **kwargs):
        settings = current.get()
        if settings is None or not settings.enabled:
            return await original(*args, **kwargs)
        bound = signature.bind(*args, **kwargs)
        url = bound.arguments.get("url", "")
        if urlsplit(url).path.rstrip("/") != "/api/chat":
            return await original(*args, **kwargs)
        try:
            payload = json.loads(bound.arguments["payload"])
        except (TypeError, ValueError, KeyError):
            return await original(*args, **kwargs)
        if not isinstance(payload, dict) or not isinstance(payload.get("model"), str) or not payload["model"]:
            return await original(*args, **kwargs)
        operation = Operation(
            payload, url, settings,
            tracer or trace.get_tracer(SCOPE, VERSION),
            meter or metrics.get_meter(SCOPE, VERSION),
        )
        try:
            with trace.use_span(operation.span, end_on_exit=False,
                                record_exception=False, set_status_on_exception=False):
                response = await original(*args, **kwargs)
        except BaseException as error:
            operation.finish(error_type(error))
            raise
        if not hasattr(response, "body_iterator"):
            operation.observe(response)
            operation.finish()
            return response

        iterator = response.body_iterator

        async def observed_body():
            try:
                async for chunk in iterator:
                    operation.chunk(chunk)
                    yield chunk
            except BaseException as error:
                operation.finish(error_type(error))
                raise
            finally:
                operation.finish()

        response.body_iterator = observed_body()
        original_background = response.background

        async def cleanup():
            try:
                if original_background:
                    await original_background()
            finally:
                # Covers a response that was closed before the iterator started.
                operation.finish("cancelled" if not operation.complete else None)

        response.background = cleanup
        return response

    return send_post_request


def install(router):
    """Install once per worker; changing wrapper code requires a worker restart."""
    if not hasattr(router, "_suse_ai_ollama_current"):
        current = ContextVar("suse_ai_ollama_current", default=None)
        router._suse_ai_ollama_current = current
        router.send_post_request = wrap_provider(router.send_post_request, current)
    return router._suse_ai_ollama_current


class Filter:
    class Valves(BaseModel):
        enabled: bool = True
        priority: int = 0
        caller_cluster: str = Field(default="", description="Actual caller cluster; required only for dependency resolution.")
        caller_namespace: str = Field(default="", description="Actual caller Kubernetes namespace, used for short DNS names.")
        endpoints: list[Endpoint] = Field(default_factory=list, description="Explicit Kubernetes endpoint to canonical OTel service associations.")

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(self, body: dict) -> dict:
        from open_webui.routers import ollama

        install(ollama).set(self.valves.model_copy(deep=True))
        return body
