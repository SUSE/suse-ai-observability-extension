"""Opt-in composition of resolved-client and paired service observations.

Requires the current example Collector (including count/suse_ai_clients) in the
identity fixture. Uses the same explicit opt-in and existing sts configuration
as test_backend_identity. Independent CEL equality cannot prove relation merging.
"""

import time
import uuid

from identity_fixture import attrs
from test_backend_identity import BackendTestCase


class BackendRelationsTest(BackendTestCase):
    def test_resolved_and_paired_calls_share_one_backend_relation(self):
        namespace = self.prefix + "-relations"
        client_name, server_name = self.prefix + "-client", self.prefix + "-server"
        client = {**self.k8s, "service.namespace": namespace, "service.name": client_name}
        server = {**self.k8s, "service.namespace": namespace, "service.name": server_name}
        # Keep components independently discoverable; only calls create edges.
        self.send("metrics", client)
        self.send("metrics", server)
        peer = {
            "server.address": "explicit-target.fixture.svc.cluster.local",
            "suse.ai.peer.service.name": server_name,
            "suse.ai.peer.service.namespace": namespace,
            "suse.ai.peer.cluster": self.k8s["k8s.cluster.name"],
        }
        query = f'type = "otel service" and label = "service.namespace:{namespace}"'

        def edges():
            return self.snapshot(query)["relations"]

        self.send("traces", client, peer)
        first = self.capture("resolved-client-edge", self.wait_for(edges, "client-only edge"))
        self.assertEqual(len(first), 1)
        now, trace_id, span_id = time.time_ns(), uuid.uuid4().hex, uuid.uuid4().hex[:16]
        client_span = {
            "traceId": trace_id, "spanId": span_id, "name": "provider call", "kind": 3,
            "startTimeUnixNano": str(now - 100000000), "endTimeUnixNano": str(now),
            "attributes": attrs(peer),
        }
        server_span = {
            **client_span, "spanId": uuid.uuid4().hex[:16], "parentSpanId": span_id,
            "name": "fixture SERVER", "kind": 2, "attributes": [],
        }
        self.send_payload("traces", {"resourceSpans": [
            {"resource": {"attributes": attrs(resource)}, "scopeSpans": [{"spans": [span]}]}
            for resource, span in ((client, client_span), (server, server_span))
        ]})

        def both_sources():
            result = self.api("/api/metrics/query_batch", {"queries": [{
                "id": "observations", "_type": "instant", "time": str(int(time.time())),
                "query": f'suse_ai_service_calls{{client="{client_name}"}}',
            }]})["results"][0]["data"]["data"]["result"]
            scopes = {r["metric"].get("otel_scope_name") for r in result}
            return result if {
                "traces_service_graph",
                "github.com/open-telemetry/opentelemetry-collector-contrib/connector/countconnector",
            }.issubset(scopes) else False

        self.capture("paired-and-client-metrics", self.wait_for(both_sources, "both observation sources"))
        final = self.capture("composed-edge", edges())
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["id"], first[0]["id"])
