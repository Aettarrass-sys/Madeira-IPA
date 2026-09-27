#!/bin/bash
# Build the Wine PE modules changed by the WoW64 companion revision.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$root/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
jobs="$(sysctl -n hw.ncpu)"

build_arch() {
    local arch="$1"; shift
    local build="$root/wine/build-$arch"
    if [ ! -f "$build/config.status" ]; then
        mkdir -p "$build"
        (cd "$build" && ../configure --enable-archs="$arch" --without-x \
            --without-vulkan --disable-tests)
    fi
    local targets=() name source
    for name in "$@"; do targets+=("dlls/$name/$arch-windows/$name.dll"); done
    make -C "$build" -j"$jobs" "${targets[@]}"
    for name in "$@"; do
        source="$build/dlls/$name/$arch-windows/$name.dll"
        test -s "$source"
        cp "$source" "$root/app/Madeira/$arch-windows/$name.dll"
    done
}

# The 32-bit process executes its native WoW64 half as aarch64, not ARM64EC.
build_arch aarch64 ntdll wow64 wow64win nsi
# Retain the existing ARM64EC path with PE files from the matched Wine source.
build_arch arm64ec ntdll nsi
