"""Column identity contracts plus optional read-only tests of installed tables.

AI_PRESENTATION_URL, AI_PRESENTATION_TOKEN_FILE and AI_PRESENTATION_EVIDENCE
enable the backend checks. No telemetry, settings or workloads are mutated.
"""

import json
import os
from pathlib import Path
import unittest
from urllib.parse import quote
from urllib.request import Request, urlopen

from test_contract import BY_ID, evaluate


PREFIX = "urn:stackpack:suse-ai:component-presentation:"
COLUMNS = {
    "all": ["health", "otel_name", "suse_ai_category", "otel_namespace", "otel_k8s_cluster"],
    "inference": ["health", "otel_name", "otel_namespace", "suse_ai_category", "suse_ai_product", "otel_k8s_cluster"],
    "data-services": ["health", "otel_name", "otel_namespace", "suse_ai_product", "otel_k8s_cluster", "suse_ai_data_metrics"],
    "applications": ["health", "otel_name", "otel_namespace", "suse_ai_category", "otel_k8s_cluster"],
    "model-inventory": ["otel_name", "otel_namespace", "suse_ai_service", "suse_ai_product", "suse_ai_cluster", "suse_ai_model_metrics"],
    "models": ["health", "otel_name", "otel_namespace", "suse_ai_service", "suse_ai_usage_requests", "suse_ai_usage_latency", "suse_ai_usage_tokens"],
    "agents": ["otel_name", "otel_namespace", "suse_ai_service"],
    "database-dependencies": ["otel_name", "suse_ai_discovery", "suse_ai_product", "suse_ai_observer_service", "otel_namespace", "suse_ai_observer_cluster"],
}


class PresentationTableContractTest(unittest.TestCase):
    def test_native_metrics_links_keep_service_identity(self):
        columns = BY_ID[PREFIX + "data-services"]["presentation"]["overview"]["columns"]
        link = next(c["projection"] for c in columns if c["columnId"] == "suse_ai_data_metrics")
        for product, expected in (("milvus", "Search latency, request rate"),
                                  ("qdrant", "Collections, response rate"),
                                  ("opensearch", "Cluster health, pending tasks")):
            identifier = f"urn:opentelemetry:namespace/data:service/{product}"
            context = {"tags": {"suse.ai.product": [product]}, "identifiers": [identifier]}
            self.assertEqual(evaluate(link["name"], context), expected)
            self.assertEqual(evaluate(link["identifier"], context), identifier)

    def test_agent_host_link_preserves_namespace(self):
        columns = BY_ID[PREFIX + "agents"]["presentation"]["overview"]["columns"]
        link = next(c["projection"] for c in columns if c["columnId"] == "suse_ai_service")
        for namespace in ("one", "two"):
            context = {"tags": {"service.namespace": [namespace], "service.name": ["agent-service"]}}
            self.assertEqual(evaluate(link["identifier"], context),
                             f"urn:opentelemetry:namespace/{namespace}:service/agent-service")


@unittest.skipUnless(os.environ.get("AI_PRESENTATION_URL"), "Opt-in read-only live table checks")
class BackendPresentationTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["AI_PRESENTATION_URL"].rstrip("/")
        cls.token = Path(os.environ["AI_PRESENTATION_TOKEN_FILE"]).read_text().strip()
        cls.evidence = Path(os.environ["AI_PRESENTATION_EVIDENCE"])
        cls.evidence.mkdir(parents=True, exist_ok=True)

    def api(self, path, body=None):
        request = Request(self.url + path, None if body is None else json.dumps(body).encode(),
                          {"X-API-Key": self.token, "Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def capture(self, name, value):
        (self.evidence / (name + ".json")).write_text(json.dumps(value, indent=2))
        return value

    def test_all_eight_tables_have_only_their_intended_columns(self):
        for view, expected in COLUMNS.items():
            with self.subTest(view=view):
                table = self.capture(view, self.api("/api/overview/" + quote(PREFIX + view, safe=""), {}))
                self.assertEqual([c["columnId"] for c in table["metadata"]["columns"]], expected)
                for row in table["data"]:
                    if view in ("all", "data-services"):
                        self.assertFalse(row["componentIdentifier"].startswith("urn:suse-ai:database-dependency:"))
                    if view == "data-services":
                        self.assertEqual(row["cells"]["suse_ai_data_metrics"]["component"]["componentId"],
                                         row["componentIdentifier"])
                    if view == "database-dependencies":
                        self.assertEqual(row["cells"]["suse_ai_discovery"]["value"], "Client-observed; unresolved")

    def test_agent_and_model_service_links_resolve(self):
        for view in ("agents", "model-inventory", "models"):
            table = self.api("/api/overview/" + quote(PREFIX + view, safe=""), {})
            for row in table["data"]:
                link = row["cells"]["suse_ai_service"]["component"]
                self.assertTrue(link["componentId"].startswith("urn:opentelemetry:namespace/"))
                detail = self.api("/api/components/" + quote(link["componentId"], safe=""))
                self.assertEqual(detail["typeName"], "otel service")

    def test_native_dependency_section_uses_actual_outgoing_neighbors(self):
        caller = os.environ.get("AI_PRESENTATION_CALLER")
        if not caller:
            self.skipTest("Set AI_PRESENTATION_CALLER to verify a known resolved caller")
        detail = self.capture("caller", self.api("/api/components/" + quote(caller, safe="")))
        resources = {r["resourceId"]: r for r in detail["relatedResources"]}
        native = resources["suse_ai_data_dependencies"]
        self.assertEqual(native["presentationIdentifier"], PREFIX + "data-services")
        # Query the backend's bound section, never locally substitute the service.
        snapshot = self.capture("native-dependencies", self.api("/api/snapshot", {
            "query": native["stql"], "queryVersion": "0.0.1",
            "metadata": {"groupingEnabled": False, "showIndirectRelations": False, "minGroupSize": 0,
                         "groupedByLayer": False, "groupedByDomain": False, "groupedByRelation": False,
                         "autoGrouping": False, "connectedComponents": False, "neighboringComponents": False,
                         "showFullComponent": True},
        }))["viewSnapshotResponse"]
        self.assertTrue(snapshot["components"], "Expected a resolved native data dependency")
        for component in snapshot["components"]:
            self.assertTrue(component["typeIdentifier"].endswith(":otel service"))
        self.assertEqual(resources["suse_ai_observed_dependencies"]["presentationIdentifier"],
                         PREFIX + "database-dependencies")


if __name__ == "__main__":
    unittest.main()
