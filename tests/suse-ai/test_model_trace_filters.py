"""Model usage trace filters must not hide spans without endpoint attributes.

The endpoint fields stay in the usage identifier and required tags. Trace-only
``suse.ai.trace.*`` tags exist only when the endpoint is reported, so the
resolved span filter narrows on what is present instead of emitting an empty
matcher for an absent attribute.
"""

import re
import unittest

from test_contract import BY_ID, evaluate, mapped, record


MODELS_TRACES = "urn:stackpack:suse-ai:otel-component-mapping:models-traces"
MODELS_METRICS = "urn:stackpack:suse-ai:otel-component-mapping:models-metrics"
MODELS_PRESENTATION = "urn:stackpack:suse-ai:component-presentation:models"
MODEL_METRICS_PRESENTATION = "urn:stackpack:suse-ai:component-presentation:model-metrics"
BINDING = re.compile(r"^\$\{(.+)\}$")


def optional_tags(mapping_id, data):
    node = BY_ID[mapping_id]
    variables = {
        item["name"]: evaluate(item["value"], data) for item in node.get("vars", [])
    }
    context = {**data, "vars": variables}
    tags = {}
    for item in node["output"].get("optional", {}).get("tags", []):
        value = evaluate(item["source"], context)
        if "pattern" in item:
            for key, tag_value in value.items():
                match = re.fullmatch(item["pattern"], str(key))
                if match:
                    target = item["target"]
                    for index, group in enumerate(match.groups(), 1):
                        target = target.replace("${" + str(index) + "}", group)
                    tags[target] = str(tag_value)
        else:
            tags[item["target"]] = str(value)
    return tags


def model_usage(data, mapping_id):
    matches = [item for item in mapped(data) if item["typeName"] == "genai model usage"]
    if len(matches) != 1:
        raise AssertionError(f"Expected one genai model usage: {matches}")
    component = matches[0]
    component["tags"].update(optional_tags(mapping_id, data))
    return component


def resolved_trace_attributes(tags):
    presentation = BY_ID[MODELS_PRESENTATION]["presentation"]
    context = {"tags": {key: [value] for key, value in tags.items()}}
    attributes = {}
    for key, expressions in presentation["tracesPerspective"]["spanFilter"]["attributes"].items():
        if key.startswith("__multi__"):
            for expression in expressions:
                values = evaluate(BINDING.fullmatch(expression).group(1), context)
                for attribute, value in values.items():
                    attributes.setdefault(str(attribute), []).append(str(value))
        else:
            attributes[key] = [
                str(evaluate(BINDING.fullmatch(expression).group(1), context))
                for expression in expressions
            ]
    return attributes


def render_metric_query(expression, tags):
    context = {"tags": {key: [value] for key, value in tags.items()}}

    def replace(match):
        if match.group(1) in ("__rate_interval", "__interval"):
            return "5m"
        return str(evaluate(match.group(1), context))

    return re.sub(r"\$\{([^}]+)\}", replace, expression)


class ModelTraceFilterTests(unittest.TestCase):
    def endpoint_cases(self):
        return [
            ({}, "", ""),
            ({"server.address": "", "server.port": ""}, "", ""),
            ({"server.address": "backend.example"}, "backend.example", ""),
            ({"server.port": 11434}, "", "11434"),
            ({"server.address": "backend.example", "server.port": 11434}, "backend.example", "11434"),
        ]

    def test_unreported_endpoint_keeps_identity_but_omits_trace_matchers(self):
        for signal, mapping in (
            ("TRACES", MODELS_TRACES),
            ("METRICS", MODELS_METRICS),
        ):
            for endpoint, address, port in self.endpoint_cases():
                with self.subTest(signal=signal, endpoint=endpoint):
                    data = record(
                        signal,
                        attributes={
                            "gen_ai.provider.name": "ollama",
                            "gen_ai.request.model": "test-model",
                            **endpoint,
                        },
                    )
                    component = model_usage(data, mapping)
                    self.assertEqual(
                        component["identifier"],
                        "urn:suse-ai:namespace/prod-eu:service/assistant"
                        f":provider/ollama:address/{address}:port/{port}:model/test-model",
                    )
                    self.assertEqual(component["tags"]["server.address"], address)
                    self.assertEqual(component["tags"]["server.port"], port)
                    self.assertEqual(
                        component["tags"].get("suse.ai.trace.server.address"),
                        address or None,
                    )
                    self.assertEqual(
                        component["tags"].get("suse.ai.trace.server.port"),
                        port or None,
                    )
                    attributes = resolved_trace_attributes(component["tags"])
                    self.assertEqual(
                        attributes.get("server.address"),
                        [address] if address else None,
                    )
                    self.assertEqual(
                        attributes.get("server.port"),
                        [port] if port else None,
                    )
                    self.assertEqual(attributes["gen_ai.request.model"], ["test-model"])

    def test_metric_presentation_keeps_required_endpoint_matchers(self):
        presentation = BY_ID[MODEL_METRICS_PRESENTATION]
        metric = next(
            item for item in presentation["metrics"] if item["metricId"] == "suse_ai_requests"
        )
        expression = metric["metricQueries"][0]["expression"]
        for endpoint, address, port in self.endpoint_cases():
            with self.subTest(endpoint=endpoint):
                data = record(
                    "METRICS",
                    attributes={
                        "gen_ai.provider.name": "ollama",
                        "gen_ai.request.model": "test-model",
                        **endpoint,
                    },
                )
                query = render_metric_query(expression, model_usage(data, MODELS_METRICS)["tags"])
                self.assertIn(f'server_address="{address}"', query)
                self.assertIn(f'server_port="{port}"', query)
                self.assertNotIn("suse_ai_trace_", query)


if __name__ == "__main__":
    unittest.main()
