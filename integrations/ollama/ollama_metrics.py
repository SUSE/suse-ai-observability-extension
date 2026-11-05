"""Expose read-only Ollama inventory and residency snapshots as Prometheus gauges."""

import argparse
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, HTTPRedirectHandler, build_opener


MAX_RESPONSE_BYTES = 1024 * 1024
FIELDS = {
    "size": ("ollama_model_size_bytes", "Model allocation reported by Ollama /api/ps in bytes."),
    "size_vram": ("ollama_model_vram_bytes", "Model GPU allocation reported by Ollama /api/ps in bytes."),
    "context_length": ("ollama_model_context_length", "Configured context length of the loaded Ollama model."),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(ProxyHandler({}), NoRedirect())


def gauge(name, description):
    return [f"# HELP {name} {description}", f"# TYPE {name} gauge"]


def label(value):
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def model_index(payload):
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise ValueError("Expected a models list")
    result = {}
    for model in models:
        if not isinstance(model, dict):
            raise ValueError("Expected a model object")
        name = model.get("name") or model.get("model")
        if not isinstance(name, str) or not name or name in result:
            raise ValueError("Expected a unique nonempty model name")
        result[name] = model
    return result


def number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError("Expected a nonnegative finite model allocation")
    return value


def render(payload, available_payload):
    loaded, available = model_index(payload), model_index(available_payload)
    lines = gauge("ollama_loaded_models", "Number of models currently loaded by this Ollama process.")
    lines.append(f"ollama_loaded_models {len(loaded)}")
    for field, (metric, description) in FIELDS.items():
        lines.extend(gauge(metric, description))
    for name, model in loaded.items():
        for field, (metric, _) in FIELDS.items():
            if field not in model:
                continue
            value = number(model[field])
            lines.append(f'{metric}{{model="{label(name)}"}} {value}')
    lines.extend(gauge("ollama_model_info", "Available model inventory reported by Ollama /api/tags."))
    lines.extend(gauge("ollama_model_loaded", "1 if the available model is loaded in this process, otherwise 0."))
    lines.extend(gauge("ollama_model_disk_size_bytes", "Available model size on disk reported by Ollama /api/tags."))
    for name, model in available.items():
        details = model.get("details", {})
        if not isinstance(details, dict):
            raise ValueError("Expected model details object")
        labels = {"model": name}
        for key, field in (("family", "family"), ("parameter_size", "parameter_size"),
                           ("quantization", "quantization_level")):
            value = details.get(field, "")
            if not isinstance(value, str):
                raise ValueError("Expected string model metadata")
            labels[key] = value
        dimensions = ",".join(f'{key}="{label(value)}"' for key, value in labels.items())
        lines.append(f"ollama_model_info{{{dimensions}}} 1")
        lines.append(f'ollama_model_loaded{{model="{label(name)}"}} {int(name in loaded)}')
        if "size" in model:
            lines.append(f'ollama_model_disk_size_bytes{{model="{label(name)}"}} {number(model["size"])}')
        if name not in loaded:
            lines.append(f'ollama_model_vram_bytes{{model="{label(name)}"}} 0')
    return lines


def collect(endpoint, timeout=5):
    lines = gauge("ollama_api_up", "1 when both local Ollama /api/ps and /api/tags snapshots are valid, otherwise 0.")

    def read(url):
        with OPENER.open(url, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("Unexpected response status")
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("Response too large")
        return json.loads(body)

    try:
        snapshot = render(read(endpoint), read(endpoint.removesuffix("/api/ps") + "/api/tags"))
    except (HTTPError, URLError, HTTPException, OSError, ValueError, TypeError, OverflowError):
        # No cached model values: an unavailable process must not look idle or healthy.
        lines.append("ollama_api_up 0")
    else:
        lines.append("ollama_api_up 1")
        lines.extend(snapshot)
    return ("\n".join(lines) + "\n").encode()


def handler(endpoint, timeout):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/healthz":
                body, content_type = b"ok\n", "text/plain"
            elif self.path == "/metrics":
                body, content_type = collect(endpoint, timeout), "text/plain; version=0.0.4; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--listen", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()
    parsed = urlsplit(args.ollama_url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        parser.error("--ollama-url must be an HTTP(S) origin without credentials or a path")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    endpoint = args.ollama_url.rstrip("/") + "/api/ps"
    ThreadingHTTPServer((args.listen, args.port), handler(endpoint, args.timeout)).serve_forever()


if __name__ == "__main__":
    main()
