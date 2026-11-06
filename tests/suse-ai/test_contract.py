"""Behavioral checks for the package's telemetry and identity contracts.

CEL expressions are read from the shipped settings, not reimplemented as Python
mapping rules. The server validator remains authoritative for the platform's
typed CEL environment and presentation schema.
"""

import copy
import functools
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from celpy import Environment, celtypes, json_to_cel
import promql_parser as promql
import yaml


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "stackpack/suse-ai"


class Loader(yaml.SafeLoader):
    pass


for tag in ("!include", "!resource", "!icon"):
    Loader.add_constructor(tag, lambda loader, node: loader.construct_scalar(node))


NODES = [
    node
    for path in sorted((PACK / "settings").rglob("*.sty"))
    for node in yaml.load(path.read_text(), Loader=Loader)["nodes"]
]
BY_ID = {node["identifier"]: node for node in NODES}
ENV = Environment()


def tagged_values(node, tag):
    if isinstance(node, yaml.ScalarNode):
        if node.tag == tag:
            yield node.value
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from tagged_values(item, tag)
    elif isinstance(node, yaml.MappingNode):
        for _, item in node.value:
            yield from tagged_values(item, tag)


def single_value(tags, key):
    values = tags.get(key, [])
    return values[0] if len(values) == 1 else celtypes.StringType("")


def select_prefix(tags, prefix):
    return celtypes.MapType(
        {
            celtypes.StringType(str(key)[len(prefix) :]): values[0]
            for key, values in tags.items()
            if str(key).startswith(str(prefix)) and len(values) == 1
        }
    )


def cel_string(value):
    # cel-python 0.4.0 string(BoolType) uses Python's "True"/"False".
    # CEL's specified boolean-to-string conversion is lowercase.
    if isinstance(value, celtypes.BoolType):
        return celtypes.StringType("true" if value else "false")
    return celtypes.StringType(value)


@functools.lru_cache(maxsize=None)
def program(expression):
    return ENV.program(
        ENV.compile(expression),
        functions={
            "singleValue": single_value,
            "selectPrefix": select_prefix,
            "string": cel_string,
            "join": lambda values, separator: celtypes.StringType(str(separator).join(values)),
            "replace": lambda value, old, new: celtypes.StringType(
                str(value).replace(str(old), str(new))
            ),
        },
    )


def evaluate(expression, context):
    return program(expression).evaluate(
        {key: json_to_cel(value) for key, value in context.items()}
    )


def record(
    signal="TRACES",
    resource=None,
    attributes=None,
    metric="gen_ai.client.operation.duration",
):
    return {
        "signal": signal,
        "resource": {
            "attributes": resource
            if resource is not None
            else {
                "service.name": "assistant",
                "service.namespace": "prod-eu",
                "service.instance.id": "pod-1",
                "telemetry.sdk.name": "opentelemetry",
            }
        },
        "scope": {"name": "openlit.otel", "version": "fixture", "attributes": {}},
        "span": {
            "name": "chat llama3",
            "attributes": attributes or {},
            "kind": "Client",
        },
        "metric": {"name": metric},
        "datapoint": {"attributes": attributes or {}},
    }


def selected(spec, context):
    if not evaluate(spec.get("condition", "true"), context):
        return False
    action = evaluate(spec.get("action", "'CONTINUE'"), context)
    if action == "CREATE":
        return True
    return any(
        selected(child, context)
        for key, child in spec.items()
        if key in ("scope", "span", "metric", "datapoint")
    )


def mapped(data, kind="OtelComponentMapping"):
    results = []
    for node in NODES:
        if node["_type"] != kind or data["signal"] not in node["input"]["signal"]:
            continue
        if not selected(node["input"]["resource"], data):
            continue
        variables = {
            item["name"]: evaluate(item["value"], data) for item in node.get("vars", [])
        }
        context = {**data, "vars": variables}
        output = {
            key: str(evaluate(value, context))
            for key, value in node["output"].items()
            if key not in ("required", "optional")
        }
        output["tags"] = {}
        for item in node["output"].get("required", {}).get("tags", []):
            value = evaluate(item["source"], context)
            if "pattern" in item:
                for key, tag_value in value.items():
                    match = re.fullmatch(item["pattern"], str(key))
                    if match:
                        target = item["target"]
                        for index, group in enumerate(match.groups(), 1):
                            target = target.replace("${" + str(index) + "}", group)
                        output["tags"][target] = str(tag_value)
            else:
                output["tags"][item["target"]] = str(value)
        results.append(output)
    return results


def component(data, type_name):
    matches = [item for item in mapped(data) if item["typeName"] == type_name]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {type_name}: {matches}")
    return matches[0]


