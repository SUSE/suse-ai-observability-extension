"""Opt-in database discovery/composition through the installed packs and Collector.

Uses test_backend_identity's existing sts configuration and fixture. Install a
fresh test version and the current example's database normalizer first.
"""

import time
import uuid

from identity_fixture import attrs
from test_backend_identity import BackendTestCase


class BackendDatabaseDependenciesTest(BackendTestCase):
    def spans(self, resource, cases):
        now, spans, ids = time.time_ns(), [], []
        for values, kind in cases:
            trace_id = uuid.uuid4().hex
            ids.append(trace_id)
            spans.append({"traceId": trace_id, "spanId": uuid.uuid4().hex[:16],
                          "name": "database composition fixture", "kind": kind,
                          "startTimeUnixNano": str(now-100000000), "endTimeUnixNano": str(now),
                          "attributes": attrs(values)})
        self.send_payload("traces", {"resourceSpans": [{"resource": {"attributes": attrs(resource)},
                                                      "scopeSpans": [{"spans": spans}]}]})
        return ids

    def test_client_only_endpoints_have_matching_edges_and_scoped_presentations(self):
        name, namespace = self.prefix + "-db-client", self.prefix + "-db"
        caller = {**self.k8s, "service.name": name, "service.namespace": namespace}
        cases = [({"db.system": system, "net.peer.name": "database.example",
                   "net.peer.port": 19530}, 3)
                 for system in ("milvus", "qdrant", "opensearch", "elasticsearch")]
        cases += [({"db.system.name": "milvus", "server.address": "database.example"}, 3),
                  ({"db.system.name": "milvus", "server.address": "other.example", "server.port": 19530}, 3)]
        controls = [({"db.system.name": "postgresql", "server.address": "control.example"}, 3),
                    ({"db.system.name": "milvus"}, 3),
                    ({"db.system.name": "milvus", "server.address": "server-span.example"}, 2)]
        trace_ids = self.spans({**caller, "service.instance.id": "replica-1"}, cases + controls)
        repeated_id = self.spans({**caller, "service.instance.id": "replica-2"}, cases[:1])[0]
        query = f'label = "service.name:{name}" and label = "service.namespace:{namespace}"'

        def complete():
            result = self.snapshot(query)
            dependencies = [c for c in result["components"]
                            if c["typeIdentifier"].endswith(":genai database dependency")]
            return result if len(dependencies) == 6 and len(result["relations"]) >= 6 else False

        topology = self.capture("database-topology", self.wait_for(complete, "six database endpoints and edges"))
        dependencies = [c for c in topology["components"] if c["typeIdentifier"].endswith(":genai database dependency")]
        services = [c for c in topology["components"] if c["typeIdentifier"].endswith(":otel service")]
        self.assertEqual(len(services), 1)
        self.assertNotIn("stackpack:suse-ai", services[0]["tags"], "A database client is not itself an AI product")
        for dependency in dependencies:
            edges = [r for r in topology["relations"] if r["target"] == dependency["id"]]
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0]["source"], services[0]["id"])
        expected = {c["id"] for c in dependencies}
        self.wait_for(lambda: expected.issubset(self.inventory_ids("database-dependencies")),
                      "observed dependency inventory membership")
        for inventory in ("all", "data-services"):
            self.assertFalse(expected & self.inventory_ids(inventory), inventory)
        known = next(c for c in dependencies if "db.system.name:milvus" in c["tags"]
                     and "server.port:19530" in c["tags"] and "server.address:database.example" in c["tags"])
        unknown = next(c for c in dependencies if "server.port:" in c["tags"])
        for endpoint, expected_ids in ((known, {trace_ids[0], repeated_id}), (unknown, {trace_ids[4]})):
            detail = self.capture("database-detail-" + str(endpoint["id"]), self.api("/api/components/" + str(endpoint["id"])))
            span_filter = detail["boundTraces"]["filter"]
            now = int(time.time()*1000)
            def matching_traces():
                response = self.api(f"/api/traces/query?start={now-600000}&end={now}&page=0&pageSize=100",
                                    {"primarySpanFilter": span_filter, "secondarySpanFilter": {"attributes": {}}, "sortBy": []})
                return response if {trace["traceId"] for trace in response["traces"]} == expected_ids else False

            # Match actual backend output, not a translated presentation expression.
            self.capture("database-traces-" + str(endpoint["id"]), self.wait_for(matching_traces, "exact database endpoint traces"))
            metrics = self.capture("database-metrics-" + str(endpoint["id"]), self.api(
                f"/api/components/{endpoint['id']}/metricPerspectiveData?startTime={now-600000}&endTime={now}"))
            self.assertEqual(metrics["tabs"], [], "No database-server charts on an inferred endpoint")
            self.assertFalse(self.tag_values(endpoint, "cluster-name"))
            self.assertEqual(self.tag_values(endpoint, "suse.ai.observer.cluster"), {self.k8s["k8s.cluster.name"]})

    def test_resolved_database_reuses_product_service_in_both_arrival_orders(self):
        for first in ("trace", "metric"):
            namespace = self.prefix + "-resolved-" + first
            caller = {**self.k8s, "service.name": "caller", "service.namespace": namespace}
            target = {**self.k8s, "service.name": "milvus", "service.namespace": namespace,
                      "suse.ai.product": "milvus", "suse.ai.component.type": "vectordb"}
            peer = {"db.system.name": "milvus", "server.address": "verified.database.example", "server.port": 19530,
                    "suse.ai.peer.service.name": "milvus", "suse.ai.peer.service.namespace": namespace,
                    "suse.ai.peer.cluster": self.k8s["k8s.cluster.name"]}

            def metric():
                self.send_payload("metrics", {"resourceMetrics": [{"resource": {"attributes": attrs(target)},
                    "scopeMetrics": [{"metrics": [{"name": "milvus_proxy_search_vectors_count", "gauge": {
                        "dataPoints": [{"timeUnixNano": str(time.time_ns()), "asInt": "1"}]}}]}]}]})

            if first == "metric":
                metric()
                self.wait_for(lambda: self.snapshot(f'identifier = "urn:opentelemetry:namespace/{namespace}:service/milvus"')["components"],
                              "database metric contribution before client trace")
            self.spans(caller, [(peer, 3)])
            if first == "trace":
                def observed_call():
                    result = self.api("/api/metrics/query_batch", {"queries": [{
                        "id": "calls", "_type": "instant", "time": str(int(time.time())),
                        "query": f'suse_ai_service_calls{{client="caller", client_service_namespace="{namespace}", server="milvus"}}',
                    }]})
                    return result if result["results"][0]["data"]["data"]["result"] else False

                self.capture("call-before-server", self.wait_for(observed_call, "client call before database metrics"))
                self.assertEqual(self.snapshot(f'type = "genai database dependency" and label = "service.namespace:{namespace}"')["components"], [])
                metric()
            query = f'label = "service.namespace:{namespace}"'

            def complete():
                result = self.snapshot(query)
                return result if len(result["components"]) == 2 and len(result["relations"]) == 1 else False

            topology = self.capture("resolved-" + first, self.wait_for(complete, "one edge to the native database"))
            self.assertTrue(all(c["typeIdentifier"].endswith(":otel service") for c in topology["components"]))
            database = next(c for c in topology["components"] if c["name"] == "milvus")
            self.assertEqual(self.tag_values(database, "suse.ai.product"), {"milvus"})
            self.assertEqual(self.tag_values(database, "suse.ai.category"), {"vectordb"})
            ident = f"urn:opentelemetry:namespace/{namespace}:service/milvus"
            self.assertIn(ident, database["identifiers"])
            self.spans(caller, [(peer, 3)])
            metric()
            self.assertEqual(self.snapshot(query)["relations"][0]["id"], topology["relations"][0]["id"])
