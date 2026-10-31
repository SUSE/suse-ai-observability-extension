"""Evaluate runtime observations against the real Prometheus engine."""

import os
import unittest

from test_product_metrics import INSTANCE, health, monitor, samples, series
from test_promql import run_promql_cases


def chart(presentation, metric, expected, **options):
    return {
        "presentation": presentation,
        "metric": "suse-ai-" + metric,
        "samples": expected,
        **options,
    }


def http_observations(statuses, **identity):
    """httpcheck emits five classes; only the matching class includes its code.

    Omitted old label sets deliberately remain within Prometheus's lookback.
    This reproduces the stale-success/stale-failure problem across code changes.
    """
    streams = {}
    for index, code in enumerate(statuses):
        for status_class in range(1, 6):
            matched = code is not None and code // 100 == status_class
            dimensions = {
                "k8s_cluster_name": "cluster-a",
                "suse_ai_observation_kind": "http-probe",
                "http_url": "http://runtime/api/tags",
                "http_status_class": f"{status_class}xx",
                **identity,
            }
            if matched:
                dimensions["http_status_code"] = str(code)
            key = tuple(sorted(dimensions.items()))
            streams.setdefault(key, ["_"] * len(statuses))[index] = "1" if matched else "0"
    return [series("httpcheck_status", "ollama", " ".join(values), **dict(dimensions))
            for dimensions, values in streams.items()]


def runtime_series(metric, values="1+0x20", **dimensions):
    return series("ollama_" + metric, "ollama", values, k8s_cluster_name="cluster-a", **dimensions)


