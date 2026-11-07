"""Product metric regressions evaluated by Prometheus, including sparse outcomes."""

import json
import os
import unittest

from test_contract import BY_ID
from test_promql import run_promql_cases


INSTANCE = "replica.with.regex+characters"


def labels(**values):
    return "{" + ",".join(f"{key}={json.dumps(value)}" for key, value in values.items()) + "}"


def series(metric, product, values="0+60x20", **dimensions):
    dimensions = {
        "suse_ai_product": product,
        "service_namespace": "prod-eu",
        "service_name": "assistant",
        "service_instance_id": INSTANCE,
        **dimensions,
    }
    return {"series": metric + labels(**dimensions), "values": values}


def samples(value, **dimensions):
    return [{"labels": labels(**dimensions), "value": value}]


def chart(product, metric, expected, **options):
    return {
        "presentation": "product-" + product,
        "metric": "suse_ai_" + (product + "_" + metric).replace("-", "_"),
        "samples": expected,
        **options,
    }


def monitor(identifier, expected):
    return {"monitor": identifier, "samples": expected}


def health(value, **identity):
    return samples(value, **{"service_namespace": "prod-eu", "service_name": "assistant", **identity})


def product_cases():
    cases = []
    for protocol, success, failures in [("rest", "200", ["400", "503"]), ("grpc", "0", ["3", "13"])]:
        metric = protocol + "_responses_total"
        chart_id = "vectordb-" + protocol + "-responses-fail"
        monitor_id = "qdrant-" + protocol + "-api-failures"
        healthy_checks = [chart("qdrant", chart_id, samples(0)), monitor(monitor_id, health(0))]
        if protocol == "rest":
            healthy_checks.append({
                "presentation": "product-qdrant",
                "metric": "suse_ai_qdrant_vectordb_rest_responses_fail",
                "samples": samples(0),
            })
        cases.append({
            "name": f"Qdrant {protocol} success-only traffic has zero failures",
            "series": [series(metric, "qdrant", status=success)],
            "checks": healthy_checks,
        })
        cases.append({
            "name": f"Qdrant {protocol} status failures aggregate replicas but preserve identities",
            "series": [
                series(metric, "qdrant", status=success),
                series(metric, "qdrant", status=failures[0]),
                series(metric, "qdrant", "0+120x20", status=failures[1], service_instance_id="other-replica"),
                series(metric, "qdrant", "0+600x20", status=failures[0], service_namespace="other"),
                series(metric, "qdrant", "0+1200x20", status=failures[0], service_name="other"),
            ],
            "checks": [
                chart("qdrant", chart_id, samples(3)),
                chart("qdrant", chart_id, samples(1), instance=True),
                monitor(monitor_id, health(3) + health(10, service_namespace="other") + health(20, service_name="other")),
            ],
        })
        for name, data in [
            ("absent protocol", []),
            ("unknown status", [series(metric, "qdrant")]),
            ("unrelated namespace", [series(metric, "qdrant", status=success, service_namespace="other")]),
        ]:
            checks = [chart("qdrant", chart_id, [])]
            if name != "unrelated namespace":
                checks.append(monitor(monitor_id, []))
            cases.append({"name": f"Qdrant {protocol} {name} does not invent a healthy series", "series": data, "checks": checks})

    milvus_metric = "milvus_proxy_req_count_total"
    milvus_success = "vectordb-system-request-success-rate"
    milvus_failure = "vectordb-system-request-failed-rate"
    milvus_count = "vectordb-system-failed-requests-count"
    cases.extend([
        {
            "name": "Milvus total and success represent one request, not two",
            "series": [series(milvus_metric, "milvus", status=status, function_name="Search") for status in ["total", "success"]],
            "checks": [
                chart("milvus", milvus_success, samples(1, function_name="Search")),
                chart("milvus", milvus_failure, samples(0, function_name="Search")),
                chart("milvus", milvus_count, samples(0)),
                monitor("milvus-request-failed-rate", health(0)),
            ],
        },
        {
            "name": "Milvus success-only operation still has a scoped zero failure baseline",
            "series": [series(milvus_metric, "milvus", status="success", function_name="CreateCollection")],
            "checks": [
                chart("milvus", milvus_failure, samples(0, function_name="CreateCollection")),
                monitor("milvus-request-failed-rate", health(0)),
            ],
        },
        {
            "name": "Milvus current and legacy failures exclude success, total, and rejection outcomes",
            "series": [
                series(milvus_metric, "milvus", f"0+{increment}x20", status=status, function_name="Search")
                for status, increment in [("fail", 60), ("fail_input", 120), ("fail_system", 180), ("success", 240), ("total", 600), ("rejected_user", 1200)]
            ],
            "checks": [
                chart("milvus", milvus_success, samples(4, function_name="Search")),
                chart("milvus", milvus_failure, samples(6, function_name="Search")),
                chart("milvus", milvus_count, samples(1800)),
                monitor("milvus-request-failed-rate", health(6)),
            ],
        },
        {
            "name": "Milvus namespace, service and instance selectors isolate failure rates",
            "series": [
                series(milvus_metric, "milvus", status="fail_system", function_name="Search"),
                series(milvus_metric, "milvus", "0+120x20", status="fail_input", function_name="Search", service_instance_id="other-replica"),
                series(milvus_metric, "milvus", "0+600x20", status="fail", function_name="Search", service_namespace="other"),
                series(milvus_metric, "milvus", "0+1200x20", status="fail", function_name="Search", service_name="other"),
            ],
            "checks": [
                chart("milvus", milvus_failure, samples(3, function_name="Search")),
                chart("milvus", milvus_failure, samples(1, function_name="Search"), instance=True),
                monitor("milvus-request-failed-rate", health(3) + health(10, service_namespace="other") + health(20, service_name="other")),
            ],
        },
        {
            "name": "Missing Milvus counters do not invent health or chart values",
            "series": [],
            "checks": [
                chart("milvus", milvus_success, []), chart("milvus", milvus_failure, []),
                chart("milvus", milvus_count, []), monitor("milvus-request-failed-rate", []),
            ],
        },
    ])

    product = "kubeflow-pipelines"
    for name, success, failed, ratio in [
        ("success only", 4, None, 1), ("failure only", None, 2, 0),
        ("both outcomes", 3, 1, 0.75), ("no runs", 0, 0, None),
        ("no telemetry", None, None, None),
    ]:
        data = [series("resource_manager_workflow_runs_" + outcome, product, f"{value}+0x20")
                for outcome, value in [("success", success), ("failed", failed)] if value is not None]
        expected = [] if ratio is None else samples(ratio)
        cases.append({
            "name": "KFP run success ratio with " + name,
            "series": data,
            "checks": [
                chart(product, "run-success-rate", expected),
                chart(product, "run-outcomes", samples(success or 0) if data else [], query_alias="succeeded"),
                chart(product, "run-outcomes", samples(failed or 0) if data else [], query_alias="failed"),
            ],
        })
    cases.extend([
        {
            "name": "KFP sparse outcome totals do not mix services, namespaces or instances",
            "series": [
                series("resource_manager_workflow_runs_success", product, "3+0x20"),
                series("resource_manager_workflow_runs_failed", product, "1+0x20", service_instance_id="other-replica"),
                series("resource_manager_workflow_runs_failed", product, "100+0x20", service_namespace="other"),
                series("resource_manager_workflow_runs_failed", product, "100+0x20", service_name="other"),
            ],
            "checks": [chart(product, "run-success-rate", samples(0.75)), chart(product, "run-success-rate", samples(1), instance=True)],
        },
        {
            "name": "KFP gRPC success-only traffic has a zero error ratio and attached health",
            "series": [series("grpc_server_handled_total", product, grpc_code="OK")],
            "checks": [chart(product, "grpc-error-ratio", samples(0)), monitor("kfp-grpc-error-ratio", health(0))],
        },
        {
            "name": "KFP gRPC ratios isolate replicas and monitor identities",
            "series": [
                series("grpc_server_handled_total", product, "0+540x20", grpc_code="OK"),
                series("grpc_server_handled_total", product, grpc_code="Internal", service_instance_id="other-replica"),
                series("grpc_server_handled_total", product, grpc_code="Internal", service_namespace="other"),
            ],
            "checks": [
                chart(product, "grpc-error-ratio", samples(0.1)),
                chart(product, "grpc-error-ratio", samples(0), instance=True),
                monitor("kfp-grpc-error-ratio", health(0.1) + health(1, service_namespace="other")),
            ],
        },
        {
            "name": "KFP pod phase charts read current gauges, not historical transitions",
            "series": [
                series("argo_workflows_pods_gauge", product, "0+0x20", phase="Running"),
                series("argo_workflows_pods_gauge", product, "0+0x20", phase="Pending"),
                series("argo_workflows_pods_count_total", product, "5+0x20", phase="Running"),
                series("argo_workflows_pod_pending_count_total", product, "100+0x20", reason="ImagePullBackOff"),
            ],
            "checks": [
                chart(product, "pods-by-phase", samples(0, phase="Running") + samples(0, phase="Pending")),
                chart(product, "pending-pods", samples(0)), monitor("kfp-image-pull-failures", health(0)),
            ],
        },
        {
            "name": "KFP pod gauges preserve namespace, service and instance scope",
            "series": [
                series("argo_workflows_pods_gauge", product, "2+0x20", phase="Pending"),
                series("argo_workflows_pods_gauge", product, "3+0x20", phase="Running"),
                series("argo_workflows_pods_gauge", product, "7+0x20", phase="Pending", service_instance_id="other-replica"),
                series("argo_workflows_pods_gauge", product, "100+0x20", phase="Pending", service_namespace="other"),
                series("argo_workflows_pods_gauge", product, "100+0x20", phase="Pending", service_name="other"),
            ],
            "checks": [
                chart(product, "pending-pods", samples(9)), chart(product, "pending-pods", samples(2), instance=True),
                chart(product, "pods-by-phase", samples(9, phase="Pending") + samples(3, phase="Running")),
            ],
        },
        {
            "name": "KFP image pull health attaches to observed pods without prior pending errors",
            "series": [series("argo_workflows_pods_gauge", product, "0+0x20", phase="Pending")],
            "checks": [monitor("kfp-image-pull-failures", health(0))],
        },
        {
            "name": "KFP current image pull errors override the zero baseline",
            "series": [
                series("argo_workflows_pods_gauge", product, "1+0x20", phase="Pending"),
                series("argo_workflows_pod_pending_count_total", product, "0+1x20", reason="ErrImagePull"),
            ],
            "checks": [{**monitor("kfp-image-pull-failures", health(15)), "eval_time": "15m"}],
        },
        {
            "name": "KFP API counters cannot manufacture workflow-controller or absent gRPC data",
            "series": [series("run_server_run_count", product, "1+0x20")],
            "checks": [
                chart(product, "run-success-rate", []), chart(product, "grpc-error-ratio", []),
                chart(product, "pods-by-phase", []), chart(product, "pending-pods", []),
                monitor("kfp-grpc-error-ratio", []), monitor("kfp-image-pull-failures", []),
            ],
        },
    ])
    return cases