def render(query, instance=False):
    tags = {
        key: [value]
        for key, value in {
            "service.namespace": "prod-eu",
            "service.name": "assistant",
            "cluster-name": "cluster-a",
            "namespace": "ai",
            "node-name": "gpu-1",
            "gpu.uuid": "GPU-device",
            "vllm.model.name": "llama3",
            "ollama.model.name": "gemma:2b",
            "gen_ai.request.model": "llama3",
            "gen_ai.provider.name": "openai",
            "server.address": "vllm.ai.svc",
            "server.port": "8000",
        }.items()
    }
    if instance:
        tags["service.instance.id"] = ["replica.with.regex+characters"]
    for key in ("service.namespace", "service.name", "service.instance.id"):
        if key in tags:
            tags["suse.ai.metric." + key.replace(".", "_")] = tags[key]
    context = {
        "name": "component-name",
        "tags": tags,
        "properties": {"sts_host": "gpu-1-cluster-a"},
    }

    def multi(match):
        values = evaluate(match[1], context)
        selectors = ", ".join(
            str(key) + "=" + json.dumps(str(value)) for key, value in values.items()
        )
        return (
            ", " if selectors and match[0].lstrip().startswith(",") else ""
        ) + selectors

    query = re.sub(r',?\s*__multi__="\$\{(.*?)\}"', multi, query)

    def scalar(match):
        if match[1] in ("__rate_interval", "__interval"):
            return "5m"
        return str(evaluate(match[1], context))

    return re.sub(r"\$\{([^}]+)\}", scalar, query)


def render_topological_monitor(query, endpoint=None):
    # Offline PromQL fixtures use the legacy resolver's nonempty tag contract,
    # never CEL presentation interpolation. test_backend_metrics exercises the
    # real native runner, including its resolved query and numeric health input.
    data = record(attributes={
        "gen_ai.provider.name": "openai", "gen_ai.request.model": "llama3",
        **({"server.address": "vllm.ai.svc", "server.port": "8000"}
           if endpoint is None else endpoint),
    })
    tags = component(data, "genai model usage")["tags"]
    tags["vllm.model.name"] = "llama3"
    parameters = {"tags." + k: v for k, v in tags.items() if v}

    def bind(match):
        if match[1] not in parameters:
            raise AssertionError(f"Unresolved monitor binding: {match[1]}")
        # Java/Scala regex replacement consumes escaping in replacement values.
        return re.sub(r"\\(.)", lambda m: m[1], parameters[match[1]])

    return re.sub(r"\$\{([^}]+)\}", bind, query)


