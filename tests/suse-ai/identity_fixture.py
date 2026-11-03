"""Shared OTLP contract cases, also exercised by the product Collector tests.

The harness supplies send(), signal_resources(), and wait_for() against a real
Collector. This fixture never simulates OTTL or backend composition.
"""

import itertools
import time


def attrs(values):
    def value(v):
        if isinstance(v, bool):
            return {"boolValue": v}
        if isinstance(v, int):
            return {"intValue": str(v)}
        if isinstance(v, float):
            return {"doubleValue": v}
        return {"stringValue": v}

    return [{"key": k, "value": value(v)} for k, v in values.items()]


def unpack(values):
    return {a["key"]: next(iter(a["value"].values())) for a in values}


class IdentityCases:
    def test_namespace_normalization_precedes_connectors(self):
        cases = [
            ({}, "default"),
            ({"service.namespace": ""}, "default"),
            ({"service.namespace": "team-a"}, "team-a"),
            ({"service.namespace": "team-b"}, "team-b"),
            (
                {"service.namespace": "team-a", "service.name": "identity-other"},
                "team-a",
            ),
            ({"k8s.namespace.name": "actual-namespace"}, "actual-namespace"),
            (
                {"service.namespace": "", "k8s.namespace.name": "actual-namespace"},
                "actual-namespace",
            ),
            (
                {
                    "service.namespace": "supplied",
                    "k8s.namespace.name": "actual-namespace",
                },
                "supplied",
            ),
            ({"service.namespace": "", "k8s.namespace.name": ""}, "default"),
        ]
        traces, metrics, expected = [], [], {}
        now = time.time_ns()
        for i, (extra, namespace) in enumerate(cases):
            # Cases 2/3 keep name and instance identical across namespaces.
            instance = "shared-replica" if i in (2, 3) else f"identity-{i}"
            resource = {
                "service.name": "identity-client",
                "service.instance.id": instance,
                "suse.ai.product": "",
                **extra,
            }
            expected[(resource["service.name"], namespace, instance)] = resource
            trace_id = f"{0xCA00 + i:032x}"
            client_id = f"{2 * i + 1:016x}"
            for server in (False, True):
                r = (
                    {
                        "service.name": "identity-server",
                        "service.namespace": namespace + "-backend",
                        "service.instance.id": f"server-{i}",
                    }
                    if server
                    else resource
                )
                span = {
                    "name": f"identity-{i}",
                    "traceId": trace_id,
                    "spanId": f"{2 * i + 2:016x}" if server else client_id,
                    "kind": 2 if server else 3,
                    "startTimeUnixNano": str(now),
                    "endTimeUnixNano": str(now + 100000000),
                    "attributes": attrs({"gen_ai.provider.name": "vllm"}),
                }
                if server:
                    span["parentSpanId"] = client_id
                traces.append(
                    {
                        "resource": {"attributes": attrs(r)},
                        "scopeSpans": [{"spans": [span]}],
                    }
                )
            metrics.append(
                {
                    "resource": {"attributes": attrs(resource)},
                    "scopeMetrics": [
                        {
                            "metrics": [
                                {
                                    "name": "gen_ai.identity.fixture",
                                    "gauge": {
                                        "dataPoints": [
                                            {
                                                "timeUnixNano": str(now),
                                                "asInt": "7",
                                                "attributes": attrs(
                                                    {"service_namespace": ""}
                                                ),
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    ],
                }
            )
        self.send("traces", {"resourceSpans": traces})
        self.send("metrics", {"resourceMetrics": metrics})

        def metric_points():
            return [
                (unpack(r.get("resource", {}).get("attributes", [])), m["name"], p)
                for r in self.signal_resources("metrics", "resourceMetrics")
                for s in r["scopeMetrics"]
                for m in s["metrics"]
                for payload in ("gauge", "sum", "histogram")
                for p in m.get(payload, {}).get("dataPoints", [])
            ]

        self.wait_for(
            lambda: (
                len(
                    [p for _, n, p in metric_points() if n == "gen_ai.identity.fixture"]
                )
                == len(cases)
            ),
            "normalized OTLP metrics",
        )
        self.wait_for(
            lambda: any(
                n == "suse.ai.service.calls"
                and unpack(p.get("attributes", [])).get("client") == "identity-client"
                for _, n, p in metric_points()
            ),
            "normalized service graph",
        )
        self.wait_for(
            lambda: (
                len(
                    [
                        r
                        for r in self.signal_resources("traces", "resourceSpans")
                        if unpack(r["resource"]["attributes"]).get("service.name")
                        in ("identity-client", "identity-other")
                    ]
                )
                >= len(cases)
            ),
            "normalized traces",
        )
        for signal, root in (
            ("traces", "resourceSpans"),
            ("metrics", "resourceMetrics"),
        ):
            seen = set()
            for row in self.signal_resources(signal, root):
                values = unpack(row.get("resource", {}).get("attributes", []))
                if values.get("service.name") not in (
                    "identity-client",
                    "identity-other",
                ):
                    continue
                key = tuple(
                    values.get(k)
                    for k in (
                        "service.name",
                        "service.namespace",
                        "service.instance.id",
                    )
                )
                self.assertIn(key, expected)
                seen.add(key)
                self.assertNotIn("suse.ai.product", values)
                self.assertNotIn("suse.ai.component.type", values)
                self.assertNotIn("suse.ai.category", values)
                original = expected[key]
                for k in (
                    "k8s.cluster.name",
                    "k8s.namespace.name",
                    "k8s.pod.uid",
                    "k8s.node.name",
                ):
                    if k not in original:
                        self.assertNotIn(k, values)
            self.assertEqual(seen, set(expected))
        spans, calls = set(), set()
        for resource, name, point in metric_points():
            dimensions = unpack(point.get("attributes", []))
            if name == "gen_ai.identity.fixture":
                self.assertEqual(
                    dimensions["service_namespace"], resource["service.namespace"]
                )
                self.assertEqual(int(point["asInt"]), 7)
            if name.startswith("otel_span.") and dimensions.get("service.name") in (
                "identity-client",
                "identity-other",
            ):
                spans.add(
                    tuple(
                        dimensions[k]
                        for k in (
                            "service.name",
                            "service.namespace",
                            "service.instance.id",
                        )
                    )
                )
            if name == "suse.ai.service.calls" and dimensions.get("client") in (
                "identity-client",
                "identity-other",
            ):
                calls.add(
                    (
                        dimensions["client_service.namespace"],
                        dimensions["server_service.namespace"],
                    )
                )
        self.assertEqual(spans, set(expected))
        self.assertEqual(
            calls, {(namespace, namespace + "-backend") for _, namespace in cases}
        )

    def test_nonempty_agent_name_compatibility(self):
        cases = list(
            itertools.product(
                (None, "", "canonical"), (None, "", "legacy"), ("agent", "task")
            )
        )
        spans, expected = [], {}
        now = time.time_ns()
        for i, (canonical, legacy, kind) in enumerate(cases):
            values = {
                k: v
                for k, v in {
                    "gen_ai.agent.name": canonical,
                    "traceloop.entity.name": legacy,
                    "traceloop.span.kind": kind,
                }.items()
                if v is not None
            }
            name = f"agent-case-{i}"
            expected[name] = canonical or (
                legacy if kind == "agent" and legacy else canonical
            )
            spans.append(
                {
                    "name": name,
                    "traceId": f"{0xCB00 + i:032x}",
                    "spanId": f"{i + 1:016x}",
                    "kind": 1,
                    "startTimeUnixNano": str(now),
                    "endTimeUnixNano": str(now + 1000000),
                    "attributes": attrs(values),
                }
            )
        self.send(
            "traces",
            {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": attrs({"service.name": "identity-agents"})
                        },
                        "scopeSpans": [{"spans": spans}],
                    }
                ]
            },
        )

        def output():
            return {
                s["name"]: unpack(s.get("attributes", [])).get("gen_ai.agent.name")
                for r in self.signal_resources("traces", "resourceSpans")
                for scope in r["scopeSpans"]
                for s in scope["spans"]
                if s["name"] in expected
            }

        self.wait_for(lambda: len(output()) == len(expected), "agent name matrix")
        self.assertEqual(output(), expected)

    def test_database_endpoint_compatibility(self):
        cases = [
            ({"db.system": "milvus", "net.peer.name": "db.local", "net.peer.port": 19530},
             ("milvus", "db.local", "19530")),
            ({"db.system.name": "", "db.system": "qdrant", "server.address": "",
              "net.peer.name": "db.local", "net.peer.ip": "192.0.2.1", "server.port": "", "net.peer.port": 6333},
             ("qdrant", "db.local", "6333")),
            ({"db.system.name": "opensearch", "db.system": "milvus", "server.address": "canonical",
              "net.peer.name": "legacy", "server.port": 443, "net.peer.port": 9200},
             ("opensearch", "canonical", "443")),
            ({"db.system": "elasticsearch", "net.peer.ip": "2001:db8::1"},
             ("elasticsearch", "2001:db8::1", None)),
            ({"db.system": "milvus"}, ("milvus", None, None)),
            ({"db.system": "", "net.peer.name": "not-a-database"}, (None, None, None)),
            ({"http.request.method": "GET", "net.peer.name": "web"}, (None, None, None)),
        ]
        now, spans, expected = time.time_ns(), [], {}
        for i, (values, result) in enumerate(cases):
            name = "database-case-" + str(i)
            expected[name] = result
            spans.append({"name": name, "traceId": f"{0xDC00+i:032x}", "spanId": f"{i+1:016x}",
                          "kind": 3, "startTimeUnixNano": str(now), "endTimeUnixNano": str(now+1000000),
                          "attributes": attrs(values)})
        self.send("traces", {"resourceSpans": [{
            "resource": {"attributes": attrs({"service.name": "identity-database-client"})},
            "scopeSpans": [{"spans": spans}]}]})

        def resources():
            return [r for r in self.signal_resources("traces", "resourceSpans")
                    if unpack(r.get("resource", {}).get("attributes", [])).get("service.name")
                    == "identity-database-client"]

        def output():
            return {s["name"]: tuple(unpack(s.get("attributes", [])).get(k)
                                    for k in ("db.system.name", "server.address", "server.port"))
                    for r in resources() for scope in r["scopeSpans"] for s in scope["spans"]}

        self.wait_for(lambda: len(output()) == len(expected), "database endpoint matrix")
        self.assertEqual(output(), expected)
        for resource in resources():
            attributes = unpack(resource["resource"]["attributes"])
            self.assertEqual(attributes["service.namespace"], "default")
            self.assertFalse({"suse.ai.product", "suse.ai.component.type", "k8s.cluster.name",
                              "k8s.namespace.name", "db.system.name", "db.system"} & attributes.keys())
