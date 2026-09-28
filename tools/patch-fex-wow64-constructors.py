#!/usr/bin/env python3
"""Repair skipped GNU constructors in the pinned iOS-host WoW64 FEX CRT."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fex_root", type=Path)
    path = parser.parse_args().fex_root / "Source/Windows/Common/CRT/CRT_iOS.cpp"
    source = path.read_text(encoding="utf-8")
    old_comment = """// iOS-host builds (llvm-mingw 22.1.4's arm64ec EC-mangling doesn't reconcile
// cleanly with -nostdlib + custom CRT). So we let mingw's default
// DllMainCRTStartup run the C++ constructors / TLS callbacks for us."""
    new_comment = """// iOS-host builds (llvm-mingw 22.1.4's arm64ec EC-mangling doesn't reconcile
// cleanly with -nostdlib + custom CRT). MinGW usually runs constructors, but
// Wine can enter the WoW64 CPU module before its DLL startup has run."""
    if source.count(old_comment) != 1:
        raise SystemExit(f"Expected one pinned CRT comment in {path}; found {source.count(old_comment)}")
    source = source.replace(old_comment, new_comment, 1)
    old = """#include <rpmalloc/rpmalloc.h>

namespace FEX::Windows {
void InitCRTProcess() {
  // mingw's default startup already ran the C++ ctors. Ensure the rpmalloc
  // global heap is up (idempotent) before any per-thread init below.
  rpmalloc_initialize(nullptr);
}"""
    new = """#include <cstdio>
#include <cstdlib>
#include <rpmalloc/rpmalloc.h>

extern \"C\" void (*__CTOR_LIST__[])();

namespace {
volatile unsigned ConstructorsRan = 0;
struct ConstructorProbe {
  ConstructorProbe() { ConstructorsRan = 1; }
};
ConstructorProbe Probe;

void RunConstructorsIfNeeded() {
  if (ConstructorsRan) {
    std::fputs(\"[wow64-crt] constructors already ran\\n\", stderr);
    return;
  }
  // Match CRT.cpp's reverse traversal of MinGW's GNU constructor list.
  auto begin = &__CTOR_LIST__[1];
  auto end = begin;
  while (*end) ++end;
  while (end != begin) (*--end)();
  if (!ConstructorsRan) {
    std::fputs(\"[wow64-crt] constructor probe absent from list\\n\", stderr);
    std::abort();
  }
  std::fputs(\"[wow64-crt] ran skipped constructors\\n\", stderr);
}
} // namespace

namespace FEX::Windows {
void InitCRTProcess() {
  // The WoW64 CPU entry may run before MinGW calls C++ global constructors.
  // The global Threads map in Module.cpp must be constructed before use.
  rpmalloc_initialize(nullptr);
  RunConstructorsIfNeeded();
}"""
    if source.count(old) != 1:
        raise SystemExit(f"Expected one pinned CRT block in {path}; found {source.count(old)}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
