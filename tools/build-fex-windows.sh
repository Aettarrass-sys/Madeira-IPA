#!/bin/bash
# Build the PE CPU modules from the same FEX revision as the native iOS core.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$root/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin:$PATH"
for spec in 'aarch64 wow64fex aarch64-windows xtajit.dll' \
            'arm64ec arm64ecfex arm64ec-windows xtajit64.dll'; do
    read -r arch target folder output <<< "$spec"
    build="$root/FEX/build-pe-$arch"
    cmake -S "$root/FEX" -B "$build" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_TOOLCHAIN_FILE="$root/FEX/Data/CMake/toolchain_mingw.cmake" \
        -DMINGW_TRIPLE="$arch-w64-mingw32" \
        -DFEX_IOS_HOST_BUILD=ON -DENABLE_LTO=OFF -DENABLE_CCACHE=OFF \
        -DCMAKE_C_FLAGS=-DFEX_IOS_HOST=1 \
        -DCMAKE_CXX_FLAGS=-DFEX_IOS_HOST=1 \
        -DENABLE_ASSERTIONS=OFF -DBUILD_TESTING=OFF -DBUILD_THUNKS=OFF \
        -DBUILD_FEXCONFIG=OFF -DTUNE_ARCH=generic -DTUNE_CPU=none
    cmake --build "$build" --target "$target" --parallel "$(sysctl -n hw.ncpu)"
    source="$build/Bin/lib$target.dll"
    test -s "$source"
    cp "$source" "$root/app/Madeira/$folder/$output"
    echo "Installed $folder/$output from $source"
done
