#!/usr/bin/env python3
"""Evaluate shipped dashboard expressions with the repository's pinned Prometheus."""

import os
from pathlib import Path
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]


def expression(dashboard, panel, index=None):
    data = yaml.safe_load((ROOT / "stackpack/suse-ai/settings/dashboards" / (dashboard + ".sty")).read_text())
    queries = data["nodes"][0]["dashboard"]["spec"]["panels"][panel]["spec"]["queries"]
    if index is None:
        index = next(i for i, q in enumerate(queries) if "offset 1h" not in q["spec"]["plugin"]["spec"]["query"])
    return queries[index]["spec"]["plugin"]["spec"]["query"].replace("${cluster}", "fixture")


def check(query, value=None, time="70m"):
    return {"expr": query, "eval_time": time, "exp_samples": [] if value is None else [{"labels": "{}", "value": value}]}


def series(metric, labels, values="0+60x70"):
    return {"series": metric + "{" + labels + "}", "values": values}


def main():
    identity = 'k8s_cluster_name="fixture",service_namespace="ai",service_name="gateway",requested_model="chat"'
    requests = "litellm_proxy_requests_metric_total"
    calls = expression("gateway-spend", "gateway-requests")
    failed = expression("gateway-spend", "gateway-failed")
    spend = expression("gateway-spend", "gateway-spend")
    tests = [
        {"name": "Scrape copies collapse; users and replicas remain additive", "interval": "1m", "input_series": [
            series(requests, identity + ',service_instance_id="a",end_user="one",job="scrape-a"'),
            series(requests, identity + ',service_instance_id="a",end_user="one",job="scrape-b"'),
            series(requests, identity + ',service_instance_id="a",end_user="two",job="scrape-a"', "0+120x70"),
            series(requests, identity + ',service_instance_id="b",end_user="one",job="scrape-a"', "0+180x70"),
            series(requests, identity.replace('"fixture"', '"other"') + ',service_instance_id="a"', "0+600x70"),
        ], "promql_expr_test": [check(calls, 360), check(failed, 0), check(spend)]},
        {"name": "Missing or idle traffic never becomes a healthy error percentage", "interval": "1m", "input_series": [
            series(requests, identity + ',service_instance_id="a"', "0+0x70"),
        ], "promql_expr_test": [check(calls, 0), check(failed), check(spend)]},
        {"name": "No sources stays unknown", "interval": "1m", "input_series": [],
         "promql_expr_test": [check(calls), check(failed), check(spend), check(expression("gpu-fleet", "gpu-count"))]},
        {"name": "A reported failure is counted once despite duplicate scrapes", "interval": "1m", "input_series": [
            series(requests, identity + ',service_instance_id="a"', "0+600x70"),
            series("litellm_proxy_failed_requests_metric_total", identity + ',service_instance_id="a",exception_class="Timeout",job="one"'),
            series("litellm_proxy_failed_requests_metric_total", identity + ',service_instance_id="a",exception_class="Timeout",job="two"'),
        ], "promql_expr_test": [check(failed, 10)]},
        {"name": "Physical GPUs are not multiplied by pod attribution or other clusters", "interval": "1m", "input_series": [
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",UUID="gpu-a",k8s_node_name="n1",pod_name="p1"', "20+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",UUID="gpu-a",k8s_node_name="n1",pod_name="p2"', "20+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",UUID="gpu-b",k8s_node_name="n2"', "60+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="other",UUID="gpu-a",k8s_node_name="n1"', "100+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",UUID="gpu-a",k8s_node_name="n1",GPU_I_ID="1"', "90+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",k8s_node_name="n1"', "90+0x70"),
        ], "promql_expr_test": [check(expression("gpu-fleet", "gpu-count"), 2), check(expression("gpu-fleet", "gpu-util"), 40)]},
        {"name": "An hour-ago comparison evaluates the earlier five-minute window", "interval": "1m", "input_series": [
            series("vllm:generation_tokens_total", 'k8s_cluster_name="fixture",service_instance_id="a",model_name="chat",engine="0"',
                   "0+60x60 3720+120x9"),
        ], "promql_expr_test": [check(expression("overview", "vllm-tokens-compare"), 2),
                               check(expression("overview", "vllm-tokens-compare", 0), 1)]},
        {"name": "Compact legends preserve replica and physical-device identity", "interval": "1m", "input_series": [
            series("ollama_model_vram_bytes", 'k8s_cluster_name="fixture",service_instance_id="aaaaaaaa-1",model="chat",job="one"', "100+0x70"),
            series("ollama_model_vram_bytes", 'k8s_cluster_name="fixture",service_instance_id="aaaaaaaa-1",model="chat",job="two"', "100+0x70"),
            series("ollama_model_vram_bytes", 'k8s_cluster_name="fixture",service_instance_id="aaaaaaaa-2",model="chat",job="one"', "200+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",UUID="GPU-aaaaaaaa-1",k8s_node_name="node",pod_name="one"', "20+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",UUID="GPU-aaaaaaaa-1",k8s_node_name="node",pod_name="two"', "20+0x70"),
            series("DCGM_FI_DEV_GPU_UTIL", 'k8s_cluster_name="fixture",UUID="GPU-aaaaaaaa-2",k8s_node_name="node"', "60+0x70"),
        ], "promql_expr_test": [check("sum(" + expression("model-serving", "ollama-vram") + ")", 300),
                               check("count(" + expression("model-serving", "ollama-vram") + ")", 2),
                               check("count(" + expression("gpu-fleet", "util-by-gpu") + ")", 2),
                               check("sum(" + expression("gpu-fleet", "util-by-gpu") + ")", 80)]},
    ]
    with tempfile.TemporaryDirectory(prefix="suse-ai-dashboard-promql-") as directory:
        path = Path(directory)
        path.chmod(0o755)
        (path / "tests.yaml").write_text(yaml.safe_dump({"evaluation_interval": "1m", "fuzzy_compare": True, "tests": tests}))
        result = subprocess.run([
            os.environ.get("CONTAINER_RUNTIME", "podman"), "run", "--rm", "--network", "none",
            "--entrypoint", "/bin/promtool", "-v", str(path) + ":/test:ro,z",
            os.environ["AI_PROMETHEUS_IMAGE"], "test", "rules", "/test/tests.yaml",
        ], check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    print(f"{len(tests)} dashboard query scenarios passed with pinned Prometheus")


if __name__ == "__main__":
    main()
