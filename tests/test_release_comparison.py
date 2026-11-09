"""A release comparison must not take ownership of live component identities."""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "release_comparison", Path(__file__).resolve().parents[1] / "scripts/build-release-comparison.py")
COMPARISON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARISON)


class ReleaseComparisonTest(unittest.TestCase):
    def test_canonical_ids_and_aliases_are_isolated_but_metric_dimensions_are_preserved(self):
        mapping = {"_type": "OtelComponentMapping",
                   "identifier": "urn:stackpack:open-telemetry:otel-component-mapping:pod",
                   "output": {"identifier": "'urn:opentelemetry:kubernetes:/' + vars.cluster + ':pod/' + vars.pod",
                              "typeName": "'pod'", "required": {"additionalIdentifiers": [
                                  "'urn:kubernetes:/' + vars.cluster + ':pod/' + vars.pod"], "tags": [
                                      {"source": "'open-telemetry'", "target": "stackpack"},
                                      {"source": "resource.attributes['k8s.cluster.name']", "target": "cluster-name"}]}}}
        isolated = COMPARISON.isolate_node(mapping, companion=True)
        self.assertEqual(isolated["identifier"], "urn:stackpack:suse-ai-v300:otel-component-mapping:companion-pod")
        output = isolated["output"]
        self.assertIn("urn:suse-ai-v300:otel:kubernetes:/", output["identifier"])
        self.assertIn("urn:suse-ai-v300:kubernetes:/", output["required"]["additionalIdentifiers"][0])
        self.assertEqual(output["typeName"], "'v3.0 release pod'")
        self.assertEqual(output["required"]["tags"][1], mapping["output"]["required"]["tags"][1])
        self.assertIn("urn:opentelemetry:", mapping["output"]["identifier"])

    def test_baseline_monitors_keep_real_queries_and_shared_monitor_functions(self):
        monitor = {"_type": "Monitor", "name": "Request errors",
                   "identifier": "urn:stackpack:suse-ai:monitor:errors",
                   "function": "urn:stackpack:common:monitor-function:threshold",
                   "arguments": {"urnTemplate": "urn:opentelemetry:namespace/${service_namespace}:service/${service_name}",
                                 "metric": {"query": 'rate(otel_span_calls_total{service_name="${tags.service.name}"}[5m])'},
                                 "threshold": 0.05}}
        isolated = COMPARISON.isolate_node(monitor)
        self.assertEqual(isolated["function"], monitor["function"])
        self.assertEqual(isolated["arguments"]["metric"], monitor["arguments"]["metric"])
        self.assertEqual(isolated["arguments"]["threshold"], monitor["arguments"]["threshold"])
        self.assertEqual(isolated["arguments"]["urnTemplate"],
                         "urn:suse-ai-v300:otel:namespace/${service_namespace}:service/${service_name}")

    def test_comparison_menu_and_shared_resource_links_do_not_change_the_primary_menu(self):
        node = {"_type": "ComponentPresentation", "identifier": "urn:stackpack:suse-ai:component-presentation:all",
                "binding": {"query": 'label = "stackpack:suse-ai" and type = "otel service"'},
                "presentation": {"overview": {"mainMenu": {"group": "SUSE AI"}},
                                 "icon": COMPARISON.Asset("products/ollama.svg", "!icon")}}
        isolated = COMPARISON.isolate_node(node)
        self.assertEqual(isolated["presentation"]["overview"]["mainMenu"]["group"], "SUSE AI 3.0 release")
        self.assertEqual(isolated["binding"]["query"],
                         'label = "stackpack:suse-ai-v300" and type = "v3.0 release otel service"')
        self.assertEqual(isolated["presentation"]["icon"].tag, "!icon")
        namespace_link = "'urn:kubernetes:/' + vars.cluster + ':namespace/' + vars.namespace"
        self.assertEqual(COMPARISON.rewrite_text(namespace_link), namespace_link)


if __name__ == "__main__":
    unittest.main()
