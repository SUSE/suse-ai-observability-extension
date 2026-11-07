"""Available-model mapping, presentation identity and real Prometheus regressions."""

import importlib.util
import json
import promql_parser as promql
import re2
import os
import re
import unittest

from test_contract import BY_ID, ROOT, component, evaluate, mapped, record, render_topological_monitor, walk
from test_product_metrics import samples
from test_promql import run_promql_cases
from test_runtime_observations import runtime_series


PREFIX = "urn:stackpack:suse-ai:"
MAPPING = BY_ID[PREFIX + "otel-component-mapping:ollama-models"]
RELATION = BY_ID[PREFIX + "otel-relation-mapping:ollama-model-host"]


def observation(model="gemma:2b", **resource):
    return record("METRICS", resource={
        "service.name": "ollama", "service.namespace": "ai",
        "service.instance.id": "pod-a", "k8s.cluster.name": "cluster-a",
        "suse.ai.product": "ollama",
        **resource,
    }, metric="ollama_model_info", attributes={"model": model})


class OllamaModelContractTest(unittest.TestCase):
    def test_identity_colons_replica_changes_and_service_relation(self):
        for name in ("gemma:2b", "llama3.2:latest", "library/nomic-embed-text:latest"):
            data = observation(name)
            model = component(data, "genai served model")
            self.assertEqual(model["identifier"],
                             "urn:suse-ai:cluster/cluster-a:namespace/ai:service/ollama:served-model/" + name)
            self.assertEqual(model["name"], name)
            self.assertTrue(model["tags"].pop("suse.ai.monitor.k8s_cluster_name"))
            self.assertEqual(model["tags"], {
                "stackpack": "suse-ai", "service.name": "ollama", "service.namespace": "ai",
                "suse.ai.metric.service_name": "ollama", "suse.ai.metric.service_namespace": "ai",
                "suse.ai.metric.k8s_cluster_name": "cluster-a", "suse.ai.product": "ollama",
                "ollama.model.name": name,
            })
            edge = mapped(data, "OtelRelationMapping")
            self.assertEqual(len(edge), 1)
            self.assertEqual(edge[0]["sourceId"], component(data, "otel service")["identifier"])
            self.assertEqual(edge[0]["targetId"], model["identifier"])
            self.assertEqual(edge[0]["typeName"], "serves-model")
            self.assertEqual(edge[0]["dependencyType"], "HIERARCHICAL")
            data["resource"]["attributes"]["service.instance.id"] = "pod-replacement"
            data["datapoint"]["attributes"].update(family="changed", quantization="Q8_0")
            self.assertEqual(component(data, "genai served model")["identifier"], model["identifier"])

    def test_cluster_namespace_service_and_model_separate_inventory(self):
        base = component(observation(), "genai served model")["identifier"]
        for key in ("k8s.cluster.name", "service.namespace", "service.name"):
            self.assertNotEqual(base, component(observation(**{key: "other"}), "genai served model")["identifier"])
        data = observation()
        del data["resource"]["attributes"]["k8s.cluster.name"]
        del data["resource"]["attributes"]["service.namespace"]
        model = component(data, "genai served model")
        self.assertEqual(model["identifier"], "urn:suse-ai:namespace/default:service/ollama:served-model/gemma:2b")
        self.assertEqual(model["tags"]["suse.ai.metric.k8s_cluster_name"], "")
        data["resource"]["attributes"]["k8s.cluster.name"] = ""
        self.assertEqual(component(data, "genai served model")["identifier"], model["identifier"])

    def test_monitor_cluster_scope_matches_literal_and_absent_clusters(self):
        query = BY_ID[PREFIX + "monitor:ollama-model-unavailable"]["arguments"]["queries"]["promqlQuery"]
        for cluster in (None, "", "cluster-a", "cluster.+[1]", 'a"$\\E.b'):
            data = observation()
            if cluster is None:
                del data["resource"]["attributes"]["k8s.cluster.name"]
            else:
                data["resource"]["attributes"]["k8s.cluster.name"] = cluster
            tags = component(data, "genai served model")["tags"]
            self.assertTrue(tags["suse.ai.monitor.k8s_cluster_name"])
            tree = promql.parse(render_topological_monitor(query, monitor_tags=tags))
            for selector in walk(tree):
                if not isinstance(selector, promql.VectorSelector):
                    continue
                matcher = next(m for m in selector.matchers.matchers if m.name == "k8s_cluster_name")
                pattern = json.loads('"' + matcher.value + '"')
                self.assertIsNotNone(re2.fullmatch(pattern, cluster or ""))
                for other in ("", "clusterX+[1]", "other", (cluster or "") + "x"):
                    if other != (cluster or ""):
                        self.assertIsNone(re2.fullmatch(pattern, other))

    def test_only_available_inventory_creates_models_and_managed_optout_applies(self):
        for metric in ("ollama_model_loaded", "ollama_model_size_bytes", "ollama_model_vram_bytes",
                       "ollama_model_context_length", "ollama_api_up", "gen_ai.client.operation.duration"):
            data = observation()
            data["metric"]["name"] = metric
            self.assertFalse(any(m["typeName"] == "genai served model" for m in mapped(data)))
        for changes in ({"suse.ai.managed": False}, {"suse.ai.managed": "false"}, {"service.name": ""}):
            data = observation(**changes)
            self.assertFalse(any(m["typeName"] == "genai served model" for m in mapped(data)))
            self.assertEqual(mapped(data, "OtelRelationMapping"), [])
        data = observation("")
        self.assertFalse(any(m["typeName"] == "genai served model" for m in mapped(data)))

    def test_idle_inventory_refreshes_identity_beyond_expiry_and_deletion_stops_refresh(self):
        spec = importlib.util.spec_from_file_location("ollama_inventory_exporter", ROOT / "integrations/ollama/ollama_metrics.py")
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        tags = {"models": [{"name": "gemma:2b", "size": 42}]}
        ttl = MAPPING["expireAfter"]
        self.assertEqual(ttl, 900000)
        self.assertEqual(RELATION["expireAfter"], ttl)
        identities = set()
        # Feed the actual exporter's output through the actual shipped CEL at
        # 30-second scrape intervals, past both keep_alive and topology expiry.
        for elapsed in range(0, ttl * 2, 30000):
            loaded = tags if elapsed < 300000 else {"models": []}
            lines = exporter.render(loaded, tags)
            info = [line for line in lines if line.startswith("ollama_model_info{")]
            self.assertEqual(len(info), 1)
            self.assertIn('model="gemma:2b"', info[0])
            data = observation()
            identities.add(component(data, "genai served model")["identifier"])
            self.assertEqual(mapped(data, "OtelRelationMapping")[0]["targetId"], next(iter(identities)))
            if elapsed >= 300000:
                self.assertIn('ollama_model_loaded{model="gemma:2b"} 0', lines)
        self.assertEqual(len(identities), 1)
        self.assertFalse(any(line.startswith("ollama_model_info{") for line in
                             exporter.render({"models": []}, {"models": []})))

    def test_neutral_presentations_link_real_service_with_identity_only(self):
        for suffix in ("model-inventory", "served-models"):
            node = BY_ID[PREFIX + "component-presentation:" + suffix]
            columns = {c["columnId"]: c["projection"] for c in node["presentation"]["overview"]["columns"]}
            for product in ("ollama", "vllm"):
                context = {"tags": {"service.namespace": ["ai"], "service.name": [product],
                                    "suse.ai.product": [product], "cluster-name": ["cluster-a"]}}
                link = columns["suse_ai_service"]
                self.assertEqual(link["_type"], "ComponentLinkProjection")
                self.assertEqual(evaluate(link["identifier"], context), f"urn:opentelemetry:namespace/ai:service/{product}")
                self.assertEqual(evaluate(columns["suse_ai_product"]["value"], context), product)
                self.assertEqual(evaluate(columns["suse_ai_cluster"]["value"], context), "cluster-a")
            self.assertNotIn("suse_ai_model_metrics", columns)
            self.assertFalse(any(p["_type"] == "MetricProjection" for p in columns.values()))
        ollama = BY_ID[PREFIX + "component-presentation:served-models-ollama"]
        self.assertIn('label = "suse.ai.product:ollama"', ollama["binding"]["query"])
        self.assertNotIn("gen_ai_client", str(ollama))
        self.assertEqual(len(ollama["metrics"]), 5)


