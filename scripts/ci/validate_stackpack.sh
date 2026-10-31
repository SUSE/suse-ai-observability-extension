#!/usr/bin/env bash
set -euo pipefail

stackpack_dir=$(realpath "${1:?StackPack directory is required}")
: "${VALIDATOR_IMAGE:?VALIDATOR_IMAGE must be set}"

docker run --rm --network none \
  --entrypoint /opt/docker/bin/stack-pack-validator \
  -v "${stackpack_dir}:/stackpack:ro,z" \
  "${VALIDATOR_IMAGE}" \
  -directory /stackpack
