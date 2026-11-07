#!/usr/bin/env python3
"""Read metrics only through the supplied sts wrapper; never mutate the backend."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]


def literal(value):
    # Groovy single-quoted strings do not interpolate PromQL's dollar signs.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r") + "'"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cluster", default="suse-ai")
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    if not args.sts.is_file():
        parser.error("--sts must name an explicit existing wrapper")
    args.output.mkdir(parents=True, exist_ok=False)
    requests = []
    if args.inventory:
        names = '{__name__=~"vllm.*|ollama.*|gen_ai.*|litellm.*|DCGM.*"}'
        requests = [
            ("names-now", "count by (__name__) (" + names + ")", False),
            ("names-one-hour-ago", "count by (__name__) (" + names + " offset 1h)", False),
            ("names-seven-days", "count by (__name__) (last_over_time(" + names + "[7d]))", False),
        ]
    else:
        cluster = json.dumps(re.escape(args.cluster))[1:-1]
        for path in sorted((ROOT / "stackpack/suse-ai/settings/dashboards").glob("*.sty")):
            spec = yaml.safe_load(path.read_text())["nodes"][0]["dashboard"]["spec"]
            for key, panel in spec["panels"].items():
                for index, query in enumerate(panel["spec"].get("queries", [])):
                    expression = query["spec"]["plugin"]["spec"]["query"].replace("${cluster}", cluster)
                    requests.append((path.stem + "-" + key + "-" + str(index), expression, True))

    def read(request):
        name, expression, ranged = request
        script = "Telemetry." + ("promql" if ranged else "instantPromql") + "(" + literal(expression) + ")"
        if ranged:
            script += ".start('-15m').step('1m')"
        # Returning a stream directly raises HTTP 500 on the inspected backend.
        script += ".collectStream(10000)"
        command = [str(args.sts.resolve()), "script", "run", "--script", script, "-o", "json"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
        (args.output / (name + ".json")).write_text(result.stdout)
        record = {"name": name, "query": expression, "exit_code": result.returncode}
        if result.returncode:
            (args.output / (name + ".error.txt")).write_text(result.stderr)
            return {**record, "error": result.stderr.strip()}
        payload = json.loads(result.stdout)
        values = payload["result"]["value"]
        points = [point[1] for value in values for point in value["timeSeries"]["points"]]
        return {**record, "series": len(values), "points": len(points),
                "finite_points": sum(isinstance(value, (int, float)) and math.isfinite(value) for value in points)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(read, requests))
    summary = {"observed_at": datetime.now(timezone.utc).isoformat(), "cluster": args.cluster,
               "read_only": True, "query_count": len(results), "results": results}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for result in results:
        print(result["name"], "ERROR" if result["exit_code"] else
              f'{result["series"]} series; {result["finite_points"]}/{result["points"]} finite samples')
    if any(result["exit_code"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
