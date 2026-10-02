#!/bin/bash
# Rebuild the PE module that exports GetPhysicallyInstalledSystemMemory.
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TC="$R/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
export PATH="$TC:$PATH"
B="$R/wine/build-arm64ec"
test -f "$B/config.status"
make -C "$B" -j"$(sysctl -n hw.ncpu)" dlls/kernelbase/arm64ec-windows/kernelbase.dll
SRC="$B/dlls/kernelbase/arm64ec-windows/kernelbase.dll"
OUT="$R/app/Madeira/arm64ec-windows/kernelbase.dll"
test -s "$SRC"
cp "$SRC" "$OUT"
# Keep the linked DLL intact; unlike ntdll no loader padding is needed.
cmp "$SRC" "$OUT"
shasum -a 256 "$OUT"
