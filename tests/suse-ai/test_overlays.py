"""Protect native fields while allowing the approved shared product icons."""

import unittest

from test_contract import NODES


def identifiers(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"fieldId", "sectionId", "metricId", "resourceId", "columnId",
                       "filterId", "tabId", "summaryMetricId"}:
                yield item
            else:
                yield from identifiers(item)
    elif isinstance(value, list):
        for item in value:
            yield from identifiers(item)


class OverlayContractTest(unittest.TestCase):
    def test_presentation_ids_cannot_collide_with_native_fields(self):
        for node in NODES:
            if node["_type"] == "ComponentPresentation":
                for identifier in identifiers(node):
                    self.assertTrue(identifier.startswith("suse_ai_"), identifier)

    def test_icon_overrides_do_not_replace_native_fields_or_layout(self):
        for node in NODES:
            if node["_type"] != "ComponentPresentation":
                continue
            query = node["binding"]["query"]
            if '"otel service' not in query and not node["identifier"].endswith(":common"):
                continue
            presentation = node["presentation"]
            if ":component-presentation:icon-" in node["identifier"]:
                self.assertEqual(set(presentation), {"icon"}, node["identifier"])
                self.assertIn('label = "stackpack:suse-ai"', query)
                self.assertGreater(node["rank"]["specificity"], 10)
                continue
            self.assertLess(node["rank"]["specificity"], 2, node["identifier"])
            for key in ("icon", "name", "summary", "tracesPerspective"):
                self.assertNotIn(key, presentation, node["identifier"])
            self.assertNotIn("title", presentation.get("highlight", {}))
            if "overview" in presentation:
                self.assertNotIn("highlight", presentation)
                self.assertNotIn("metricPerspective", presentation)

    def test_native_mappings_do_not_claim_unsupported_domain_or_layer_assignment(self):
        for node in NODES:
            if node["_type"] in ("OtelComponentMapping", "OtelRelationMapping"):
                self.assertFalse({"domainName", "domainIdentifier", "layerName", "layerIdentifier"}
                                 & node["output"].keys())