def walk(expr):
    yield expr
    if isinstance(expr, promql.AggregateExpr):
        yield from walk(expr.expr)
        if expr.param is not None:
            yield from walk(expr.param)
    elif isinstance(expr, promql.BinaryExpr):
        yield from walk(expr.lhs)
        yield from walk(expr.rhs)
    elif isinstance(expr, promql.Call):
        for arg in expr.args:
            yield from walk(arg)
    elif isinstance(expr, (promql.ParenExpr, promql.UnaryExpr, promql.SubqueryExpr)):
        yield from walk(expr.expr)
    elif isinstance(expr, promql.MatrixSelector):
        yield from walk(expr.vector_selector)


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.attributes = {
            "gen_ai.provider.name": "openai",
            "gen_ai.request.model": "llama3",
            "gen_ai.operation.name": "chat",
            "server.address": "vllm.ai.svc",
            "server.port": 8000,
        }

    def test_openlit_uses_canonical_otel_services(self):
        data = record(attributes=self.attributes)
        self.assertEqual(
            component(data, "otel service")["identifier"],
            "urn:opentelemetry:namespace/prod-eu:service/assistant",
        )
        self.assertEqual(
            component(data, "otel service instance")["identifier"],
            "urn:opentelemetry:namespace/prod-eu:service/assistant:serviceInstance/pod-1",
        )
        self.assertEqual(
            component(data, "genai model usage")["identifier"],
            "urn:suse-ai:namespace/prod-eu:service/assistant"
            ":provider/openai:address/vllm.ai.svc:port/8000:model/llama3",
        )
        self.assertEqual(
            data["resource"]["attributes"]["telemetry.sdk.name"], "opentelemetry"
        )

    def test_ai_service_contributions_retain_the_presentation_tag(self):
        # The base OTel mappings contribute their own stackpack label to the
        # shared identity. Each AI contribution must retain the AI label.
        for signal in ("TRACES", "METRICS"):
            data = record(signal, attributes=self.attributes)
            for type_name in ("otel service", "otel service instance"):
                with self.subTest(signal=signal, type_name=type_name):
                    self.assertEqual(
                        component(data, type_name)["tags"]["stackpack"], "suse-ai"
                    )

    def test_openllmetry_legacy_provider(self):
        data = record(
            attributes={"gen_ai.system": "anthropic", "gen_ai.request.model": "claude"}
        )
        data["scope"]["name"] = "opentelemetry.instrumentation.anthropic"
        self.assertEqual(
            component(data, "genai model usage")["tags"]["gen_ai.provider.name"],
            "anthropic",
        )
        self.assertEqual(component(data, "otel service")["name"], "assistant")

    def test_current_provider_wins_over_legacy(self):
        data = record(attributes={**self.attributes, "gen_ai.system": "legacy-value"})
        self.assertEqual(
            component(data, "genai model usage")["tags"]["gen_ai.provider.name"],
            "openai",
        )

    def test_provider_does_not_create_a_physical_engine(self):
        types = {
            item["typeName"] for item in mapped(record(attributes=self.attributes))
        }
        self.assertEqual(
            types, {"otel service", "otel service instance", "genai model usage"}
        )

    def test_namespace_provider_and_endpoint_separate_models(self):
        data = record(attributes=self.attributes)
        original = component(data, "genai model usage")["identifier"]
        for context, key, value in [
            ("resource", "service.namespace", "prod-us"),
            ("span", "gen_ai.provider.name", "anthropic"),
            ("span", "server.address", "other.ai.svc"),
            ("span", "server.port", 9000),
        ]:
            other = copy.deepcopy(data)
            other[context]["attributes"][key] = value
            self.assertNotEqual(
                original, component(other, "genai model usage")["identifier"]
            )

    def test_replica_changes_do_not_duplicate_logical_models(self):
        data = record(attributes=self.attributes)
        original = component(data, "genai model usage")["identifier"]
        data["resource"]["attributes"]["service.instance.id"] = "pod-2"
        self.assertEqual(original, component(data, "genai model usage")["identifier"])

    def test_metrics_and_traces_preserve_model_usage_without_runtime_call_edges(self):
        traces = record(attributes=self.attributes)
        metrics = record("METRICS", attributes=self.attributes)
        self.assertEqual(
            component(traces, "genai model usage"),
            component(metrics, "genai model usage"),
        )
        # Requesting a model identifies usage, not a separately callable runtime.
        # Communication edges require paired spans identifying real services.
        self.assertEqual(mapped(traces, "OtelRelationMapping"), [])
        self.assertEqual(mapped(metrics, "OtelRelationMapping"), [])

    def test_service_calls_preserve_canonical_namespaces_and_ignore_virtual_nodes(self):
        attrs = {'client': 'assistant', 'server': 'assistant',
                 'client_service.namespace': 'front', 'server_service.namespace': 'back',
                 'connection_type': ''}
        data = record('METRICS', resource={}, attributes=attrs, metric='suse.ai.service.calls')
        relations = mapped(data, 'OtelRelationMapping')
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]['sourceId'], 'urn:opentelemetry:namespace/front:service/assistant')
        self.assertEqual(relations[0]['targetId'], 'urn:opentelemetry:namespace/back:service/assistant')
        data['datapoint']['attributes'] = {'client': 'a', 'server': 'b', 'connection_type': ''}
        self.assertEqual(mapped(data, 'OtelRelationMapping')[0]['sourceId'],
                         'urn:opentelemetry:namespace/default:service/a')
        for changes in ({'virtual_node': 'server'}, {'virtual_node': 'client'},
                        {'connection_type': 'database'}, {'server': ''}):
            data['datapoint']['attributes'] = {**attrs, **changes}
            self.assertEqual(mapped(data, 'OtelRelationMapping'), [])
        data['datapoint']['attributes'] = attrs
        data['metric']['name'] = 'traces_service_graph_request_total'
        self.assertEqual(mapped(data, 'OtelRelationMapping'), [],
                         'AI settings must not also consume the companion service graph')

    def test_unknown_endpoint_is_not_merged_with_a_known_endpoint(self):
        known = record(attributes=self.attributes)
        unknown = record(
            attributes={
                k: v for k, v in self.attributes.items() if not k.startswith("server.")
            }
        )
        self.assertNotEqual(
            component(known, "genai model usage")["identifier"],
            component(unknown, "genai model usage")["identifier"],
        )

    def test_standard_and_openllmetry_agent_names_match(self):
        standard = record(
            attributes={
                "gen_ai.agent.name": "planner",
                "gen_ai.operation.name": "invoke_agent",
            }
        )
        legacy = record(
            attributes={
                "traceloop.span.kind": "agent",
                "traceloop.entity.name": "planner",
            }
        )
        self.assertEqual(
            component(standard, "genai agent"), component(legacy, "genai agent")
        )
        self.assertEqual(
            component(standard, "genai agent")["identifier"],
            "urn:suse-ai:namespace/prod-eu:service/assistant:agent/planner",
        )

    def test_invocation_ids_and_content_do_not_enter_topology(self):
        data = record(
            attributes={
                **self.attributes,
                "gen_ai.agent.name": "planner",
                "gen_ai.agent.id": "invocation-123",
                "gen_ai.conversation.id": "private-chat",
                "gen_ai.input.messages": "private-prompt",
            }
        )
        output = json.dumps(mapped(data))
        for private in ("invocation-123", "private-chat", "private-prompt"):
            self.assertNotIn(private, output)

    def test_named_agent_keeps_hosting_relation_without_direct_model_communication(self):
        anonymous = record(attributes=self.attributes)
        named = record(attributes={**self.attributes, "gen_ai.agent.name": "planner"})
        self.assertEqual(mapped(anonymous, "OtelRelationMapping"), [])
        relations = mapped(named, "OtelRelationMapping")
        agent = component(named, "genai agent")["identifier"]
        model = component(named, "genai model usage")["identifier"]
        service = component(named, "otel service")["identifier"]
        self.assertTrue(
            any(
                item["sourceId"] == agent and item["targetId"] == service
                for item in relations
            )
        )
        self.assertFalse(any(model in (item["sourceId"], item["targetId"])
                             for item in relations))

    def test_legacy_product_tags_enrich_existing_identity(self):
        data = record(
            "METRICS",
            resource={
                "service.name": "inference",
                "service.namespace": "prod-eu",
                "suse.ai.component.type": "inference-engine",
                "suse.ai.component.name": "vllm",
            },
            metric="vllm:num_requests_running",
            attributes={"model_name": "llama3"},
        )
        service = component(data, "otel service")
        self.assertEqual(
            service["identifier"],
            "urn:opentelemetry:namespace/prod-eu:service/inference",
        )
        self.assertEqual(service["tags"]["suse.ai.product"], "vllm")
        self.assertEqual(service["tags"]["suse.ai.category"], "inference-engine")
        self.assertEqual(
            component(data, "genai served model")["tags"]["vllm.model.name"], "llama3"
        )

    def test_litellm_overrides_enrich_proxy_services_without_inference_entities(self):
        for signal in ("METRICS", "TRACES"):
            data = record(signal, resource={
                "service.name": "litellm",
                "service.namespace": "vllm",
                "service.instance.id": "pod-uid",
                "suse.ai.managed": "true",
                "suse.ai.component.name": "litellm",
                "suse.ai.component.type": "model-proxy",
            }, metric="litellm_guardrail_requests_total", attributes={})
            service = component(data, "otel service")
            self.assertEqual(service["identifier"], "urn:opentelemetry:namespace/vllm:service/litellm")
            self.assertEqual(service["tags"]["suse.ai.product"], "litellm")
            self.assertEqual(service["tags"]["suse.ai.category"], "model-proxy")
            instance = component(data, "otel service instance")
            self.assertTrue(instance["identifier"].endswith(":serviceInstance/pod-uid"))
            self.assertEqual({m["typeName"] for m in mapped(data)}, {"otel service", "otel service instance"})

    def test_plain_otel_and_missing_service_do_not_create_ai_components(self):
        for data in [
            record(),
            record(resource={}, attributes=self.attributes),
            record(resource={"service.name": ""}, attributes=self.attributes),
        ]:
            self.assertEqual(mapped(data), [])

    def test_no_service_instance_is_invented(self):
        data = record(
            resource={"service.name": "assistant"}, attributes=self.attributes
        )
        self.assertEqual(
            component(data, "otel service")["identifier"],
            "urn:opentelemetry:namespace/default:service/assistant",
        )
        self.assertNotIn(
            "otel service instance", [item["typeName"] for item in mapped(data)]
        )

    def test_explicit_opt_out_is_respected(self):
        for disabled in (False, "false"):
            data = record(
                attributes={**self.attributes, "gen_ai.agent.name": "planner"}
            )
            data["resource"]["attributes"]["suse.ai.managed"] = disabled
            self.assertEqual(mapped(data), [])
            self.assertEqual(mapped(data, "OtelRelationMapping"), [])

    def test_managed_flag_discovers_metrics_only_services(self):
        for enabled in (True, "true"):
            data = record(
                "METRICS",
                resource={"service.name": "custom-ai", "suse.ai.managed": enabled},
                metric="custom_requests",
            )
            self.assertEqual(component(data, "otel service")["name"], "custom-ai")

    def test_all_relations_have_endpoints_from_the_same_record(self):
        cases = [
            record(attributes=self.attributes),
            record(attributes={"gen_ai.agent.name": "planner"}),
            record(
                "METRICS",
                resource={"service.name": "vllm", "suse.ai.product": "vllm"},
                metric="vllm:num_requests_running",
                attributes={"model_name": "llama3"},
            ),
        ]
        for data in cases:
            identifiers = {item["identifier"] for item in mapped(data)}
            for relation in mapped(data, "OtelRelationMapping"):
                self.assertIn(relation["sourceId"], identifiers)
                self.assertIn(relation["targetId"], identifiers)