class ProductPresentationTest(unittest.TestCase):
    def test_highlights_match_product_operations_and_kubeflow_process_roles(self):
        prefix = "urn:stackpack:suse-ai:component-presentation:"
        common = BY_ID[prefix + "product-kubeflow-pipelines"]
        self.assertNotIn("highlight", common["presentation"])
        self.assertNotIn("service.name:", common["binding"]["query"])
        for role, service, metric in [
            ("api", "kubeflow-pipelines", "run-api-rate"),
            ("controller", "kubeflow-workflow-controller", "pods-by-phase"),
        ]:
            presentation = BY_ID[prefix + f"kubeflow-pipelines-{role}-highlights"]
            self.assertIn('label = "service.name:' + service + '"', presentation["binding"]["query"])
            refs = presentation["presentation"]["highlight"]["metrics"][0]["metrics"]
            self.assertIn("suse_ai_kubeflow_pipelines_" + metric.replace("-", "_"), [m["metricId"] for m in refs])
        milvus = BY_ID[prefix + "product-milvus"]["presentation"]["highlight"]["metrics"][0]["metrics"]
        self.assertEqual(milvus[0]["metricId"], "suse_ai_milvus_vectordb_system_search_latency")


@unittest.skipUnless(os.environ.get("AI_PROMETHEUS_IMAGE"), "Set AI_PROMETHEUS_IMAGE to run query evaluation")
class ProductPromQLTest(unittest.TestCase):
    def test_product_sparse_outcomes_and_identity_boundaries(self):
        result = run_promql_cases(product_cases())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
