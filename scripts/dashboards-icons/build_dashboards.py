#!/usr/bin/env python3
"""Build the four native dashboards from the verified demo metric vocabulary."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "stackpack/suse-ai/settings/dashboards"
PREFIX = "urn:stackpack:suse-ai:shared:dashboard:"
NAMES = {
    "overview": "Overview",
    "model-serving": "Model serving",
    "gateway-spend": "Gateway & spend",
    "gpu-fleet": "GPU fleet",
}
BLUE = "#1F78B4"
CLUSTER = 'k8s_cluster_name=~"${cluster}"'
CLIENT_COUNT = "gen_ai_client_operation_duration_seconds_count"
CLIENT_BUCKET = "gen_ai_client_operation_duration_seconds_bucket"
CLIENT_TOKENS = "gen_ai_client_token_usage_sum"
SERVER_ID = "k8s_cluster_name, service_namespace, service_name, service_instance_id"
DEVICE_ID = "k8s_cluster_name, UUID, k8s_node_name"
LITELLM_ID = (SERVER_ID + ", end_user, hashed_api_key, api_key_alias, team, team_alias, user, org_id, org_alias, "
              "requested_model, model, status_code, user_email, route, client_ip, user_agent, model_id, api_provider, "
              "exception_class, exception_status, le")
VLLM_ID = SERVER_ID + ", model_name, engine, finished_reason, le"


def selector(metric, extra="", offset=False, window=None):
    result = metric + "{" + CLUSTER + (", " + extra if extra else "") + "}"
    if window:
        result += "[" + window + "]"
    if offset:
        result += " offset 1h"
    return result


def rate(metric, extra="", offset=False):
    return "rate(" + selector(metric, extra, offset, "5m") + ")"


def client_rate(offset=False):
    return "60 * sum(" + rate(CLIENT_COUNT, offset=offset) + ")"


def client_p95(offset=False, by=""):
    group = by + ", le" if by else "le"
    return "histogram_quantile(0.95, sum by (" + group + ") (" + rate(CLIENT_BUCKET, offset=offset) + "))"


def product_rate(metric, identity, offset=False, by=""):
    aggregation = "sum by (" + by + ")" if by else "sum"
    return aggregation + " (max by (" + identity + ") (" + rate(metric, offset=offset) + "))"


def gateway_rate(offset=False, by=""):
    return "60 * " + product_rate("litellm_proxy_requests_metric_total", LITELLM_ID, offset, by)


def gateway_errors(offset=False):
    total = product_rate("litellm_proxy_requests_metric_total", LITELLM_ID, offset)
    failures = product_rate("litellm_proxy_failed_requests_metric_total", LITELLM_ID, offset)
    # Zero errors requires observed traffic; absent or idle traffic remains unknown.
    return "100 * (" + failures + " or (0 * " + total + ")) / (" + total + " > 0)"


def gateway_p95(offset=False, by=""):
    group = by + ", le" if by else "le"
    return "histogram_quantile(0.95, " + product_rate("litellm_request_total_latency_metric_bucket", LITELLM_ID, offset, group) + ")"


def spend_rate(offset=False, by=""):
    return "3600 * " + product_rate("litellm_spend_metric_total", LITELLM_ID, offset, by)


def vllm_p95(offset=False, by=""):
    group = by + ", le" if by else "le"
    return "histogram_quantile(0.95, " + product_rate("vllm:time_to_first_token_seconds_bucket", VLLM_ID, offset, group) + ")"


def ollama(metric, offset=False, by_model=False):
    group = SERVER_ID + (", model" if by_model else "")
    return "max by (" + group + ") (" + selector(metric, offset=offset) + ")"


def device(metric, offset=False):
    # Whole physical GPUs only. UUID is verified in the demo; exclude missing IDs and MIG slices.
    return "max by (" + DEVICE_ID + ") (" + selector(metric, 'UUID!="", GPU_I_ID=""', offset) + ")"


def memory_percent(offset=False):
    used = device("DCGM_FI_DEV_FB_USED", offset)
    free = device("DCGM_FI_DEV_FB_FREE", offset)
    return "100 * " + used + " / ((" + used + " + " + free + ") > 0)"


def query(expression, alias):
    return {"kind": "TimeSeriesQuery", "spec": {"plugin": {
        "kind": "PrometheusTimeSeriesQuery", "spec": {"query": expression, "alias": alias}
    }}}


def panel(title, kind, plugin, queries=(), description=""):
    return {"spec": {"display": {"name": title, "description": description},
                     "plugin": {"kind": kind, "spec": plugin},
                     "queries": list(queries), "links": []}}


def markdown(title, text):
    return panel(title, "Markdown", {"text": text})


def stat(title, expression, unit="short", decimals=1, description="", thresholds=None):
    return panel(title, "StatChart", {
        "calculation": "last", "format": {"unit": unit, "decimalPlaces": decimals},
        "sparkline": True, "thresholds": thresholds or {"defaultColor": BLUE, "steps": []},
    }, [query(expression, "Now")], description)


def comparison(title, expression, unit="short", description="", decimals=1):
    return panel(title + " — now vs 1 hour ago", "TimeSeriesChart", {
        "yAxis": {"show": True, "min": 0, "format": {"unit": unit, "decimalPlaces": decimals}},
        "legend": {"show": True, "position": "bottom", "mode": "list", "values": []},
        "visual": {"connectNulls": False},
    # The installed renderer uses a fixed palette and ignores per-query styling.
    # Aggregate comparisons have one series per query: history gets pale blue,
    # Now gets dark blue and is drawn last. Missing history stays missing.
    }, [query(expression(True), "1h ago"), query(expression(False), "Now")],
        description + " Dark blue is Now when both periods have data. The previous hour is shifted forward; gaps remain gaps.")


def trend(title, expression, unit="short", alias="", description="", decimals=1):
    """Keep entity comparisons readable without unsupported per-query colors."""
    return panel(title, "TimeSeriesChart", {
        "yAxis": {"show": True, "min": 0, "format": {"unit": unit, "decimalPlaces": decimals}},
        "legend": {"show": True, "position": "bottom", "mode": "list", "values": []},
        "visual": {"connectNulls": False},
    }, [query(expression(False), alias)], description + " Current selected time window; no shifted historical series.")


def short_identity(expression, source, target, pattern="(.{8}).*"):
    # Add a compact display label without dropping the full identity used for
    # deduplication or merging distinct replicas/devices.
    return 'label_replace(' + expression + ', "' + target + '", "$1", "' + source + '", "' + pattern + '")'


def gateway_model_legend(expression):
    # Add display metadata after aggregation, preserving original labels and values.
    # Non-model routes such as /metrics may omit requested_model entirely.
    return (f'label_replace(label_replace({expression}, '
            '"suse_ai_requested_model", "$1", "requested_model", "(.+)"), '
            '"suse_ai_requested_model", "Model not reported", "requested_model", "^$")')


def dashboard(slug, about, how, stats, charts, note, matchers):
    nav = " · ".join("**" + name + "**" if slug == key else "[" + name + "](/#/dashboards/" + PREFIX + key + ")"
                     for key, name in NAMES.items())
    panels = {"about": markdown("About / How to read", nav + "\n\n" + about
                               + " **How to read:** " + how)}
    items = []

    def place(key, x, y, width, height):
        items.append({"x": x, "y": y, "width": width, "height": height,
                      "content": {"$ref": "#/spec/panels/" + key}})

    place("about", 0, 0, 24, 1)
    for i, (key, value) in enumerate(stats):
        panels[key] = value
        place(key, 6 * i, 1, 6, 2)
    for i, (key, value) in enumerate(charts):
        panels[key] = value
        place(key, 12 * (i % 2), 3 + 3 * (i // 2), 12, 3)
    panels["coverage"] = markdown("Coverage / Next steps", note)
    place("coverage", 0, 3 + 3 * ((len(charts) + 1) // 2), 24, 1)
    variables = []
    if matchers:
        variables.append({"kind": "ListVariable", "spec": {
            "name": "cluster", "display": {"name": "Cluster", "description": "Cluster reporting these metrics."},
            "allowMultiple": False, "allowAllValue": False, "sort": "alphabetical-asc",
            "plugin": {"kind": "MetricLabelValues", "spec": {"labelName": "k8s_cluster_name", "matchers": matchers}},
        }})
    return {"nodes": [{"_type": "Dashboard", "identifier": PREFIX + slug,
                        "name": "SUSE AI — " + NAMES[slug], "description": about,
                        "dashboard": {"metadata": {"project": '{"saveVariables":false}'},
                                      "spec": {"panels": panels, "layouts": [{"kind": "Grid", "spec": {"items": items}}],
                                               "variables": variables}}}]}


def build():
    client_scope = "Client observations across instrumented callers; a user request may create several model calls."
    coverage = ("**Source coverage:** LiteLLM reports gateway traffic and cost; vLLM reports server request and token metrics; "
                "Ollama reports loaded models; client GenAI metrics report caller experience; DCGM reports GPU usage. "
                "These are separate observation points: do not sum their request or token counts. "
                "A missing line means no usable samples; an idle histogram has no meaningful percentile. "
                "New sources may have no hour-ago history.")
    overview = dashboard("overview",
        "Are AI calls completing promptly, and is serving capacity under pressure?",
        "Start with Right now, then compare the same five-minute window with one hour earlier. "
        "Blue values describe load; they do not assert health. Gaps mean no usable samples or no traffic.",
        [
            ("gateway-requests", stat("Gateway requests / min", gateway_rate(), description="LiteLLM proxy requests, including failures.")),
            ("gateway-failed", stat("Gateway failed (%)", gateway_errors(), "percent", 2,
                "LiteLLM failures divided by proxy requests. Idle traffic has no error percentage.")),
            ("client-latency", stat("Client duration p95", client_p95(), "s", 2,
                "P95 of observed client operations, including failed calls; not server TTFT.")),
            ("gpu-util", stat("Mean GPU utilization", "avg(" + device("DCGM_FI_DEV_GPU_UTIL") + ")", "percent", 1,
                "Equal-weight average of reported physical GPUs, deduplicated by cluster and device.")),
        ], [
            ("calls-compare", comparison("Client calls / min", client_rate, description=client_scope)),
            ("vllm-tokens-compare", comparison("vLLM generated tokens / s",
                lambda past: product_rate("vllm:generation_tokens_total", VLLM_ID, past),
                description="Server-side output throughput, separate from caller token observations.")),
            ("models-compare", comparison("Ollama loaded model replicas", lambda past: "sum(" + ollama("ollama_loaded_models", past) + ")",
                description="Loaded models summed across serving replicas; the same model on two replicas counts twice.", decimals=0)),
            ("gpu-compare", comparison("Mean GPU utilization", lambda past: "avg(" + device("DCGM_FI_DEV_GPU_UTIL", past) + ")", "percent",
                description="Compare utilization with calls and latency before deciding to add capacity.")),
        ], coverage, [CLIENT_COUNT, "ollama_api_up", "DCGM_FI_DEV_GPU_UTIL", "litellm_proxy_requests_metric_total", "vllm:generation_tokens_total"])

    callers = "service_namespace, service_name, gen_ai_provider_name, gen_ai_request_model"
    caller_alias = "${service_namespace}/${service_name} · ${gen_ai_provider_name}/${gen_ai_request_model}"
    server_alias = "${model} · ${service_namespace}/${service_name} · ${suse_ai_replica}"
    vllm_group = "service_namespace, service_name, model_name"
    vllm_alias = "${service_namespace}/${service_name} · ${model_name}"
    serving = dashboard("model-serving",
        "Compare vLLM serving latency and throughput, Ollama residency, and client GenAI experience.",
        "Client duration includes the caller-to-provider path. Model names remain as reported; caller names "
        "are not joined to server inventory. Ollama memory and context describe loaded models, not token throughput.",
        [
            ("vllm-finished", stat("vLLM finished requests / min", "60 * " + product_rate("vllm:request_success_total", VLLM_ID),
                description="All observed finish reasons, including abort/error; the metric name alone does not imply success.")),
            ("vllm-ttft", stat("vLLM first token p95", vllm_p95(), "s", 2,
                "Histogram estimate over five minutes. Bucket boundaries can keep p95 flat even when individual requests vary; idle histograms have no percentile.")),
            ("loaded-models", stat("Ollama loaded model replicas", "sum(" + ollama("ollama_loaded_models") + ")", decimals=0,
                description="Loaded-model count across live serving replicas, not available disk inventory.")),
            ("client-latency", stat("Client duration p95", client_p95(), "s", 2,
                "Caller-to-provider duration including failed calls; separate from server first-token latency.")),
        ], [
            ("vllm-ttft-compare", trend("vLLM first token p95 by model", lambda past: vllm_p95(past, vllm_group), "s", vllm_alias,
                "Histogram estimate: a flat percentile can reflect bucket resolution, not identical request durations.", 3)),
            ("vllm-tokens", trend("vLLM generated tokens / s",
                lambda past: product_rate("vllm:generation_tokens_total", VLLM_ID, past, vllm_group), "short", vllm_alias,
                "Aggregate real serving replicas after deduplicating scrape copies.")),
            ("caller-latency", trend("Client p95 by caller and model", lambda past: client_p95(past, callers), "s", caller_alias,
                "Use caller and requested-model labels to locate slow observations.", 2)),
            ("client-tokens", trend("Client input / output tokens per second",
                lambda past: "sum by (" + callers + ", gen_ai_token_type) (" + rate(CLIENT_TOKENS, offset=past) + ")",
                "short", caller_alias + " · ${gen_ai_token_type}", "Rates use the token histogram sum, not its observation count.")),
            ("ollama-vram", trend("Ollama model VRAM", lambda past: short_identity(ollama("ollama_model_vram_bytes", past, True),
                "service_instance_id", "suse_ai_replica"), "bytes", server_alias,
                "Per loaded model and serving replica. Missing model series does not establish deletion or zero memory.", 2)),
            ("vllm-ttft-total-compare", comparison("vLLM first token p95", vllm_p95, "s", description=
                "All observed vLLM models. Histogram interpolation can produce a flat p95 within a broad bucket.", decimals=3)),
        ], "**Investigate:** compare first-token latency and output throughput on vLLM, then caller latency by model. "
           "For Ollama, check loaded-model count and VRAM before investigating model residency. "
           "**Histogram resolution:** if all requests land in the 40–60 ms bucket, p95 is estimated at 59 ms. "
           "That does not mean every request took 59 ms. Replica labels show the first eight identity characters. "
           "The verified vLLM inventory did not expose queue or KV-cache gauges, so these panels do not infer them.\n\n" + coverage,
        [CLIENT_COUNT, "ollama_api_up", "vllm:generation_tokens_total"])

    gpu_alias = "${k8s_node_name} · ${suse_ai_device}"
    gpu_trend = lambda expression: short_identity(expression, "UUID", "suse_ai_device", "GPU-(.{8}).*")
    gpus = dashboard("gpu-fleet",
        "Locate busy, memory-constrained or hot physical GPUs using DCGM telemetry.",
        "Each device is identified by cluster and UUID; repeated pod/scrape copies are deduplicated. "
        "MIG slices and missing UUIDs are excluded. Legends show node and the first eight GPU UUID characters. "
        "Use Overview for the fleet's hour-ago utilization comparison. "
        "Utilization is a capacity signal, not a health verdict.",
        [
            ("gpu-count", stat("Reported physical GPUs", "count(" + device("DCGM_FI_DEV_GPU_UTIL") + ")", decimals=0,
                description="Distinct reporting device identities. Missing exporters are not counted as healthy or as zero devices.")),
            ("gpu-util", stat("Mean GPU utilization", "avg(" + device("DCGM_FI_DEV_GPU_UTIL") + ")", "percent", 1,
                "Average of reported physical-device utilization percentages.")),
            ("gpu-temp", stat("Highest GPU temperature", "max(" + device("DCGM_FI_DEV_GPU_TEMP") + ")", "celsius", 1,
                "Highest reported temperature. Thermal limits vary by hardware; no universal alarm threshold is assumed.")),
            ("gpu-power", stat("Fleet power", "sum(" + device("DCGM_FI_DEV_POWER_USAGE") + ")", "watt", 1,
                "Sum after physical-device deduplication, in watts; this is not an electricity bill.")),
        ], [
            ("util-by-gpu", trend("GPU utilization", lambda past: gpu_trend(device("DCGM_FI_DEV_GPU_UTIL", past)), "percent", gpu_alias,
                "Per-device utilization. Pod attribution does not provide hardware isolation.")),
            ("memory-by-gpu", trend("Framebuffer used", lambda past: gpu_trend(memory_percent(past)), "percent", gpu_alias,
                "100 × used / (used + free), using DCGM MiB gauges. Reserved memory is outside this denominator.")),
            ("temp-by-gpu", trend("GPU temperature", lambda past: gpu_trend(device("DCGM_FI_DEV_GPU_TEMP", past)), "celsius", gpu_alias,
                "Check cooling and vendor limits when temperature rises with load.")),
            ("power-by-gpu", trend("GPU power", lambda past: gpu_trend(device("DCGM_FI_DEV_POWER_USAGE", past)), "watt", gpu_alias,
                "Compare power with utilization before investigating idle allocation.")),
        ], "**Readout:** compare rising memory usage with loaded models, then temperature with power. "
           "Open the GPU inventory to inspect workload allocation.\n\n**Coverage:** these panels use verified DCGM device gauges. "
           "The demo did not report XID or ECC series, so this dashboard makes no claim that hardware errors are absent. "
           "This family expects the verified uppercase UUID label; a different exporter label contract needs validation.",
        ["DCGM_FI_DEV_GPU_UTIL"])

    gateway_group = "service_namespace, service_name, requested_model"
    gateway_alias = "${service_namespace}/${service_name} · ${suse_ai_requested_model}"
    gateway = dashboard("gateway-spend",
        "Track LiteLLM gateway demand, failures, latency and reported spend by requested model.",
        "All rates use five minutes. Spend / h extrapolates the reported five-minute cost rate; it is not a bill or "
        "a prediction. LiteLLM prices are expressed in USD; verify configured model prices. Zero reported spend does not "
        "establish that compute is free. New telemetry may have no hour-ago baseline.",
        [
            ("gateway-requests", stat("Gateway requests / min", gateway_rate(), description="LiteLLM proxy requests, including failures.")),
            ("gateway-failed", stat("Gateway failed (%)", gateway_errors(), "percent", 2,
                "Failure counter divided by all proxy requests. No traffic gives no percentage.")),
            ("gateway-latency", stat("Gateway duration p95", gateway_p95(), "s", 2,
                "P95 of reported end-to-end proxy durations; an idle histogram remains undefined.")),
            ("gateway-spend", stat("Reported spend / h (USD)", spend_rate(), "currencyUSD", 4,
                "3600 × the five-minute rate of LiteLLM reported spend. Counter resets are handled before aggregation.")),
        ], [
            ("requests-compare", trend("Requests / min by outcome", lambda past: gateway_model_legend(gateway_rate(past, gateway_group + ", status_code")),
                "short", gateway_alias + " · HTTP ${status_code}", "Compare model routes and status codes before examining the backend.")),
            ("latency-compare", trend("Gateway duration p95", lambda past: gateway_model_legend(gateway_p95(past, gateway_group)), "s", gateway_alias,
                "Measured total request latency by requested model.", 2)),
            ("spend-compare", trend("Reported spend / h (USD)", lambda past: gateway_model_legend(spend_rate(past, gateway_group)), "currencyUSD", gateway_alias,
                "Configured model prices determine reported spend; this does not include GPU infrastructure costs.", 4)),
            ("tokens-compare", trend("Gateway tokens / s",
                lambda past: gateway_model_legend(product_rate("litellm_tokens_metric_total", LITELLM_ID, past, gateway_group)), "short", gateway_alias,
                "LiteLLM token observations, separate from client and inference-server counters.")),
        ], "**Investigate:** high failure rates → inspect status codes and the routed model; high latency → compare with "
           "Model serving. Rising reported spend → compare tokens and model pricing.\n\n"
           "**Aggregation:** native request dimensions and serving replica identity survive scrape deduplication, "
           "then totals are grouped by service and requested model. No per-user or API-key values appear in chart legends. "
           "Model not reported means the series has no requested model, including non-model endpoints. "
           "Missing data remains unknown; zero spend reflects only what LiteLLM reported.",
        ["litellm_proxy_requests_metric_total"])
    return {"overview": overview, "model-serving": serving, "gateway-spend": gateway, "gpu-fleet": gpus}


class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for slug, data in build().items():
        path = DESTINATION / (slug + ".sty")
        path.write_text("# Generated by scripts/dashboards-icons/build_dashboards.py; edit that source.\n"
                        + yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=120))
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
