#!/usr/bin/env bash
# Offline release packaging; GNU coreutils/findutils and Info-ZIP are sufficient.
set -euo pipefail
export LC_ALL=C TZ=UTC
unset ZIPOPT
umask 022

source_dir=$(realpath "${1:-stackpack/suse-ai}")
mkdir -p "${2:-dist}"
output_dir=$(realpath "${2:-dist}")
version=$(sed -nE 's/^version: ([0-9]+\.[0-9]+\.[0-9]+)$/\1/p' "$source_dir/stackpack.yaml")
[[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || {
  echo 'Expected one stable version in stackpack.yaml' >&2; exit 1;
}
grep -qx 'name: suse-ai' "$source_dir/stackpack.yaml"

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir "$stage/source"
for entry in README.md stackpack.yaml settings resources icons includes; do
  [[ -e "$source_dir/$entry" ]] || { echo "Missing $entry" >&2; exit 1; }
  cp -R "$source_dir/$entry" "$stage/source/"
done
cd "$stage/source"
if [[ -n "$(find . ! -type f ! -type d -print)" ]]; then
  echo 'StackPack must contain only regular files and directories' >&2; exit 1
fi
find . -type d -exec chmod 0755 {} +
find . -type f -exec chmod 0644 {} +
# Fixed ZIP epoch, independent of checkout times, host timezone and source modes.
find . -exec touch -h -d '@315532800' {} +
# Stored entries avoid compressor-version differences. No directory or extra fields.
find README.md stackpack.yaml settings resources icons includes -type f -print |
  sort | zip -q -X -0 "$stage/suse-ai-$version.sts" -@
install -m 0644 "$stage/suse-ai-$version.sts" "$output_dir/suse-ai-$version.sts"
cd "$output_dir"
sha256sum suse-ai-*.sts > SHA256SUMS
sha256sum --check SHA256SUMS
