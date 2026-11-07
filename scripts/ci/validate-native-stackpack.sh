#!/usr/bin/env bash
set -euo pipefail
source scripts/ci/stackpack-images.env
bash scripts/ci/validate_stackpack.sh "${STACKPACK_SOURCE:-stackpack/suse-ai}"
output=$(mktemp)
trap 'rm -f "$output"' EXIT
if bash scripts/ci/validate_stackpack.sh tests/fixtures/invalid-component-mapping >"$output" 2>&1; then
  cat "$output"
  echo 'Validator accepted an invalid mapping' >&2
  exit 1
fi
cat "$output"
grep -q 'undeclared.*undeclaredValidationControl' "$output"