def runtime_cases():
    cases = []
    # 200 -> HTTP failure -> different 2xx -> transport failure -> original 2xx.
    observations = http_observations([200, 503, 201, None, 200, 200])
    checks = []
    for minute, value in [(0, 1), (1, 0), (2, 1), (3, 0), (4, 1)]:
        checks.extend([
            chart("http-probes", "http-probe-success", samples(value), eval_time=f"{minute}m"),
            {**monitor("http-probe-unavailable", health(value)), "eval_time": f"{minute}m"},
        ])
    cases.append({"name": "HTTP latest observation wins across code changes, errors and recovery", "series": observations, "checks": checks})
    cases.extend([
        {
            "name": "HTTP independently tracks each endpoint and replica",
            "series": http_observations([200] * 6)
                      + http_observations([200, 503, 503, 503, 503, 503], service_instance_id="other-replica")
                      + http_observations([200] * 6, http_url="http://runtime/health"),
            "checks": [
                chart("http-probes", "http-probe-success", samples(0)),
                chart("http-probes", "http-probe-success", samples(1), instance=True),
                monitor("http-probe-unavailable", health(0)),
            ],
        },
        {
            "name": "HTTP failed endpoints cannot hide behind another URL's success",
            "series": http_observations([200] * 6)
                      + http_observations([503] * 6, http_url="http://runtime/health"),
            "checks": [chart("http-probes", "http-probe-success", samples(0)), monitor("http-probe-unavailable", health(0))],
        },
        {
            "name": "HTTP service and namespace identities remain separate",
            "series": http_observations([200] * 6)
                      + http_observations([503] * 6, service_namespace="other")
                      + http_observations([503] * 6, service_name="other"),
            "checks": [
                chart("http-probes", "http-probe-success", samples(1)),
                monitor("http-probe-unavailable", health(1) + health(0, service_namespace="other") + health(0, service_name="other")),
            ],
        },
        {
            "name": "HTTP unmarked observations cannot create endpoint-check health",
            "series": http_observations([200] * 6, suse_ai_observation_kind="other"),
            "checks": [chart("http-probes", "http-probe-success", []), monitor("http-probe-unavailable", [])],
        },
        {
            "name": "Absent HTTP observations stay absent",
            "series": [],
            "checks": [chart("http-probes", "http-probe-success", []), chart("http-probes", "http-probe-duration", []), monitor("http-probe-unavailable", [])],
        },
        {
            "name": "HTTP observations expire without fabricated recovery",
            "series": http_observations([503]),
            "checks": [
                chart("http-probes", "http-probe-success", [], eval_time="6m"),
                {**monitor("http-probe-unavailable", []), "eval_time": "6m"},
            ],
        },
    ])

    stale_metrics = [
        runtime_series("loaded_models", "1 _ _ _ _ _"),
        runtime_series("model_size_bytes", "100 _ _ _ _ _", model="model-a"),
        runtime_series("model_vram_bytes", "80 _ _ _ _ _", model="model-a"),
        runtime_series("model_context_length", "4096 _ _ _ _ _", model="model-a"),
    ]
    cases.append({
        "name": "Failed Ollama reads hide stale model observations immediately",
        "series": [runtime_series("api_up", "1 0 0 0 0 0")] + stale_metrics,
        "checks": [
            chart("product-ollama-runtime", "ollama-api-up", samples(0), eval_time="1m"),
            *[chart("product-ollama-runtime", "ollama-" + metric, [], eval_time="1m")
              for metric in ["loaded-models", "model-size", "model-vram", "model-context"]],
        ],
    })
    cases.append({
        "name": "Model observations without a successful Ollama API read remain absent",
        "series": stale_metrics,
        "checks": [chart("product-ollama-runtime", "ollama-" + metric, [], eval_time="1m")
                   for metric in ["api-up", "loaded-models", "model-size", "model-vram", "model-context"]],
    })
    data = []
    for replica, copies, model_data in [
        (INSTANCE, 2, [("model-a", 100, 80, 4096), ("model-b", 30, 0, 1024)]),
        ("other-replica", 1, [("model-a", 200, 180, 8192)]),
    ]:
        for scraper in ["scraper-a", "scraper-b"]:
            dimensions = {"service_instance_id": replica, "job": scraper}
            data.extend([runtime_series("api_up", **dimensions), runtime_series("loaded_models", f"{copies}+0x20", **dimensions)])
            for model, size, vram, context in model_data:
                for metric, value in [("model_size_bytes", size), ("model_vram_bytes", vram), ("model_context_length", context)]:
                    data.append(runtime_series(metric, f"{value}+0x20", model=model, **dimensions))
    for dimension in ["service_namespace", "service_name"]:
        foreign = {dimension: "other"}
        data.extend([runtime_series("api_up", **foreign), runtime_series("loaded_models", "100+0x20", **foreign)])
        for metric in ["model_size_bytes", "model_vram_bytes", "model_context_length"]:
            data.append(runtime_series(metric, "1000000+0x20", model="model-a", **foreign))
    cases.append({
        "name": "Ollama sums actual model copies and bytes once per replica while preserving context lengths",
        "series": data,
        "checks": [
            chart("product-ollama-runtime", "ollama-loaded-models", samples(3)),
            chart("product-ollama-runtime", "ollama-loaded-models", samples(2), instance=True),
            chart("product-ollama-runtime", "ollama-model-size", samples(300, model="model-a") + samples(30, model="model-b")),
            chart("product-ollama-runtime", "ollama-model-size", samples(100, model="model-a") + samples(30, model="model-b"), instance=True),
            chart("product-ollama-runtime", "ollama-model-vram", samples(260, model="model-a") + samples(0, model="model-b")),
            chart("product-ollama-runtime", "ollama-model-context", samples(4096, model="model-a", service_instance_id=INSTANCE)
                  + samples(8192, model="model-a", service_instance_id="other-replica")
                  + samples(1024, model="model-b", service_instance_id=INSTANCE)),
        ],
    })
    cases.append({
        "name": "Empty successful Ollama runtime reports zero copies without inventing models",
        "series": [runtime_series("api_up"), runtime_series("loaded_models", "0+0x20")],
        "checks": [
            chart("product-ollama-runtime", "ollama-loaded-models", samples(0)),
            *[chart("product-ollama-runtime", "ollama-" + metric, []) for metric in ["model-size", "model-vram", "model-context"]],
        ],
    })
    cases.append({
        "name": "Successful Ollama reads remove unloaded models while retaining current ones",
        "series": [
            runtime_series("api_up", "1 1 1"),
            runtime_series("loaded_models", "2 1 0"),
            *[runtime_series(family, "100 _ _", model="unloaded")
              for family in ["model_size_bytes", "model_vram_bytes", "model_context_length"]],
            *[runtime_series(family, "200 200 _", model="remaining")
              for family in ["model_size_bytes", "model_vram_bytes", "model_context_length"]],
        ],
        "checks": [
            chart("product-ollama-runtime", "ollama-loaded-models", samples(1), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-model-size", samples(200, model="remaining"), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-model-vram", samples(200, model="remaining"), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-model-context", samples(200, model="remaining", service_instance_id=INSTANCE), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-loaded-models", samples(0), eval_time="2m"),
            *[chart("product-ollama-runtime", "ollama-" + metric, [], eval_time="2m")
              for metric in ["model-size", "model-vram", "model-context"]],
        ],
    })
    cases.append({
        "name": "Latest Ollama read overrides an older duplicate scraper's up or down status",
        "series": [
            runtime_series("api_up", "1 _ _", job="old-scraper"),
            runtime_series("loaded_models", "9 _ _", job="old-scraper"),
            runtime_series("model_size_bytes", "900 _ _", model="model-a", job="old-scraper"),
            runtime_series("api_up", "_ 0 1", job="current-scraper"),
            runtime_series("loaded_models", "_ _ 1", job="current-scraper"),
            runtime_series("model_size_bytes", "_ _ 100", model="model-a", job="current-scraper"),
        ],
        "checks": [
            chart("product-ollama-runtime", "ollama-api-up", samples(0), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-loaded-models", [], eval_time="1m"),
            chart("product-ollama-runtime", "ollama-model-size", [], eval_time="1m"),
            chart("product-ollama-runtime", "ollama-api-up", samples(1), eval_time="2m"),
            chart("product-ollama-runtime", "ollama-loaded-models", samples(1), eval_time="2m"),
            chart("product-ollama-runtime", "ollama-model-size", samples(100, model="model-a"), eval_time="2m"),
        ],
    })
    cases.append({
        "name": "Recovered Ollama scraper is not held down by an older duplicate failure",
        "series": [
            runtime_series("api_up", "0 _ _", job="old-scraper"),
            runtime_series("api_up", "_ 1 1", job="new-scraper"),
            runtime_series("loaded_models", "_ 1 1", job="new-scraper"),
        ],
        "checks": [
            chart("product-ollama-runtime", "ollama-api-up", samples(1), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-loaded-models", samples(1), eval_time="1m"),
        ],
    })
    cases.append({
        "name": "Failed Ollama replica does not retain stale counts or hide healthy replica observations",
        "series": [
            runtime_series("api_up", "1 0 0"),
            runtime_series("loaded_models", "2 _ _"),
            runtime_series("api_up", "1 1 1", service_instance_id="healthy-replica"),
            runtime_series("loaded_models", "1 1 1", service_instance_id="healthy-replica"),
        ],
        "checks": [
            chart("product-ollama-runtime", "ollama-api-up", samples(0), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-loaded-models", samples(1), eval_time="1m"),
            chart("product-ollama-runtime", "ollama-loaded-models", [], eval_time="1m", instance=True),
        ],
    })
    return cases


@unittest.skipUnless(os.environ.get("AI_PROMETHEUS_IMAGE"), "Set AI_PROMETHEUS_IMAGE to run query evaluation")
class RuntimeObservationsTest(unittest.TestCase):
    def test_latest_probe_status_and_runtime_replica_scope(self):
        result = run_promql_cases(runtime_cases())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
