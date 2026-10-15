"""Provider lifecycle tests using real OTel SDKs and native aiohttp spans."""

import asyncio
from contextvars import ContextVar
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import aiohttp
from aiohttp import web
from opentelemetry import trace
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException
from starlette.responses import StreamingResponse


spec = importlib.util.spec_from_file_location(
    "suse_ai_ollama", Path(__file__).resolve().parents[1] / "suse_ai_ollama.py"
)
integration = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = integration
spec.loader.exec_module(integration)


class ResolutionTests(unittest.TestCase):
    def target(self, cluster="one", namespace="ai", **extra):
        return integration.Endpoint(
            cluster=cluster, kubernetes_namespace=namespace,
            kubernetes_service="ollama", port=11434,
            service_namespace=extra.pop("service_namespace", namespace),
            service_name=extra.pop("service_name", "inference"), **extra,
        )

    def test_explicit_namespace_and_cluster_scoping(self):
        targets = [self.target(), self.target(namespace="other"),
                   self.target(cluster="two", service_name="second-inference")]
        for host in ("ollama", "ollama.ai", "ollama.ai.svc", "ollama.ai.svc.cluster.local."):
            result = integration.resolve_endpoint(host, 11434, "one", "ai", targets)
            self.assertEqual(result["suse.ai.peer.service.name"], "inference")
            self.assertEqual(result["suse.ai.peer.service.namespace"], "ai")
        self.assertEqual(integration.resolve_endpoint(
            "ollama", 11434, "one", "other", targets
        )["suse.ai.peer.service.namespace"], "other")
        self.assertEqual(integration.resolve_endpoint(
            "ollama.ai.svc", 11434, "two", "ai", targets
        )["suse.ai.peer.service.name"], "second-inference")

    def test_unknown_ambiguous_or_unscoped_endpoints_are_not_resolved(self):
        target = self.target()
        for host, port, cluster, namespace in (
            ("ollama", 11434, "", "ai"), ("ollama", 11434, "one", ""),
            ("ollama", 11434, "one", "unrelated"),
            ("ollama", 443, "one", "ai"), ("external.example", 11434, "one", "ai"),
            (None, None, "one", "ai"),
        ):
            self.assertIsNone(integration.resolve_endpoint(host, port, cluster, namespace, [target]))
        self.assertIsNone(integration.resolve_endpoint(
            "ollama.ai", 11434, "one", "ai", [target, self.target(service_name="other")]
        ))

    def test_url_attributes_are_sanitized_or_omitted(self):
        self.assertEqual(integration.endpoint_attributes("https://secret:password@Host/path?q=secret"),
                         {"server.address": "host", "server.port": 443})
        for value in ("", "relative/path", "http://host:wrong", "file:///tmp/model"):
            self.assertEqual(integration.endpoint_attributes(value), {})


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = self.provider.get_tracer(integration.SCOPE)
        self.reader = InMemoryMetricReader()
        self.meters = MeterProvider(metric_readers=[self.reader])
        self.meter = self.meters.get_meter(integration.SCOPE)
        self.current = ContextVar("test_settings", default=integration.Filter.Valves())
        self.finished = 0

    async def asyncTearDown(self):
        self.provider.shutdown()
        self.meters.shutdown()

    def wrap(self, original):
        return integration.wrap_provider(original, self.current, self.tracer, self.meter)

    def operations(self):
        return [s for s in self.exporter.get_finished_spans() if s.name.startswith("chat ")]

    def data(self, name):
        data = self.reader.get_metrics_data()
        return [point for resource in data.resource_metrics for scope in resource.scope_metrics
                for metric in scope.metrics if metric.name == name for point in metric.data.data_points]

    async def test_native_http_child_and_exact_usage_for_ten_operations(self):
        async def respond(request):
            await request.json()
            return web.json_response({"model": "llama3.2:latest", "done": True,
                                      "prompt_eval_count": 7, "eval_count": 11})
        app = web.Application()
        app.router.add_post("/api/chat", respond)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        AioHttpClientInstrumentor().instrument(tracer_provider=self.provider)

        async def original(url, payload, stream=False):
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    return await response.json()

        try:
            wrapped = self.wrap(original)
            with self.tracer.start_as_current_span("inbound", kind=trace.SpanKind.SERVER) as inbound:
                parent = inbound.get_span_context()
                for _ in range(10):
                    await wrapped(f"http://127.0.0.1:{port}/api/chat", json.dumps({"model": "llama3.2:latest"}))
            operations = self.operations()
            clients = [s for s in self.exporter.get_finished_spans() if s.name == "POST"]
            self.assertEqual(len(operations), 10)
            self.assertEqual(len(clients), 10)
            self.assertTrue(all(s.context.trace_id == parent.trace_id and s.parent.span_id == parent.span_id for s in operations))
            self.assertEqual({s.parent.span_id for s in clients}, {s.context.span_id for s in operations})
            self.assertEqual(sum(p.count for p in self.data("gen_ai.client.operation.duration")), 10)
            token_points = self.data("gen_ai.client.token.usage")
            self.assertEqual({p.attributes["gen_ai.token.type"]: p.sum for p in token_points}, {"input": 70, "output": 110})
            self.assertTrue(all(p.attributes["server.port"] == port for p in token_points))
        finally:
            AioHttpClientInstrumentor().uninstrument()
            await runner.cleanup()

    async def test_stream_finishes_at_consumption_and_cleanup_is_idempotent(self):
        async def body():
            yield b'{"message":{"content":"hi"},"done":false}\n'
            yield b'{"model":"llama3.2","done":true,"prompt_eval_'
            yield b'count":3,"eval_count":2}\n'

        async def cleanup():
            self.finished += 1

        async def original(url, payload):
            return StreamingResponse(body(), background=BackgroundTask(cleanup))

        result = await self.wrap(original)("http://ollama:11434/api/chat", '{"model":"llama3.2"}')
        self.assertEqual(self.operations(), [])
        chunks = [chunk async for chunk in result.body_iterator]
        await result.background()
        await result.background()  # A late/repeated completion must not emit again.
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(self.operations()), 1)
        self.assertEqual(self.operations()[0].attributes["gen_ai.usage.output_tokens"], 2)
        self.assertEqual(sum(p.count for p in self.data("gen_ai.client.operation.duration")), 1)

    async def test_cancelled_stream_has_duration_without_invented_usage(self):
        entered = asyncio.Event()

        async def body():
            yield b'{"message":{"content":"partial"},"done":false}\n'
            entered.set()
            await asyncio.sleep(60)

        async def original(url, payload):
            return StreamingResponse(body())

        response = await self.wrap(original)("http://ollama:11434/api/chat", '{"model":"llama3.2"}')

        async def consume():
            async for _ in response.body_iterator:
                pass

        task = asyncio.create_task(consume())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await response.background()
        self.assertEqual(len(self.operations()), 1)
        self.assertEqual(self.operations()[0].attributes["error.type"], "cancelled")
        self.assertEqual(self.data("gen_ai.client.token.usage"), [])
        self.assertEqual(sum(p.count for p in self.data("gen_ai.client.operation.duration")), 1)

    async def test_stream_not_consumed_and_truncated_stream_are_finalized(self):
        async def body():
            yield b'{"done":false}\n'

        async def original(url, payload):
            return StreamingResponse(body())

        wrapper = self.wrap(original)
        response = await wrapper("http://ollama:11434/api/chat", '{"model":"unconsumed"}')
        await response.background()
        response = await wrapper("http://ollama:11434/api/chat", '{"model":"truncated"}')
        async for _ in response.body_iterator:
            pass
        self.assertEqual([s.attributes["error.type"] for s in self.operations()], ["cancelled", "incomplete_response"])
        self.assertEqual(self.data("gen_ai.client.token.usage"), [])

    async def test_closing_stream_after_first_chunk_records_cancellation_once(self):
        async def body():
            yield b'{"done":false}\n'
            await asyncio.sleep(60)

        async def original(url, payload):
            return StreamingResponse(body())

        response = await self.wrap(original)("http://ollama:11434/api/chat", '{"model":"cancel"}')
        await anext(response.body_iterator)
        await response.body_iterator.aclose()
        await response.background()
        self.assertEqual([s.attributes["error.type"] for s in self.operations()], ["cancelled"])
        self.assertEqual(self.data("gen_ai.client.token.usage"), [])

    async def test_reload_reuses_wrapper_and_request_context_without_a_second_provider(self):
        async def original(url, payload):
            return {"done": True}

        router = SimpleNamespace(send_post_request=original)
        current = integration.install(router)
        wrapper = router.send_post_request
        self.assertIs(integration.install(router), current)
        self.assertIs(router.send_post_request, wrapper)
        self.assertIs(wrapper.__wrapped__, original)
        # Valve changes are consumed from request-local snapshots. The existing
        # wrapper is deliberately retained until the worker is restarted.
        current.set(integration.Filter.Valves(enabled=False))
        self.assertEqual(await wrapper("http://ollama:11434/api/chat", '{"model":"inactive"}'), {"done": True})

    async def test_concurrent_requests_do_not_share_state(self):
        async def original(url, payload, metadata=None):
            value = json.loads(payload)
            await asyncio.sleep(0.01)
            return {"done": True, "model": value["model"], "eval_count": value["n"]}

        wrapper = self.wrap(original)
        await asyncio.gather(*(wrapper("http://ollama:11434/api/chat", json.dumps({"model": f"model-{n}", "n": n}),
                                               metadata={"chat_id": "same" if n < 2 else str(n)}) for n in range(4)))
        self.assertEqual({s.name: s.attributes["gen_ai.usage.output_tokens"] for s in self.operations()},
                         {f"chat model-{n}": n for n in range(4)})

    async def test_provider_errors_preserve_application_error_without_content_capture(self):
        async def original(url, payload):
            raise HTTPException(404, "private prompt must not be recorded")
        with self.assertRaises(HTTPException):
            await self.wrap(original)("http://ollama:11434/api/chat", '{"model":"missing"}')
        span = self.operations()[0]
        self.assertEqual(span.attributes["error.type"], "http_404")
        self.assertEqual(span.events, ())
        self.assertEqual(self.data("gen_ai.client.token.usage"), [])

    async def test_non_chat_and_inactive_requests_are_untouched(self):
        async def original(url, payload):
            return {"done": True}
        wrapped = self.wrap(original)
        await wrapped("http://ollama:11434/api/embeddings", '{"model":"embedding"}')
        self.current.set(None)
        await wrapped("http://ollama:11434/api/chat", '{"model":"ordinary"}')
        self.assertEqual(self.operations(), [])

    async def test_different_models_endpoints_and_unknown_endpoint_stay_separate(self):
        async def original(url, payload):
            return {"done": True, "eval_count": 1}
        wrapped = self.wrap(original)
        for host, model in (("http://one:11434", "model"), ("http://two:11434", "model"),
                            ("http://one:11434", "other"), ("", "model")):
            await wrapped(host + "/api/chat", json.dumps({"model": model}))
        points = self.data("gen_ai.client.operation.duration")
        self.assertEqual(len(points), 4)
        self.assertEqual(len({(p.attributes.get("server.address"), p.attributes["gen_ai.request.model"]) for p in points}), 4)


if __name__ == "__main__":
    unittest.main()
