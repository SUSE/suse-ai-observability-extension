"""Exercise the shipped Collector transforms through OTLP/HTTP.

Only transport endpoints/exporters and flush intervals are replaced. The test
uses an official contrib binary, so a custom topology exporter cannot satisfy it.
"""

import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid

import yaml

from test_contract import ROOT, component, mapped, record


def attributes(values):
    return [
        {
            "key": key,
            "value": {"intValue": str(value)}
            if isinstance(value, int)
            else {"stringValue": value},
        }
        for key, value in values.items()
    ]


def decoded(values):
    return {item["key"]: next(iter(item["value"].values())) for item in values}


@unittest.skipUnless(
    os.environ.get("AI_COLLECTOR_IMAGE"),
    "Set AI_COLLECTOR_IMAGE to run the Docker integration test",
)
class CollectorTest(unittest.TestCase):
    def test_shipped_receiver_overlays_resolve_all_pipeline_components(self):
        # Loading only collector.yaml missed a dangling exporter reference in
        # the product overlay. Validate exactly the multi-file invocation.
        for overlay in ("vllm-receiver.yaml", "kubernetes-receiver.yaml", "dcgm-receiver.yaml", "litellm-receiver.yaml"):
            with self.subTest(overlay=overlay):
                subprocess.run(
                    [
                        os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "run", "--rm", "--network", "none",
                        "-v", f"{ROOT / 'examples/suse-ai'}:/config:ro,z",
                        "-e", "SUSE_OBSERVABILITY_OTLP_ENDPOINT=localhost:4317",
                        "-e", "SUSE_OBSERVABILITY_API_KEY=test",
                        "-e", "VLLM_SERVICE_NAME=vllm",
                        "-e", "VLLM_SERVICE_NAMESPACE=demo",
                        "-e", "VLLM_METRICS_TARGET=localhost:8000",
                        "-e", "OBSERVED_NAMESPACE=demo",
                        "-e", "K8S_CLUSTER_NAME=test-cluster",
                        "-e", "DCGM_EXPORTER_NAMESPACE=gpu-operator",
                        os.environ["AI_COLLECTOR_IMAGE"], "validate",
                        "--config=/config/collector.yaml",
                        f"--config=/config/{overlay}",
                    ],
                    check=True, capture_output=True, text=True,
                )

    def test_otlp_identity_compatibility_and_signal_preservation(self):
        image = os.environ["AI_COLLECTOR_IMAGE"]
        container = "suse-ai-test-" + uuid.uuid4().hex[:10]
        with tempfile.TemporaryDirectory(prefix="suse-ai-collector-") as directory:
            directory = Path(directory)
            directory.chmod(0o777)
            config = yaml.safe_load(
                (ROOT / "examples/suse-ai/collector.yaml").read_text()
            )
            # Fail on any actual transformation error instead of hiding it.
            for key in ("transform/suse_ai_resource", "transform/genai_compat"):
                config["processors"][key]["error_mode"] = "propagate"
            config["exporters"] = {
                "file/" + signal: {
                    "path": "/test/" + signal + ".json",
                    "flush_interval": "100ms",
                }
                for signal in ("traces", "metrics", "logs")
            }
            for name, pipeline in config["service"]["pipelines"].items():
                pipeline["exporters"] = ["file/" + name.split('/')[0] if e == 'otlp_grpc/suse'
                                         else e for e in pipeline["exporters"]]
            config["connectors"]["span_metrics"]["metrics_flush_interval"] = "1s"
            config["connectors"]["service_graph/suse_ai"]["metrics_flush_interval"] = "1s"
            config_path = directory / "collector.yaml"
            config_path.write_text(yaml.safe_dump(config, sort_keys=False))
            subprocess.run(
                [
                    os.environ.get("AI_CONTAINER_RUNTIME", "docker"),
                    "run",
                    "--detach",
                    "--name",
                    container,
                    "--publish",
                    "127.0.0.1::4318",
                    "--volume",
                    str(directory) + ":/test:rw,z",
                    image,
                    "--config=/test/collector.yaml",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            try:
                endpoint = (
                    "http://"
                    + subprocess.check_output(
                        [os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "port", container, "4318/tcp"], text=True
                    ).strip()
                )
                now = time.time_ns()
                resource = {
                    "service.name": "assistant",
                    "service.namespace": "prod-eu",
                    "service.instance.id": "pod-1",
                    "telemetry.sdk.name": "opentelemetry",
                    "suse.ai.component.type": "model-proxy.litellm",
                }
                legacy = {
                    "gen_ai.system": "openai",
                    "gen_ai.request.model": "llama3",
                    "gen_ai.usage.prompt_tokens": 12,
                    "gen_ai.usage.completion_tokens": 8,
                    "server.address": "model.example",
                    "server.port": 443,
                }
                spans = [
                    {
                        "traceId": "1" * 32,
                        "spanId": "2" * 16,
                        "name": "chat llama3",
                        "kind": 3,
                        "startTimeUnixNano": str(now - 100000000),
                        "endTimeUnixNano": str(now),
                        "attributes": attributes(legacy),
                    },
                    {
                        "traceId": "1" * 32,
                        "spanId": "3" * 16,
                        "name": "planner.agent",
                        "kind": 1,
                        "startTimeUnixNano": str(now - 200000000),
                        "endTimeUnixNano": str(now),
                        "attributes": attributes(
                            {
                                "traceloop.span.kind": "agent",
                                "traceloop.entity.name": "planner",
                            }
                        ),
                    },
                    {
                        "traceId": "4" * 32,
                        "spanId": "5" * 16,
                        "name": "chat native",
                        "kind": 3,
                        "startTimeUnixNano": str(now - 100000000),
                        "endTimeUnixNano": str(now),
                        "attributes": attributes(
                            {
                                "gen_ai.provider.name": "anthropic",
                                "gen_ai.system": "legacy-value",
                                "gen_ai.request.model": "claude",
                                "gen_ai.usage.input_tokens": 5,
                            }
                        ),
                    },
                ]
                trace_data = {
                    "resourceSpans": [
                        {
                            "resource": {"attributes": attributes(resource)},
                            "scopeSpans": [
                                {
                                    "scope": {
                                        "name": "opentelemetry.instrumentation.openai"
                                    },
                                    "spans": spans,
                                }
                            ],
                        }
                    ]
                }
                paired_spans = []
                # Two client replicas call the same service in another namespace.
                # Both sides are real CLIENT/SERVER spans with matching parents.
                for replica in (1, 2):
                    trace_id = str(replica + 5) * 32
                    client_id, server_id = str(replica + 5) * 16, str(replica + 7) * 16
                    for service, namespace, instance, span_id, parent, kind in (
                        ('caller', 'front', f'pod-{replica}', client_id, '', 3),
                        ('backend', 'back', 'server-1', server_id, client_id, 2),
                    ):
                        span = {'traceId': trace_id, 'spanId': span_id, 'name': 'rpc ' + service,
                                'kind': kind, 'startTimeUnixNano': str(now - 100000000),
                                'endTimeUnixNano': str(now)}
                        if parent:
                            span['parentSpanId'] = parent
                        if kind == 3 and replica == 1:
                            # A resolved provider call and its paired server use
                            # one shared relation mapping after normalization.
                            span['attributes'] = attributes({
                                'server.address': 'backend.back.svc.cluster.local',
                                'suse.ai.peer.service.name': 'backend',
                                'suse.ai.peer.service.namespace': 'back',
                                'suse.ai.peer.cluster': 'cluster-one',
                            })
                        paired_spans.append(span)
                        trace_data['resourceSpans'].append({
                            'resource': {'attributes': attributes({'service.name': service,
                                'service.namespace': namespace, 'service.instance.id': instance,
                                'k8s.cluster.name': 'cluster-one'})},
                            'scopeSpans': [{'spans': [span]}]})
                point = {
                    "attributes": attributes(
                        {
                            "gen_ai.system": "openai",
                            "gen_ai.request.model": "llama3",
                            "gen_ai.token.type": "input",
                            "server.address": "model.example",
                            "server.port": 443,
                        }
                    ),
                    "startTimeUnixNano": str(now - 1000000000),
                    "timeUnixNano": str(now),
                    "count": "1",
                    "sum": 12,
                    "explicitBounds": [10, 20],
                    "bucketCounts": ["0", "1", "0"],
                }
                metric_data = {
                    "resourceMetrics": [
                        {
                            "resource": {"attributes": attributes(resource)},
                            "scopeMetrics": [
                                {
                                    "scope": {"name": "openlit.otel"},
                                    "metrics": [
                                        {
                                            "name": "gen_ai.client.token.usage",
                                            "unit": "{token}",
                                            "histogram": {
                                                "dataPoints": [point],
                                                "aggregationTemporality": 2,
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
                metric_only = copy.deepcopy(point)
                metric_only['attributes'] = attributes({
                    'gen_ai.provider.name': 'openai', 'gen_ai.request.model': 'metric-only'})
                metric_data['resourceMetrics'][0]['scopeMetrics'][0]['metrics'][0]['histogram']['dataPoints'].append(metric_only)
                log_data = {
                    "resourceLogs": [
                        {
                            "resource": {"attributes": attributes(resource)},
                            "scopeLogs": [
                                {
                                    "scope": {"name": "evaluation-fixture"},
                                    "logRecords": [
                                        {
                                            "timeUnixNano": str(now),
                                            "traceId": "1" * 32,
                                            "spanId": "2" * 16,
                                            "eventName": "gen_ai.evaluation.result",
                                            "body": {"stringValue": "fixture-score"},
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }

                def post(signal, data):
                    payload = json.dumps(data).encode()
                    request = Request(
                        endpoint + "/v1/" + signal,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    with urlopen(request, timeout=2) as response:
                        body = json.loads(response.read() or b"{}")
                    self.assertFalse(body.get("partialSuccess"), body)

                deadline = time.monotonic() + 15
                while True:
                    try:
                        post("traces", trace_data)
                        break
                    except (URLError, ConnectionError):
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(0.1)
                post("metrics", metric_data)
                post("logs", log_data)

                def exported(signal):
                    path = directory / (signal + ".json")
                    if not path.exists():
                        return []
                    lines = path.read_text().splitlines()
                    try:
                        return [json.loads(line) for line in lines if line]
                    except json.JSONDecodeError:
                        return []  # A flush may be in progress.

                deadline = time.monotonic() + 15
                while not all(
                    exported(signal) for signal in ("traces", "metrics", "logs")
                ):
                    if time.monotonic() > deadline:
                        self.fail("Collector did not export all three signals")
                    time.sleep(0.1)
                def metric_names():
                    return {m['name'] for b in exported('metrics') for r in b['resourceMetrics']
                            for scope in r['scopeMetrics'] for m in scope['metrics']}
                while 'suse.ai.service.calls' not in metric_names():
                    if time.monotonic() > deadline:
                        self.fail('Collector did not emit service-call observations')
                    time.sleep(0.1)
                # The service-graph connector re-exports cached cumulative
                # counts. Idle flushes must not extend topology lifetimes.
                time.sleep(3)
                # Graceful shutdown flushes the final batch before counting spans.
                subprocess.run(
                    [os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "stop", "--time", "10", container],
                    check=True,
                    capture_output=True,
                )
                trace_resources = [
                    r for batch in exported("traces") for r in batch["resourceSpans"]
                ]
                emitted = [
                    s
                    for r in trace_resources
                    for scope in r["scopeSpans"]
                    for s in scope["spans"]
                ]
                self.assertEqual(
                    len(emitted), 7, "Synthetic topology copies must not be exported"
                )
                self.assertEqual(
                    {s["spanId"] for s in emitted}, {s["spanId"] for s in spans + paired_spans}
                )
                normalized_resource = decoded(
                    trace_resources[0]["resource"]["attributes"]
                )
                for key, value in resource.items():
                    self.assertEqual(normalized_resource[key], value)
                self.assertEqual(normalized_resource["suse.ai.product"], "litellm")
                by_name = {s["name"]: decoded(s.get("attributes", [])) for s in emitted}
                self.assertEqual(
                    by_name["chat llama3"]["gen_ai.provider.name"], "openai"
                )
                self.assertEqual(by_name["chat llama3"]["gen_ai.system"], "openai")
                self.assertEqual(
                    int(by_name["chat llama3"]["gen_ai.usage.input_tokens"]), 12
                )
                self.assertEqual(
                    by_name["planner.agent"]["gen_ai.agent.name"], "planner"
                )
                self.assertEqual(
                    by_name["chat native"]["gen_ai.provider.name"], "anthropic"
                )

                metric_resources = [
                    r for batch in exported("metrics") for r in batch["resourceMetrics"]
                ]
                genai = [
                    (r, m)
                    for r in metric_resources
                    for scope in r["scopeMetrics"]
                    for m in scope["metrics"]
                    if m["name"] == "gen_ai.client.token.usage"
                ]
                self.assertEqual(len(genai), 1)
                self.assertEqual(genai[0][1]["histogram"]["dataPoints"][0]["sum"], 12)
                metric_attributes = decoded(
                    genai[0][1]["histogram"]["dataPoints"][0]["attributes"]
                )
                self.assertEqual(metric_attributes["gen_ai.provider.name"], "openai")
                trace_component = component(
                    record(
                        resource=normalized_resource, attributes=by_name["chat llama3"]
                    ),
                    "genai model usage",
                )
                metric_component = component(
                    record(
                        "METRICS",
                        resource=normalized_resource,
                        attributes=metric_attributes,
                    ),
                    "genai model usage",
                )
                self.assertEqual(
                    trace_component["identifier"], metric_component["identifier"]
                )
                evidence = []
                for r in metric_resources:
                    for scope in r['scopeMetrics']:
                        for m in scope['metrics']:
                            for payload in ('sum', 'gauge', 'histogram'):
                                for dp in m.get(payload, {}).get('dataPoints', []):
                                    evidence.append(record('METRICS',
                                        resource=decoded(r.get('resource', {}).get('attributes', [])),
                                        attributes=decoded(dp.get('attributes', [])), metric=m['name']))
                evidence.extend(record(resource=normalized_resource, attributes=attrs)
                                for attrs in by_name.values())
                model_names = {c['name'] for e in evidence for c in mapped(e)
                               if c['typeName'] == 'genai model usage'}
                self.assertEqual(model_names, {'llama3', 'claude', 'metric-only'},
                                 'Trace-only, metric-only and dual-signal model usage must remain available')
                model_ids = {c['identifier'] for e in evidence for c in mapped(e)
                             if c['typeName'] == 'genai model usage'}
                self.assertFalse(any(model_ids.intersection((r['sourceId'], r['targetId']))
                                     for e in evidence for r in mapped(e, 'OtelRelationMapping')),
                                 'Model usage must not create a direct runtime communication path')
                self.assertNotIn('suse.ai.model.observations', metric_names(),
                                 'Model inventory uses original telemetry without a redundant Count pipeline')
                calls = {tuple((r['sourceId'], r['targetId'])) for e in evidence
                         for r in mapped(e, 'OtelRelationMapping') if r['typeName'] == 'synchronous'}
                self.assertEqual(calls, {('urn:opentelemetry:namespace/front:service/caller',
                                         'urn:opentelemetry:namespace/back:service/backend')})
                call_points = [dp for r in metric_resources for scope in r['scopeMetrics']
                               for m in scope['metrics'] if m['name'] == 'suse.ai.service.calls'
                               for dp in m['gauge']['dataPoints']]
                self.assertEqual(sum(int(dp['asInt']) for dp in call_points), 3,
                                 'Idle flushes must not replay observed calls')
                resolved = [dp for dp in call_points
                            if 'suse.ai.peer.service.name' in decoded(dp['attributes'])]
                self.assertEqual(sum(int(dp['asInt']) for dp in resolved), 1,
                                 'Only the explicitly resolved CLIENT span contributes')
                self.assertNotIn('traces_service_graph_request_total', metric_names(),
                                 'Do not feed a second service-graph producer into the base mapping')
                logs = [
                    entry
                    for batch in exported("logs")
                    for r in batch["resourceLogs"]
                    for scope in r["scopeLogs"]
                    for entry in scope["logRecords"]
                ]
                self.assertEqual(len(logs), 1)
                self.assertEqual(logs[0]["traceId"], "1" * 32)
                self.assertEqual(logs[0]["spanId"], "2" * 16)
            except Exception:
                print(
                    subprocess.check_output(
                        [os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "logs", container],
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                )
                raise
            finally:
                subprocess.run(
                    [os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "rm", "--force", container],
                    check=False,
                    capture_output=True,
                )
