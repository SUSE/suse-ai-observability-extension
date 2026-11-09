"""Explicit failing, recovery and absent-input fixtures for every shipped monitor."""

import json

from test_contract import BY_ID


PREFIX = "urn:stackpack:suse-ai:monitor:"
IDENTITY = {"service_namespace": "prod-eu", "service_name": "assistant"}
MODEL = {"gen_ai_request_model": "llama3", "gen_ai_provider_name": "openai",
         "server_address": "vllm.ai.svc", "server_port": "8000"}


def labels(values):
    return "{" + ",".join(k + "=" + json.dumps(str(v)) for k, v in values.items()) + "}"


def point(metric, value, product="", counter=False, identity=None, **dimensions):
    tags = {**(IDENTITY if identity is None else identity), **dimensions}
    if product:
        tags["suse_ai_product"] = product
    return {"series": metric + labels(tags), "values": ("0+" if counter else "") + str(value) + ("x20" if counter else "+0x20")}


def histogram(metric, upper, product="", **dimensions):
    return [point(metric + "_bucket", 60, product, counter=True, le=bound, **dimensions)
            for bound in (str(upper), "+Inf")]


def recipes():
    result = {}
    def add(key, failing, recovering, fail_value, clear_value, identity=None, **options):
        result[key] = {"failing": failing, "recovering": recovering,
                       "values": (fail_value, clear_value), "identity": IDENTITY if identity is None else identity,
                       **options}

    for key, metric, product, failed, clear in (
        ("vllm-high-gpu-cache-usage", "vllm:kv_cache_usage_perc", "vllm", 0.95, 0.5),
        ("vllm-request-queue-buildup", "vllm:num_requests_waiting", "vllm", 20, 0),
        ("qdrant-high-memory-usage", "memory_active_bytes", "qdrant", 8589934592, 1048576),
        ("qdrant-high-rest-latency", "rest_responses_avg_duration_seconds", "qdrant", 3, 0.1),
        ("kfp-workflow-queue-lag", "argo_workflows_queue_longest_running", "kubeflow-pipelines", 600, 0),
        ("kubeflow-model-registry-slow", "httpcheck_duration_milliseconds", "kubeflow-model-registry", 2000, 100),
        ("kserve-reconcile-lag", "workqueue_longest_running_processor_seconds", "kserve", 120, 0),
    ):
        add(key, [point(metric, failed, product)], [point(metric, clear, product)], failed, clear)

    for key, metric, product, upper, percentile, divisor, dimensions, identity in (
        ("vllm-high-e2e-latency", "vllm_e2e_request_latency_seconds", "vllm", 100, 0.99, 1,
         {"model_name": "llama3"}, {**IDENTITY, "model_name": "llama3"}),
        ("vllm-high-ttft", "vllm_time_to_first_token_seconds", "vllm", 10, 0.99, 1,
         {"model_name": "llama3"}, {**IDENTITY, "model_name": "llama3"}),
        ("model-usage-latency", "gen_ai_client_operation_duration_seconds", "", 100, 0.95, 1,
         MODEL, {**IDENTITY, "gen_ai_request_model": "llama3"}),
        ("milvus-high-request-latency", "milvus_proxy_req_latency", "milvus", 10000, 0.99, 1000,
         {"function_name": "Search"}, IDENTITY),
        ("milvus-high-search-latency", "milvus_proxy_sq_latency", "milvus", 10000, 0.99, 1000, {}, IDENTITY),
        ("kserve-latency-p95", "request_predict_seconds", "kserve", 10, 0.95, 1, {}, IDENTITY),
    ):
        add(key, histogram(metric, upper, product, **dimensions), histogram(metric, 1, product, **dimensions),
            percentile * upper / divisor, percentile / divisor, identity=identity)

    for key, metric, product, label, failed, clear in (
        ("qdrant-grpc-api-failures", "grpc_responses_total", "qdrant", "status", "13", "0"),
        ("qdrant-rest-api-failures", "rest_responses_total", "qdrant", "status", "503", "200"),
        ("milvus-request-failed-rate", "milvus_proxy_req_count_total", "milvus", "status", "fail_system", "success"),
    ):
        add(key, [point(metric, 60, product, counter=True, **{label: failed})],
            [point(metric, 60, product, counter=True, **{label: clear})], 1, 0)

    for state in ("red", "yellow"):
        add("opensearch-cluster-" + state,
            [point("elasticsearch_cluster_health", 1, "opensearch", status=state)],
            [point("elasticsearch_cluster_health", 1, "opensearch", status="green")], 1, 0)

    for key, service in (("kfp-api-down", "kubeflow-pipelines"),
                         ("kfp-workflow-controller-down", "kubeflow-workflow-controller")):
        identity = {**IDENTITY, "service_name": service}
        add(key, [point("up", 0, "kubeflow-pipelines", identity=identity)],
            [point("up", 1, "kubeflow-pipelines", identity=identity)], 0, 1, identity=identity)

    for key, metric, product, dimension, bad, good, extra, identity in (
        ("application-span-error-ratio", "otel_span_calls_total", "", "status_code", "STATUS_CODE_ERROR", "STATUS_CODE_OK", {"span_kind": "SPAN_KIND_CLIENT"}, IDENTITY),
        ("kfp-grpc-error-ratio", "grpc_server_handled_total", "kubeflow-pipelines", "grpc_code", "Internal", "OK", {}, IDENTITY),
        ("kserve-error-rate", "controller_runtime_reconcile_total", "kserve", "result", "error", "success", {}, IDENTITY),
        ("model-usage-errors", "gen_ai_client_operation_duration_seconds_count", "", "error_type", "TimeoutError", "", MODEL,
         {**IDENTITY, "gen_ai_request_model": "llama3"}),
    ):
        add(key, [point(metric, 30, product, counter=True, **extra, **{dimension: status}) for status in (bad, good)],
            [point(metric, 60, product, counter=True, **extra, **{dimension: good})], 0.5, 0, identity=identity)

    add("kfp-image-pull-failures",
        [point("argo_workflows_pod_pending_count_total", 60, "kubeflow-pipelines", counter=True, reason="ImagePullBackOff")],
        [point("argo_workflows_pods_gauge", 1, "kubeflow-pipelines", phase="Running")], 900, 0, eval_time="20m")
    add("kfp-run-failures", [point("argo_workflows_count_total", 60, "kubeflow-pipelines", counter=True, phase="Failed")],
        [point("argo_workflows_count_total", 60, "kubeflow-pipelines", counter=True, phase="Succeeded")], 900, 0, eval_time="20m")
    add("kubeflow-model-registry-invalid-response",
        [point("httpcheck_validation_failed", 1, "kubeflow-model-registry", validation_type="contains")],
        [point("httpcheck_validation_passed", 1, "kubeflow-model-registry", validation_type="contains")], 1, 0)
    for key, product, extra in (("kubeflow-model-registry-unavailable", "kubeflow-model-registry", {}),
                                 ("http-probe-unavailable", "", {"suse_ai_observation_kind": "http-probe"})):
        add(key, [point("httpcheck_status", 0, product, http_status_class="2xx", **extra)],
            [point("httpcheck_status", 1, product, http_status_class="2xx", **extra)], 0, 1)
    node = {"k8s_cluster_name": "cluster-a", "k8s_node_name": "worker"}
    add("nvidia-xid-errors", [point("DCGM_FI_DEV_XID_ERRORS", 31, identity=node)],
        [point("DCGM_FI_DEV_XID_ERRORS", 0, identity=node)], 31, 0, identity=node)
    stale = point("gen_ai_client_operation_duration_seconds_count", 1)
    stale["values"] = "1 _x10"
    add("genai-metric-stream-active", [stale], [point("gen_ai_client_operation_duration_seconds_count", 1)],
        600, 0, eval_time="10m")
    ollama = {**IDENTITY, "k8s_cluster_name": "cluster-a", "service_instance_id": "pod-a"}
    add("ollama-model-unavailable", [point("ollama_api_up", 0, identity=ollama)],
        [point("ollama_api_up", 1, identity=ollama),
         point("ollama_model_loaded", 0, identity=ollama, model="llama3")],
        0, 1, identity={**IDENTITY, "k8s_cluster_name": "cluster-a", "model": "llama3"})
    return result


def matrix_cases():
    result = []
    for key, recipe in recipes().items():
        for index, state in enumerate(("failing", "recovering", "no-data")):
            result.append({"name": key + ": " + state,
                           "series": recipe.get(state, []),
                           "checks": [{"monitor": key, "eval_time": recipe.get("eval_time", "5m"),
                                       "samples": [] if state == "no-data" else [{
                                           "labels": labels(recipe["identity"]), "value": recipe["values"][index]}]}]})
    return result