def model_chart(key, value, time="5m"):
    return {"presentation": "served-models-ollama", "metric": "suse_ai_ollama_served_model_" + key.replace("-", "_"),
            "samples": [] if value is None else samples(value), "eval_time": time}


@unittest.skipUnless(os.environ.get("AI_PROMETHEUS_IMAGE"), "Set AI_PROMETHEUS_IMAGE for Prometheus")
class OllamaModelPromQLTest(unittest.TestCase):
    def test_model_scope_idle_failure_deletion_and_duplicate_scrapers(self):
        metrics = {"loaded": "model_loaded", "vram": "model_vram_bytes", "disk-size": "model_disk_size_bytes",
                   "size": "model_size_bytes", "context": "model_context_length"}
        data = []
        for pod, vram in (("a", 30), ("b", 50)):
            for scraper in ("one", "two"):
                labels = {"service_instance_id": pod, "job": scraper}
                data.append(runtime_series("api_up", **labels))
                for key, value in (("loaded", 1), ("vram", vram), ("disk-size", 42), ("size", 100), ("context", 4096)):
                    data.append(runtime_series(metrics[key], f"{value}+0x20", model="gemma:2b", **labels))
        foreign = []
        for changed in ({"service_name": "other"}, {"service_namespace": "other"},
                        {"k8s_cluster_name": "other"}, {"model": "other"}):
            # Override the fixture defaults without adding duplicate matchers.
            rows = [runtime_series("api_up")] + [runtime_series(m, "999999+0x20", model="gemma:2b") for m in metrics.values()]
            for row in rows:
                for key, value in changed.items():
                    row["series"] = re.sub(key + r'="[^"]*"', key + '="' + value + '"', row["series"])
                foreign.append(row)
        cases = [{"name": "Exact model service cluster and replica deduplication", "series": data + foreign,
                  "checks": [model_chart(k, v) for k, v in (("loaded", 1), ("vram", 80), ("disk-size", 42), ("size", 200), ("context", 4096))]}]
        # Successful unload at minute 1, failed API at minute 2, then recovery
        # with the model deleted. Old metric samples remain in lookback.
        rows = [runtime_series("api_up", "1 1 0 1")]
        for key in metrics:
            values = {"loaded": "1 0 _ _", "vram": "30 0 _ _", "disk-size": "42 42 _ _",
                      "size": "100 _ _ _", "context": "4096 _ _ _"}[key]
            rows.append(runtime_series(metrics[key], values, model="gemma:2b"))
        checks = [model_chart(k, v, "1m") for k, v in (("loaded", 0), ("vram", 0), ("disk-size", 42), ("size", None), ("context", None))]
        checks += [model_chart(k, None, t) for k in metrics for t in ("2m", "3m", "9m")]
        cases.append({"name": "Unload failure deletion and expiry never revive old model metrics", "series": rows, "checks": checks})
        cases.append({"name": "Absent telemetry stays missing", "series": [], "checks": [model_chart(k, None) for k in metrics]})
        # Current-value fields must retain the same unload, failure and scope
        # semantics as their history charts. Loaded replicas counts both hosts.
        for case in cases:
            for check in list(case["checks"]):
                key = check["metric"].removeprefix("suse_ai_ollama_served_model_")
                if key not in ("loaded", "vram", "disk_size"):
                    continue
                field_check = {k: v for k, v in check.items() if k != "metric"}
                field_check["field"] = "suse_ai_ollama_current_" + key
                if key == "loaded" and case["name"].startswith("Exact model"):
                    field_check["samples"] = samples(2)
                elif key != "loaded" and check["samples"]:
                    field_check["samples"] = samples(round(check["samples"][0]["value"] / 1073741824, 2))
                case["checks"].append(field_check)
        cases.append({"name": "Current memory fields expose GiB rather than raw bytes", "series": [
            runtime_series("api_up", service_instance_id="a"),
            runtime_series("api_up", service_instance_id="b"),
            runtime_series("model_vram_bytes", "2147483648+0x20", model="gemma:2b", service_instance_id="a"),
            runtime_series("model_vram_bytes", "3221225472+0x20", model="gemma:2b", service_instance_id="b"),
            runtime_series("model_disk_size_bytes", "4294967296+0x20", model="gemma:2b", service_instance_id="a"),
        ], "checks": [
            {"presentation": "served-models-ollama", "field": "suse_ai_ollama_current_vram", "samples": samples(5)},
            {"presentation": "served-models-ollama", "field": "suse_ai_ollama_current_disk_size", "samples": samples(4)},
        ]})
        result = run_promql_cases(cases)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
