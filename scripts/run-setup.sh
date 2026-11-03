#!/usr/bin/env bash
set -euo pipefail
# Development tasks retain the CLI's active context when no explicit auth is supplied.
if [[ -z "${STS_CONTEXT:-}" && -z "${STACKSTATE_API_URL:-}" ]]; then
  STS_CONTEXT=$("${STS_BIN:-sts}" context show -o json | jq -er '.name')
  export STS_CONTEXT
fi
version=$(sed -nE 's/^version: ([0-9]+\.[0-9]+\.[0-9]+)$/\1/p' stackpack/suse-ai/stackpack.yaml)
export SUSE_AI_ARCHIVE="$PWD/dist/suse-ai-$version.sts"
# Uses the same tested installation path as the setup container.
exec bash init.sh
