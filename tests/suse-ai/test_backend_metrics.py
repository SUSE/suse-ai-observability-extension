"""Opt-in checks of installed presentations and the actual native monitor runner.

Uses the same environment and isolated OTLP fixture as test_backend_identity.
The histograms are test telemetry, not measurements of a deployed Ollama server.
"""

import json
import subprocess
import time

from identity_fixture import attrs
from test_backend_identity import BackendTestCase, STS


class BackendMetricsTest(BackendTestCase):
    def query(self, expression):
        response = self.api(
            "/api/metrics/query_batch",
            {
                "queries": [
                    {
                        "id": "value",
                        "query": expression.replace("${__rate_interval}", "5m"),
                        "_type": "instant",
                        "time": str(getattr(self, "evaluation_time", int(time.time()))),
                    }
                ]
            },
        )
        return response["results"][0]["data"]["data"]["result"]

    def charts(self, component):
        now = int(time.time() * 1000)
        data = self.capture(
            str(component["id"]) + "-charts",
            self.api(
                f"/api/components/{component['id']}/metricPerspectiveData"
                f"?startTime={now - 600000}&endTime={now}"
            ),
        )
        return {
            m["boundMetricId"].get("metricId"): m
            for t in data["tabs"]
            for s in t["sections"]
            for m in s["metrics"]
        }

    def duration_samples(self, resources, endpoints, usage=False, tools=False):
        """Two caller replicas, cumulative counts every 30s, distinct endpoints."""
        now = time.time_ns()
        for sample in range(7):
            rows = []
            for resource, weight in resources:
                points = []
                for endpoint, failed, slow in endpoints:
                    for error, fraction in ((False, 10 - failed), (True, failed)):
                        if not fraction:
                            continue
                        count = (sample + 1) * fraction * weight
                        values = {
                            "gen_ai.provider.name": "ollama",
                            "gen_ai.request.model": "fixture-model",
                            **endpoint,
                            **({"error.type": "TimeoutError"} if error else {}),
                        }
                        points.append(
                            {
                                "attributes": attrs(values),
                                "startTimeUnixNano": str(now - 600_000_000_000),
                                "timeUnixNano": str(
                                    now - (6 - sample) * 30_000_000_000
                                ),
                                "count": str(count),
                                "sum": count * (50 if slow else 5),
                                "explicitBounds": [1, 10, 30, 60],
                                "bucketCounts": [
                                    "0",
                                    "0" if slow else str(count),
                                    "0",
                                    str(count) if slow else "0",
                                    "0",
                                ],
                            }
                        )
                metrics = [
                    {
                        "name": "gen_ai.client.operation.duration",
                        "unit": "s",
                        "histogram": {
                            "aggregationTemporality": 2,
                            "dataPoints": points,
                        },
                    }
                ]
                timestamp = str(now - (6 - sample) * 30_000_000_000)
                start = str(now - 600_000_000_000)
                count = (sample + 1) * 10 * weight
                if usage:
                    for metric_name, unit, amount, dimensions in (
                        (
                            "gen_ai.client.token.usage",
                            "tokens",
                            10,
                            {"gen_ai.token.type": "input"},
                        ),
                        (
                            "gen_ai.client.token.usage",
                            "tokens",
                            20,
                            {"gen_ai.token.type": "output"},
                        ),
                        ("gen_ai.client.operation.cost", "USD", 0.002, {}),
                    ):
                        metrics.append(
                            {
                                "name": metric_name,
                                "unit": unit,
                                "histogram": {
                                    "aggregationTemporality": 2,
                                    "dataPoints": [
                                        {
                                            "attributes": attrs(
                                                {
                                                    "gen_ai.provider.name": "ollama",
                                                    "gen_ai.request.model": "fixture-model",
                                                    **dimensions,
                                                }
                                            ),
                                            "timeUnixNano": timestamp,
                                            "startTimeUnixNano": start,
                                            "count": str(count),
                                            "sum": count * amount,
                                            "explicitBounds": [100],
                                            "bucketCounts": [str(count), "0"],
                                        }
                                    ],
                                },
                            }
                        )
                if tools:
                    metrics.append(
                        {
                            "name": "suse.ai.agent.tool.calls",
                            "sum": {
                                "aggregationTemporality": 2,
                                "isMonotonic": True,
                                "dataPoints": [
                                    {
                                        "attributes": attrs(
                                            {
                                                "tool.name": "calculate",
                                                "outcome": "success",
                                            }
                                        ),
                                        "timeUnixNano": timestamp,
                                        "startTimeUnixNano": start,
                                        "asInt": str(count),
                                    }
                                ],
                            },
                        }
                    )
                rows.append(
                    {
                        "resource": {"attributes": attrs(resource)},
                        "scopeMetrics": [{"metrics": metrics}],
                    }
                )
            self.send_payload("metrics", {"resourceMetrics": rows})

    def test_model_monitors_with_optional_endpoints(self):
        name = self.prefix + "-endpoint"
        namespace = "suse-ai-v2-demo"
        resources = [
            (
                {
                    **self.k8s,
                    "service.name": name,
                    "service.namespace": namespace,
                    "service.instance.id": name + f"-{i}",
                },
                weight,
            )
            for i, weight in enumerate((1, 3))
        ]
        cases = [
            ({}, 2, True),
            ({"server.port": "11434"}, 0, False),
            ({"server.address": "model.example"}, 4, False),
            ({"server.address": "model.example", "server.port": "11434"}, 0, True),
            (
                {"server.address": "model.+[1].example", "server.port": "11434"},
                6,
                False,
            ),
            ({"server.address": "modelXX1xexample", "server.port": "11434"}, 9, True),
            (
                {"server.address": 'quoted"$\\E.endpoint', "server.port": "11434"},
                8,
                False,
            ),
        ]
        self.duration_samples(resources, cases)
        expected = {
            f"urn:suse-ai:namespace/{namespace}:service/{name}:provider/ollama"
            f":address/{ep.get('server.address', '')}:port/{ep.get('server.port', '')}"
            ":model/fixture-model": (ep, failed / 10, 58.5 if slow else 9.55)
            for ep, failed, slow in cases
        }

        def components_ready():
            rows = self.snapshot(
                f'type = "genai model usage" and label = "service.name:{name}"'
            )["components"]
            return rows if len(rows) == len(cases) else False

        components = self.capture(
            "endpoint-models",
            self.wait_for(components_ready, "endpoint model identities"),
        )
        self.assertEqual({c["identifiers"][0] for c in components}, set(expected))
        self.wait_for(
            lambda: (
                len(
                    self.query(
                        "sum by (server_address, server_port) (rate("
                        f'gen_ai_client_operation_duration_seconds_count{{service_name="{name}"}}[5m]))'
                    )
                )
                == len(cases)
            ),
            "endpoint histogram ingestion",
        )

        for monitor, index, threshold in (
            ("model-usage-errors", 1, 0.05),
            ("model-usage-latency", 2, 30),
        ):
            result = self.capture(
                monitor,
                json.loads(
                    subprocess.check_output(
                        [
                            *STS,
                            "monitor",
                            "run",
                            "--identifier",
                            "urn:stackpack:suse-ai:monitor:" + monitor,
                            "-o",
                            "json",
                        ]
                    )
                ),
            )
            states = result["run-result"]["checkStates"]["CheckStates"]["checkStates"]
            own = {
                s["topologyElementIdentifier"]: s
                for s in states
                if s["topologyElementIdentifier"] in expected
            }
            self.assertEqual(set(own), set(expected), result)
            for identifier, state in own.items():
                _ep, failure, latency = expected[identifier]
                value = (None, failure, latency)[index]
                self.assertEqual(
                    state["health"], "DEVIATING" if value > threshold else "CLEAR"
                )
                display = json.loads(state["data"])["displayTimeSeries"][0]
                query = display["queries"][0]["query"]
                self.assertNotIn("${", query)
                values = self.capture(
                    monitor
                    + "-"
                    + str(
                        components.index(
                            next(
                                c
                                for c in components
                                if c["identifiers"][0] == identifier
                            )
                        )
                    ),
                    self.query(query),
                )
                self.assertEqual(len(values), 1)
                self.assertAlmostEqual(float(values[0]["value"][1]), value, places=5)

    def test_ollama_and_demo_presentation_scope(self):
        name = self.prefix + "-ollama"
        resource = {
            **self.k8s,
            "service.namespace": "suse-ai-v2-demo",
            "service.name": name,
            "suse.ai.product": "ollama",
        }
        resources = [
            ({**resource, "service.instance.id": f"{name}-{i}"}, weight)
            for i, weight in enumerate((1, 3))
        ]
        # Large distractors must not enter the original service's charts.
        resources += [
            (
                {
                    **resource,
                    "service.namespace": self.prefix + "-other",
                    "service.instance.id": name + "-0",
                },
                100,
            ),
            (
                {
                    **resource,
                    "service.name": name + "-other",
                    "service.instance.id": name + "-0",
                },
                100,
            ),
        ]
        self.duration_samples(resources, [({}, 0, False)], usage=True)
        self.evaluation_time = int(time.time())
        topology_query = (
            f'label = "service.name:{name}" and label = "service.namespace:suse-ai-v2-demo" '
            'and type IN ("otel service", "otel service instance")'
        )

        def ready():
            rows = self.snapshot(topology_query)["components"]
            return rows if len(rows) == 3 else False

        rows = self.wait_for(ready, "Ollama service and replicas")
        rates = {}
        for c in rows:
            self.assertEqual(
                self.tag_values(c, "suse.ai.category"), {"inference-engine"}
            )
            charts = self.charts(c)
            self.assertTrue(
                {
                    "suse-ai-requests",
                    "suse-ai-latency",
                    "suse-ai-tokens",
                    "suse-ai-reported-cost",
                }
                <= set(charts)
            )
            self.assertNotIn("suse-ai-demo-agent-tool-call-rate", charts)
            query = charts["suse-ai-requests"]["boundQueries"][0]["expression"]
            values = self.wait_for(
                lambda query=query: self.query(query), "Ollama request chart"
            )
            self.assertEqual(len(values), 1)
            rates[next(iter(self.tag_values(c, "service.instance.id")), "service")] = (
                float(values[0]["value"][1])
            )
            for metric, expected_value in (
                ("suse-ai-latency", 9.55),
                ("suse-ai-tokens-per-request", 30),
                ("suse-ai-cost-per-request", 0.002),
            ):
                expression = charts[metric]["boundQueries"][0]["expression"]
                values = self.capture(f"{c['id']}-{metric}", self.query(expression))
                self.assertEqual(len(values), 1)
                self.assertAlmostEqual(
                    float(values[0]["value"][1]), expected_value, places=5
                )
            for metric, multiplier in (
                ("suse-ai-tokens", 30),
                ("suse-ai-reported-cost", 0.002 * 3600),
            ):
                values = self.capture(
                    f"{c['id']}-{metric}",
                    self.query(charts[metric]["boundQueries"][0]["expression"]),
                )
                rate = rates[
                    next(iter(self.tag_values(c, "service.instance.id")), "service")
                ]
                self.assertAlmostEqual(
                    sum(float(v["value"][1]) for v in values),
                    rate * multiplier,
                    places=5,
                )
        self.assertAlmostEqual(rates[name + "-1"] / rates[name + "-0"], 3, places=2)
        self.assertAlmostEqual(
            rates["service"], rates[name + "-0"] + rates[name + "-1"], places=2
        )
        self.capture("ollama-rates", rates)

        for demo in (None, "false", "true"):
            service_name = self.prefix + "-demo-" + str(demo)
            app = {
                **self.k8s,
                "service.namespace": "suse-ai-v2-demo",
                "service.name": service_name,
                "service.instance.id": service_name,
                **({"suse.ai.demo": demo} if demo is not None else {}),
            }
            # The provider name does not classify the client as Ollama.
            self.duration_samples([(app, 1)], [({}, 0, False)], tools=True)
            self.evaluation_time = int(time.time())
            self.send("traces", app, {"gen_ai.provider.name": "ollama"})
            service = self.wait_for(
                lambda service_name=service_name: self.services(service_name),
                service_name,
            )[0]
            charts = self.charts(service)
            self.assertIn("suse-ai-requests", charts)
            self.assertEqual(
                "suse-ai-demo-agent-tool-call-rate" in charts, demo == "true"
            )
            self.assertNotIn("ollama", self.tag_values(service, "suse.ai.product"))
            # Cost is optional, and these SDK clients did not emit any.
            self.assertNotIn("suse-ai-reported-cost", charts)
