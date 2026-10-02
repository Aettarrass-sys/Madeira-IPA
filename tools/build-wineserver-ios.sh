#!/usr/bin/env bash
# Build an iOS base archive from source; never reuse macOS wineserver objects.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wine="$root/wine"
ws="$root/build/wineserver"
base="$ws/obj/ios-base"
sdk="$(xcrun --sdk iphoneos --show-sdk-path)"

# The host build generates Wine's config and protocol headers. Its object files
# are intentionally not included in the app's iOS archive.
make -C "$wine/build-macos" -j"$(sysctl -n hw.ncpu)" server/wineserver
test -s "$wine/build-macos/include/config.h"
rm -rf "$base" "$ws/obj/libwineserver.a"
mkdir -p "$base"

flags=(
  -arch arm64 -isysroot "$sdk" -miphoneos-version-min=18.0 -O2
  -I"$wine/include" -I"$wine/include/wine"
  -I"$wine/build-macos/include" -I"$wine/build-macos/server"
  -I"$wine/build-arm64ec/include"
  -I"$ws" -I"$wine/server" -I"$root/build/ntdll-unix/shims"
  -I"$root/build/madsync" -DHAVE_LINUX_NTSYNC_H=1
  -include "$ws/config_ios.h" -include stdarg.h
  -include "$ws/unicode_fix.h" -include "$ws/wineserver_ios_kill.h"
  '-DBINDIR="/usr/local/bin"' '-DDATADIR="/usr/local/share"'
  -D__WINESRC__ -DWINE_IOS=1 -Dmain=wineserver_main
  -Wno-implicit-function-declaration
)

# build/wineserver/build.sh compiles and inserts each of these replacements.
skip=' async.c class.c event.c fd.c handle.c inproc_sync.c mach.c main.c mapping.c object.c process.c queue.c region.c request.c sock.c thread.c unicode.c user.c window.c winstation.c '
objects=()
while IFS= read -r source; do
  case "$skip" in *" $source "*) continue ;; esac
  xcrun -sdk iphoneos clang "${flags[@]}" -c "$wine/server/$source" \
    -o "$base/${source%.c}.o"
  objects+=("$base/${source%.c}.o")
done < <(awk '
  /^SOURCES[[:space:]]*=/ { on = 1; sub(/^SOURCES[[:space:]]*=/, "") }
  on {
    cont = ($0 ~ /\\[[:space:]]*$/)
    gsub(/\\/, "")
    for (i = 1; i <= NF; i++) if ($i ~ /\.c$/) print $i
    if (!cont) exit
  }' "$wine/server/Makefile.in")
(( ${#objects[@]} > 0 )) || { echo 'No Wine server sources found' >&2; exit 1; }
ar rcs "$ws/obj/libwineserver.a" "${objects[@]}"
bash "$ws/build.sh"
test -s "$root/app/Madeira/libwineserver.a"
