#!/usr/bin/env bash
# Extract the unmodified x64 VC++ runtime files from Microsoft's redistributable.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="$root/app/Madeira/x86_64-vcruntime"
work="$(mktemp -d "${RUNNER_TEMP:-/tmp}/madeira-vcredist.XXXXXX")"
trap 'rm -rf "$work"' EXIT

command -v cabextract >/dev/null || { echo 'cabextract is required' >&2; exit 1; }
mkdir -p "$work/level0" "$work/level1" "$work/level2" "$dest"
curl --fail --location --retry 3 --output "$work/VC_redist.x64.exe" \
  'https://aka.ms/vs/17/release/vc_redist.x64.exe'
shasum -a 256 "$work/VC_redist.x64.exe"

# Microsoft changes the outer installer layout. CAB payloads can have opaque
# names and no CAB file signature, so try every non-DLL at each nested level.
# Select final files by PE machine type and certificate table, not size alone.
cabextract -q -L -d "$work/level0" "$work/VC_redist.x64.exe" || true
test -n "$(find "$work/level0" -type f -print -quit)" || {
  echo 'No CAB payload was extracted from the Microsoft installer' >&2
  exit 1
}
for level in 0 1; do
  next=$((level + 1))
  while IFS= read -r -d '' candidate; do
    [[ "$candidate" =~ \.[Dd][Ll][Ll]$ ]] && continue
    relative="${candidate#"$work/level$level/"}"
    output="$work/level$next/$relative.d"
    mkdir -p "$output"
    cabextract -q -L -d "$output" "$candidate" >/dev/null 2>&1 || true
  done < <(find "$work/level$level" -type f -print0)
done

python3 "$root/tools/verify-vcruntime.py" --extract "$work" --dest "$dest"