class PackageContractTests(unittest.TestCase):
    def test_default_navigation_keeps_replicas_in_drilldowns(self):
        menus = {}
        for node in NODES:
            overview = node.get("presentation", {}).get("overview", {})
            if "mainMenu" in overview:
                menus[overview["name"]["title"]] = node
        self.assertEqual(set(menus), {"Overview", "Applications & agents", "Models", "Inference", "Data services", "GPUs"})
        query = menus["Overview"]["binding"]["query"]
        self.assertIn('"otel service"', query)
        self.assertIn('"genai served model"', query)
        self.assertNotIn('"otel service instance"', query)
        self.assertNotIn('"genai model usage"', query)
        self.assertNotIn('"genai database dependency"', query)
        self.assertFalse(menus["Overview"]["presentation"]["topology"]["connectedComponents"])
        self.assertNotIn("Observed dependencies", menus)

    def test_overview_columns_do_not_leak_observer_or_product_specific_fields(self):
        prefix = "urn:stackpack:suse-ai:component-presentation:"
        observer_columns = {"suse_ai_observer_service", "suse_ai_observer_cluster", "suse_ai_discovery"}
        for suffix in ("common", "all", "inference", "data-services", "applications",
                       "model-inventory", "models", "agents"):
            columns = BY_ID[prefix + suffix]["presentation"]["overview"]["columns"]
            ids = {c["columnId"] for c in columns}
            self.assertFalse(ids & observer_columns, suffix)
            self.assertNotIn("suse_ai_otel_k8s_namespace", ids, suffix)
        for suffix in ("model-inventory", "served-models", "agents"):
            overview = BY_ID[prefix + suffix]["presentation"]["overview"]
            self.assertNotIn("suse_ai_health", {c["columnId"] for c in overview["columns"]})
            self.assertNotIn("suse_ai_health", {c["columnId"] for c in overview["sort"]})
        data = BY_ID[prefix + "data-services"]
        self.assertIn('type = "otel service"', data["binding"]["query"])
        self.assertNotIn('"genai database dependency"', data["binding"]["query"])

    def test_caller_drilldowns_separate_native_and_observed_data_dependencies(self):
        prefix = "urn:stackpack:suse-ai:component-presentation:"
        resources = {r["resourceId"]: r for r in
                     BY_ID[prefix + "services-overlay"]["presentation"]["highlight"]["relatedResources"]}
        native = resources["suse_ai_data_dependencies"]
        self.assertIn('withNeighborsOf(direction = "down"', native["topologyQuery"])
        self.assertIn('type = "otel service"', native["topologyQuery"])
        self.assertEqual(native["presentationIdentifier"], prefix + "data-services")
        observed = resources["suse_ai_observed_dependencies"]
        self.assertIn('type = "genai database dependency"', observed["topologyQuery"])
        for tag in ("service.namespace", "service.name"):
            self.assertIn("tags.singleValue('" + tag + "')", observed["topologyQuery"])
        self.assertEqual(observed["presentationIdentifier"], prefix + "database-dependencies")

    def test_model_usage_links_identify_the_caller(self):
        node = BY_ID["urn:stackpack:suse-ai:component-presentation:models"]
        column = next(c for c in node["presentation"]["overview"]["columns"]
                      if c["columnId"] == "suse_ai_otel_name")
        names = [str(evaluate(column["projection"]["name"], {"tags": {
            "gen_ai.request.model": ["llama3"], "service.name": [service]
        }})) for service in ("assistant", "researcher")]
        self.assertEqual(names, ["llama3 used by assistant", "llama3 used by researcher"])
        self.assertEqual(column["projection"]["identifier"], "identifiers[0]")

    def test_models_inventory_keeps_consumer_usage_in_application_drilldowns(self):
        inventory = BY_ID["urn:stackpack:suse-ai:component-presentation:model-inventory"]
        self.assertIn('type = "genai served model"', inventory["binding"]["query"])
        self.assertNotIn('"genai model usage"', inventory["binding"]["query"])
        services = BY_ID["urn:stackpack:suse-ai:component-presentation:services-overlay"]
        usage = next(r for r in services["presentation"]["highlight"]["relatedResources"]
                     if r["resourceId"] == "suse_ai_models")
        self.assertIn('type = "genai model usage"', usage["topologyQuery"])
        self.assertEqual(usage["presentationIdentifier"],
                         "urn:stackpack:suse-ai:component-presentation:models")

    def test_model_inventory_metrics_preserve_deployment_and_caller_scope(self):
        for presentation, required_labels in [
            ("served-models-vllm", {"service_namespace", "service_name", "model_name"}),
            ("models", {"service_namespace", "service_name", "gen_ai_request_model",
                               "gen_ai_provider_name", "server_address", "server_port"}),
        ]:
            node = BY_ID["urn:stackpack:suse-ai:component-presentation:" + presentation]
            columns = [c for c in node["presentation"]["overview"]["columns"]
                       if c.get("projection", {}).get("_type") == "MetricProjection"]
            metric_ids = {m["metricId"] for n in NODES for m in n.get("metrics", [])}
            self.assertEqual(len(columns), 3 if presentation == "served-models-vllm" else 0)
            for column in columns:
                projection = column["projection"]
                self.assertEqual(projection["_type"], "MetricProjection")
                self.assertIn(projection["metricId"], metric_ids)
                for selector in walk(promql.parse(render(projection["query"]))):
                    if isinstance(selector, promql.VectorSelector):
                        labels = {m.name for m in selector.matchers.matchers}
                        self.assertTrue(required_labels <= labels, column["columnId"])

    def test_gpu_inventory_preserves_physical_counts_and_scoped_metrics(self):
        node = BY_ID["urn:stackpack:suse-ai:component-presentation:gpu-nodes"]
        columns = {c["columnId"]: c for c in node["presentation"]["overview"]["columns"]}
        self.assertIn("nvidia.com/gpu.count", columns["suse_ai_gpu_count"]["projection"]["value"])
        self.assertNotIn("replicas", columns["suse_ai_gpu_count"]["projection"]["value"])
        projection = columns["suse_ai_gpu_memory"]["projection"]
        self.assertEqual(evaluate(projection["value"], {"tags": {"nvidia.com/gpu.memory": ["15360"]}}), 15360 * 1048576)
        for column in columns.values():
            p = column["projection"]
            if p["_type"] == "MetricProjection":
                for item in walk(promql.parse(render(p["query"]))):
                    if isinstance(item, promql.VectorSelector):
                        keys = {m.name for m in item.matchers.matchers}
                        if "_host_" in column["columnId"]:
                            self.assertIn("sts_host", keys)
                            self.assertIn("properties.sts_host", p["query"])
                        else:
                            self.assertTrue({"k8s_cluster_name", "k8s_node_name"} <= keys)
        titles = {f["title"] for f in node["presentation"]["highlight"]["fields"]}
        self.assertTrue({"Driver version", "CUDA runtime", "Node OS", "Scheduling slots per GPU"} <= titles)

    def test_remediation_templates_use_threshold_monitor_context(self):
        # Actual threshold monitor run output exposes these fields. It does
        # not provide componentName or currentValue; either makes the entire
        # troubleshooting panel fail, even when the monitor evaluates CLEAR.
        context = {
            "componentUrnForUrl": "urn:opentelemetry:namespace%2Fprod:service%2Finference",
            "labels": {"service_name": "inference", "service_namespace": "prod"},
            "threshold": 0.9,
        }
        for node in NODES:
            if node["_type"] != "Monitor":
                continue
            hint = node.get("remediationHint", "")
            if not hint.startswith("remediation-hints/"):
                continue
            self.assertIn(node["function"], {"urn:stackpack:common:monitor-function:threshold",
                                             "urn:stackpack:common:monitor-function:topological-threshold",
                                             "urn:stackpack:common:monitor-function:derived-state-monitor"})
            template_context = ({"componentName": "model", "causeComponentName": "inference",
                                 "causeComponentUrnForUrl": context["componentUrnForUrl"]}
                                if node["function"].endswith(":derived-state-monitor") else context)
            template = (PACK / "includes" / hint).read_text()
            for expression in re.findall(r"\{\{(.*?)\}\}", template, re.DOTALL):
                parts = expression.split()
                # The server's multiply helper truncates fractional thresholds
                # (0.9 * 100 rendered as 0). Keep the original numeric scale.
                self.assertEqual(len(parts), 1, hint)
                value = template_context
                for key in parts[0].split("."):
                    self.assertIn(key, value, f"{hint}: {expression}")
                    value = value[key]

    def test_navigation_and_products_ship_valid_presentation_icons(self):
        # A valid package can still render empty menu/component icons. Validate
        # both the presentation references and the packaged image payloads.
        for path in (PACK / "settings").rglob("*.sty"):
            document = yaml.compose(path.read_text())
            for icon in tagged_values(document, "!icon"):
                data = (PACK / "icons" / icon).read_bytes()
                if icon.endswith(".svg"):
                    svg = ET.fromstring(data)
                    self.assertEqual(svg.tag.split("}")[-1], "svg")
                    # The topology canvas requires intrinsic dimensions; an
                    # SVG with only viewBox renders in details but not topology.
                    self.assertTrue(svg.get("width"), icon)
                    self.assertTrue(svg.get("height"), icon)
                else:
                    self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), icon)

        for node in NODES:
            if node["_type"] != "ComponentPresentation":
                continue
            presentation = node["presentation"]
            menu = presentation.get("overview", {}).get("mainMenu")
            if menu:
                self.assertTrue(menu.get("icon") or presentation.get("icon"), node["name"])
            if ":product-" in node["identifier"]:
                self.assertNotIn("icon", presentation, node["name"])

    def test_packaged_assets_are_referenced(self):
        documents = [
            yaml.compose(path.read_text())
            for path in [PACK / "stackpack.yaml", *sorted((PACK / "settings").rglob("*.sty"))]
        ]
        for tag, directory in (
            ("!icon", "icons"),
            ("!resource", "resources"),
            ("!include", "includes"),
        ):
            referenced = {
                value for document in documents for value in tagged_values(document, tag)
            }
            packaged = {
                str(path.relative_to(PACK / directory))
                for path in (PACK / directory).rglob("*")
                if path.is_file()
            }
            self.assertTrue(referenced <= packaged, directory)
            if directory != "icons":
                self.assertEqual(referenced, packaged, directory)

    def test_ai_overviews_use_namespaced_identity_columns(self):
        for node in NODES:
            if node["_type"] != "ComponentPresentation":
                continue
            if '"otel service"' not in node["binding"]["query"]:
                continue
            columns = node.get("presentation", {}).get("overview", {}).get("columns", [])
            for column in columns:
                projection = column.get("projection", {})
                if projection.get("_type") == "ComponentLinkProjection" and projection.get("name") == "name":
                    self.assertEqual(column["columnId"], "suse_ai_otel_name")
                if projection.get("value") == "tags.singleValue('service.namespace')":
                    self.assertEqual(column["columnId"], "suse_ai_otel_namespace")

    def test_supported_node_types_and_unique_ownership(self):
        supported = {
            "OtelComponentMapping",
            "OtelRelationMapping",
            "ComponentPresentation",
            "MainMenuGroup",
            "Monitor",
            "Dashboard",
            "ExternalMonitor",
        }
        self.assertEqual(len(NODES), len(BY_ID))
        for node in NODES:
            self.assertIn(node["_type"], supported)
            self.assertTrue(node["identifier"].startswith("urn:stackpack:suse-ai:"))
        for path in (PACK / "settings").rglob("*.sty"):
            self.assertNotIn("{{", path.read_text())

    def test_every_metric_reference_resolves_locally(self):
        # Highlights can refer to metric definitions inherited from another
        # matching presentation, just as overview columns can be inherited.
        all_metric_ids = {
            metric["metricId"] for node in NODES for metric in node.get("metrics", [])
        }
        def referenced_metrics(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "metricId":
                        yield item
                    else:
                        yield from referenced_metrics(item)
            elif isinstance(value, list):
                for item in value:
                    yield from referenced_metrics(item)

        # Definitions are shared by matching presentations. Check both missing
        # references and definitions left unused after a presentation changes.
        referenced = {
            metric_id
            for node in NODES
            for metric_id in referenced_metrics(node.get("presentation", {}))
        }
        self.assertEqual(all_metric_ids, referenced)
        for node in NODES:
            if node["_type"] != "ComponentPresentation":
                continue
            ids = [m["metricId"] for m in node.get("metrics", [])]
            self.assertEqual(len(ids), len(set(ids)), node["identifier"])
            presentation = node.get("presentation", {})
            for section in presentation.get("highlight", {}).get("metrics", []):
                for item in section["metrics"]:
                    self.assertIn(item["metricId"], all_metric_ids)
            for tab in presentation.get("metricPerspective", {}).get("tabs", []):
                for section in tab["sections"]:
                    for item in section["metrics"]:
                        self.assertIn(item["metricId"], ids)

    def test_latency_charts_use_a_supported_duration_unit(self):
        for node in NODES:
            for metric in node.get("metrics", []):
                # "seconds" is accepted by settings validation but the UI
                # treats it as an unknown unit and omits the duration suffix.
                self.assertNotEqual(metric.get("chart", {}).get("unit"), "seconds")

    def test_product_queries_keep_namespace_and_service_and_optional_instance(self):
        for node in NODES:
            for metric in node.get("metrics", []):
                for query in metric["metricQueries"]:
                    for instance in (False, True):
                        # tlast_over_time is an existing VictoriaMetrics function.
                        # Substitute its PromQL shape for parser validation only.
                        expression = render(query["expression"], instance).replace(
                            "tlast_over_time(", "last_over_time("
                        )
                        tree = promql.parse(expression)
                        for selector in [
                            item
                            for item in walk(tree)
                            if isinstance(item, promql.VectorSelector)
                        ]:
                            keys = {m.name: m for m in selector.matchers.matchers}
                            if "genai gpu" in node["binding"]["query"]:
                                self.assertTrue({"UUID", "k8s_cluster_name"} <= keys.keys())
                            elif "_node_host_" in metric["metricId"]:
                                self.assertIn("sts_host", keys, metric["metricId"])
                                self.assertIn("properties.sts_host", query["expression"])
                            elif (
                                "_pod_gpu_" in metric["metricId"]
                                or "_pod_vgpu_" in metric["metricId"]
                                or "_node_" in metric["metricId"]
                            ):
                                self.assertIn(
                                    "k8s_cluster_name", keys, metric["metricId"]
                                )
                            else:
                                self.assertIn(
                                    "service_namespace", keys, metric["metricId"]
                                )
                                self.assertIn("service_name", keys, metric["metricId"])
                                if (
                                    instance
                                    and "genai model usage"
                                    not in node["binding"]["query"]
                                ):
                                    self.assertIn(
                                        "service_instance_id", keys, metric["metricId"]
                                    )
                                    self.assertEqual(
                                        keys["service_instance_id"].op,
                                        promql.MatchOp.Equal,
                                    )

    def test_monitors_preserve_identity_and_never_attach_to_global_products(self):
        for node in NODES:
            if node["_type"] != "Monitor":
                continue
            if node["function"].endswith(":derived-state-monitor"):
                self.assertEqual(node["arguments"], {"componentTypes": "genai served model, genai agent"})
                continue
            if node["function"].endswith(":topological-threshold"):
                queries = node["arguments"]["queries"]
                self.assertIn('label = "stackpack:suse-ai"', queries["topologyQuery"])
                self.assertNotIn("urnTemplate", node["arguments"])
                tree = promql.parse(render_topological_monitor(queries["promqlQuery"]))
                for item in walk(tree):
                    if isinstance(item, promql.VectorSelector):
                        keys = {m.name for m in item.matchers.matchers}
                        self.assertTrue({"service_namespace", "service_name"} <= keys)
                        if '"genai served model"' in queries["topologyQuery"]:
                            self.assertIn("model_name", keys)
                        else:
                            self.assertTrue({"gen_ai_request_model", "gen_ai_provider_name", "server_address", "server_port"} <= keys)
                continue
            tree = promql.parse(node["arguments"]["metric"]["query"])
            urn = node["arguments"]["urnTemplate"]
            if "nvidia-xid" in node["identifier"]:
                self.assertEqual(
                    urn, "urn:kubernetes:/${k8s_cluster_name}:node/${k8s_node_name}"
                )
                continue
            self.assertEqual(
                urn,
                "urn:opentelemetry:namespace/${service_namespace}:service/${service_name}",
            )
            for item in walk(tree):
                if isinstance(item, promql.VectorSelector):
                    keys = {m.name for m in item.matchers.matchers}
                    required = {"service_namespace", "service_name"}
                    if node["identifier"].endswith(":http-probe-unavailable"):
                        required.add("suse_ai_observation_kind")
                        self.assertTrue(any(
                            m.name == "suse_ai_observation_kind" and m.value == "http-probe"
                            for m in item.matchers.matchers
                        ))
                    elif "genai-metric-stream-active" not in node["identifier"]:
                        required.add("suse_ai_product")
                    self.assertTrue(
                        required <= keys,
                        node["identifier"],
                    )
                if isinstance(item, promql.AggregateExpr):
                    self.assertIsNotNone(item.modifier, node["identifier"])
                    self.assertTrue(
                        {"service_namespace", "service_name"}
                        <= set(item.modifier.labels),
                        node["identifier"],
                    )


if __name__ == "__main__":
    unittest.main()
