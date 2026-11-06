"""Column identity contracts plus optional read-only tests of installed tables.

AI_PRESENTATION_URL, AI_PRESENTATION_TOKEN_FILE and AI_PRESENTATION_EVIDENCE
enable the backend checks. No telemetry, settings or workloads are mutated.
"""

import json
import os
import time
from pathlib import Path
import unittest
from urllib.parse import quote
from urllib.request import Request, urlopen

from test_contract import BY_ID, evaluate


PREFIX = "urn:stackpack:suse-ai:component-presentation:"
COLUMNS = {
    "all": ["suse_ai_otel_name", "suse_ai_category", "suse_ai_otel_namespace", "suse_ai_otel_k8s_cluster"],
    "inference": ["suse_ai_otel_name", "suse_ai_otel_namespace", "suse_ai_category", "suse_ai_product", "suse_ai_otel_k8s_cluster"],
    "data-services": ["suse_ai_otel_name", "suse_ai_otel_namespace", "suse_ai_product", "suse_ai_otel_k8s_cluster"],
    "applications": ["suse_ai_otel_name", "suse_ai_otel_namespace", "suse_ai_category", "suse_ai_otel_k8s_cluster"],
    "model-inventory": ["suse_ai_otel_name", "suse_ai_otel_namespace", "suse_ai_service", "suse_ai_product", "suse_ai_cluster"],
    "models": ["suse_ai_otel_name", "suse_ai_otel_namespace", "suse_ai_service"],
    "agents": ["suse_ai_otel_name", "suse_ai_otel_namespace", "suse_ai_service"],
    "database-dependencies": ["suse_ai_otel_name", "suse_ai_product", "suse_ai_observer_service", "suse_ai_otel_namespace", "suse_ai_observer_cluster"],
}


class PresentationTableContractTest(unittest.TestCase):
    def test_shared_tables_only_contain_identity_projections(self):
        for view, expected in COLUMNS.items():
            columns = BY_ID[PREFIX + view]["presentation"]["overview"]["columns"]
            self.assertEqual([c["columnId"] for c in columns], expected)
            for column in columns:
                projection = column.get("projection", {})
                self.assertNotEqual(projection.get("_type"), "MetricProjection")
                self.assertNotIn("not reported", str(column).lower())

    def test_product_pages_have_product_metrics_and_native_service_links(self):
        for product in ("vllm", "ollama", "litellm", "milvus", "qdrant", "opensearch", "mlflow", "mcpo"):
            node = BY_ID[PREFIX + "product-" + product + "-overview"]
            self.assertIn('type = "otel service"', node["binding"]["query"])
            self.assertIn('label = "suse.ai.product:' + product + '"', node["binding"]["query"])
            columns = node["presentation"]["overview"]["columns"]
            metrics = [c for c in columns if c.get("projection", {}).get("_type") == "MetricProjection"]
            self.assertGreaterEqual(len(metrics), 3, product)
            self.assertTrue(all(c["projection"]["metricId"].startswith("suse_ai_" + product + "_") for c in metrics))

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

    def test_agent_and_model_service_links_resolve(self):
        for view in ("agents", "model-inventory", "models"):
            table = self.api("/api/overview/" + quote(PREFIX + view, safe=""), {})
            for row in table["data"]:
                link = row["cells"]["suse_ai_service"]["component"]
                self.assertTrue(link["componentId"].startswith("urn:opentelemetry:namespace/"))
                detail = self.api("/api/components/" + quote(link["componentId"], safe=""))
                self.assertEqual(detail["typeName"], "otel service")

    def test_product_table_queries_resolve_to_live_service_metrics(self):
        for product in ("vllm", "ollama", "litellm", "milvus", "qdrant", "opensearch", "mlflow", "mcpo"):
            table = self.capture(product + "-table", self.api(
                "/api/overview/" + quote(PREFIX + "product-" + product + "-overview", safe=""), {}))
            for row in table["data"]:
                queries = [{"id": key, "query": cell["individualQuery"].replace("${__rate_interval}", "5m"),
                            "_type": "instant", "time": str(int(time.time()))}
                           for key, cell in row["cells"].items() if cell["_type"] == "MetricCell"]
                result = self.capture(product + "-metrics", self.api("/api/metrics/query_batch", {"queries": queries}))
                for query in result["results"]:
                    self.assertEqual(query["resultType"], "success", query)
                    self.assertTrue(query["data"]["data"]["result"], product + ": " + query["id"])

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
