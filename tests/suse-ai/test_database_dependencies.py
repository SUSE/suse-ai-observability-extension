"""Client-observed destinations are distinct from instrumented server resources."""

import copy
import unittest

from test_contract import BY_ID, component, evaluate, mapped, record


class DatabaseDependenciesTest(unittest.TestCase):
    def observation(self, system="milvus", **attributes):
        return record(resource={"service.name": "rag", "service.namespace": "apps",
                                "service.instance.id": "replica-1", "k8s.cluster.name": "east"},
                      attributes={"db.system.name": system, "server.address": "database",
                                  "server.port": 19530, **attributes})

    def dependency(self, data):
        return component(data, "genai database dependency")

    def test_supported_databases_create_matching_components_and_relations(self):
        for system, category in (("milvus", "vectordb"), ("qdrant", "vectordb"),
                                 ("opensearch", "search-engine"), ("elasticsearch", "search-engine")):
            with self.subTest(system=system):
                data = self.observation(system)
                target = self.dependency(data)
                relations = mapped(data, "OtelRelationMapping")
                self.assertEqual(len(relations), 1)
                self.assertEqual(relations[0]["targetId"], target["identifier"])
                self.assertEqual(relations[0]["sourceId"], "urn:opentelemetry:namespace/apps:service/rag")
                self.assertEqual(target["tags"]["suse.ai.category"], category)
                self.assertEqual(target["tags"]["suse.ai.discovery"], "client-observed")
                # A database client is not itself a database/AI product resource.
                self.assertEqual([c["typeName"] for c in mapped(data)], ["genai database dependency"])
                self.assertFalse({"cluster-name", "namespace", "node-name", "pod-name"} & target["tags"].keys())

    def test_caller_namespace_cluster_endpoint_and_product_remain_separate(self):
        data = self.observation()
        original = self.dependency(data)["identifier"]
        for context, key, value in (("resource", "service.name", "other"),
                                    ("resource", "service.namespace", "other"),
                                    ("resource", "k8s.cluster.name", "west"),
                                    ("span", "server.address", "other"),
                                    ("span", "server.port", 19531),
                                    ("span", "db.system.name", "qdrant")):
            other = copy.deepcopy(data)
            other[context]["attributes"][key] = value
            self.assertNotEqual(self.dependency(other)["identifier"], original, key)
        data["resource"]["attributes"]["service.instance.id"] = "replica-2"
        self.assertEqual(self.dependency(data)["identifier"], original)
        data["span"]["attributes"]["db.collection.name"] = "another-collection"
        self.assertEqual(self.dependency(data)["identifier"], original)

    def test_missing_and_empty_namespace_and_port_have_consistent_identity(self):
        data = self.observation()
        for key in ("service.namespace", "k8s.cluster.name"):
            data["resource"]["attributes"].pop(key)
        data["span"]["attributes"].pop("server.port")
        missing = self.dependency(data)
        data["resource"]["attributes"]["service.namespace"] = ""
        data["resource"]["attributes"]["k8s.cluster.name"] = ""
        data["span"]["attributes"]["server.port"] = ""
        self.assertEqual(self.dependency(data), missing)
        self.assertEqual(missing["tags"]["service.namespace"], "default")
        self.assertNotIn("suse.ai.observer.cluster", missing["tags"])
        self.assertNotEqual(missing["identifier"], self.dependency(self.observation())["identifier"])

    def test_resolved_peers_reuse_service_calls_and_invalid_peers_keep_observation(self):
        data = self.observation(**{"suse.ai.peer.service.name": "milvus-server",
                                   "suse.ai.peer.service.namespace": "data",
                                   "suse.ai.peer.cluster": "east"})
        self.assertEqual(mapped(data), [])
        self.assertEqual(mapped(data, "OtelRelationMapping"), [])
        for key, value in (("suse.ai.peer.cluster", "west"),
                           ("suse.ai.peer.service.namespace", ""),
                           ("suse.ai.peer.service.name", "")):
            other = copy.deepcopy(data)
            other["span"]["attributes"][key] = value
            self.assertEqual(mapped(other, "OtelRelationMapping")[0]["targetId"],
                             self.dependency(other)["identifier"])

    def test_controls_and_incomplete_observations_do_not_create_destinations(self):
        for changes in ({"db.system.name": "postgresql"}, {"db.system.name": ""},
                        {"server.address": ""}):
            data = self.observation(**changes)
            self.assertEqual(mapped(data), [])
            self.assertEqual(mapped(data, "OtelRelationMapping"), [])
        for key in ("db.system.name", "server.address"):
            data = self.observation()
            data["span"]["attributes"].pop(key)
            self.assertEqual(mapped(data), [])
        for kind in ("Server", "Internal", "Producer", "Consumer"):
            data = self.observation()
            data["span"]["kind"] = kind
            self.assertEqual(mapped(data), [])
        for value in (False, "false"):
            data = self.observation()
            data["resource"]["attributes"]["suse.ai.managed"] = value
            self.assertEqual(mapped(data), [])
            self.assertEqual(mapped(data, "OtelRelationMapping"), [])
        self.assertEqual(mapped(record(attributes={"http.request.method": "GET"})), [])

    def test_component_and_relation_selection_cannot_drift(self):
        component_map = BY_ID["urn:stackpack:suse-ai:otel-component-mapping:database-dependencies"]
        relation_map = BY_ID["urn:stackpack:suse-ai:otel-relation-mapping:service-database"]
        self.assertEqual(component_map["input"], relation_map["input"])
        self.assertEqual(component_map["vars"], relation_map["vars"])
        self.assertEqual(component_map["output"]["identifier"], relation_map["output"]["targetId"])

    def test_observed_presentation_does_not_claim_server_metrics_or_health(self):
        presentation = BY_ID["urn:stackpack:suse-ai:component-presentation:database-dependencies"]["presentation"]
        target = self.dependency(self.observation())
        tags = {k: [v] for k, v in target["tags"].items()}
        fields = presentation["highlight"]["fields"]
        for field in fields:
            projection = field["projection"]
            self.assertIn(projection["_type"], ("TextProjection", "ComponentLinkProjection"))
            for key in ("value", "name", "identifier"):
                if key in projection:
                    self.assertTrue(evaluate(projection[key], {"tags": tags}))
        self.assertEqual(presentation["tracesPerspective"]["spanFilter"]["attributes"]["server.port"],
                         ["${tags.singleValue('server.port')}"])
        columns = {c["columnId"]: c for c in presentation["overview"]["columns"]}
        self.assertNotIn("suse_ai_health", columns)
        self.assertNotIn("suse_ai_otel_k8s_cluster", columns)
        self.assertFalse(any(c.get("projection", {}).get("_type") == "MetricProjection" for c in columns.values()))
        self.assertNotIn("mainMenu", presentation["overview"])
        self.assertEqual(presentation["overview"]["name"]["title"], "Unresolved calls")
        caller = columns["suse_ai_observer_service"]["projection"]
        self.assertEqual(evaluate(caller["name"], {"tags": tags}), "rag")
        self.assertEqual(evaluate(caller["identifier"], {"tags": tags}),
                         "urn:opentelemetry:namespace/apps:service/rag")
        cluster = columns["suse_ai_observer_cluster"]["projection"]["value"]
        self.assertEqual(evaluate(cluster, {"tags": tags}), "east")
        self.assertEqual(evaluate(cluster, {"tags": {}}), "")


if __name__ == "__main__":
    unittest.main()
