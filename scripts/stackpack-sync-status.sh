#!/usr/bin/env bash
set -euo pipefail
sts_cmd=("${STS_BIN:-sts}")
if [[ -n "${STS_CONTEXT:-}" ]]; then sts_cmd+=(--context "$STS_CONTEXT"); fi
syncs=$("${sts_cmd[@]}" topology-sync list -o json)
printf '%s\n' "$syncs"
jq -e '.synchronizations | type == "array"' <<<"$syncs" >/dev/null
ids=$(jq -er '[.synchronizations[] .nodeId | numbers] | map(tostring) | join("\n")' <<<"$syncs")
# Native AI uses OTel mappings, not the three removed legacy Groovy syncs.
# Read every actual synchronization; cumulative counters are not active errors.
while IFS= read -r id; do
  [[ -n "$id" ]] || continue
  "${sts_cmd[@]}" topology-sync describe --id "$id" -o json
done <<<"$ids"
