#!/bin/bash
# Rebuild the ARM64EC D3D11 frontend: native DXMT alone does not update DSR.
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TC="$R/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin"
export PATH="$TC:$PATH"
W="$R/wine/build-arm64ec"
D="$R/dxmt"
DEST="$R/app/Madeira/arm64ec-windows"
test -f "$W/config.status"
make -C "$W" -j"$(sysctl -n hw.ncpu)" \
  tools/winebuild/winebuild libs/winecrt0/arm64ec-windows/libwinecrt0.a \
  dlls/ntdll/arm64ec-windows/libntdll.a dlls/dbghelp/arm64ec-windows/libdbghelp.a
# Meson resolves @GLOBAL_SOURCE_ROOT@ in this cross file to dxmt/, whose
# toolchains symlink points at the repo toolchains (created by the workflow).
test -x "$D/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin/arm64ec-w64-mingw32-clang"
cd "$D"
SDKROOT="$(xcrun --sdk macosx --show-sdk-path)" meson setup \
  --cross-file build-arm64ec-win.txt --native-file build-osx.txt \
  --buildtype release -Dwine_build_path="$W" -Dwine_builtin_dll=true build-dsr-arm64ec
SDKROOT="$(xcrun --sdk macosx --show-sdk-path)" ninja -C build-dsr-arm64ec \
  src/d3d11/d3d11.dll.postproc src/dxgi/dxgi.dll.postproc \
  src/d3d10/d3d10core.dll.postproc src/winemetal/winemetal.dll.postproc
for module in d3d11/d3d11.dll dxgi/dxgi.dll d3d10/d3d10core.dll winemetal/winemetal.dll; do
  test -s "build-dsr-arm64ec/src/$module"
  "$TC/arm64ec-w64-mingw32-strip" -o "$DEST/$(basename "$module")" "build-dsr-arm64ec/src/$module"
done
shasum -a 256 "$DEST/d3d11.dll"
