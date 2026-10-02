#!/usr/bin/env python3
"""Apply narrowly checked iOS build fixes to pinned third-party source trees."""

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text()
    if content.count(old) != 1:
        raise SystemExit(f"Expected one matching source block in {path}; found {content.count(old)}")
    path.write_text(content.replace(old, new, 1))


def patch_fex(root: Path) -> None:
    allocator = root / "FEXCore/Source/Utils/AllocatorHooks.cpp"
    replace_once(allocator,
                 '''size_t malloc_usable_size(void* ptr) {
  IOS_RPM_GUARD();
  return ::rpmalloc_usable_size(ptr);''',
                 '''size_t malloc_usable_size(void* ptr) {
  return ::rpmalloc_usable_size(ptr);''')
    linker = root / "Data/CMake/LinkerGC.cmake"
    replace_once(linker, 'if (CMAKE_BUILD_TYPE MATCHES "RELEASE")',
                 'if (CMAKE_BUILD_TYPE MATCHES "RELEASE" AND NOT APPLE)')


def patch_llvm(root: Path) -> None:
    cmake = root / "llvm/cmake/modules/AddLLVM.cmake"
    content = cmake.read_text()
    old_gc = 'elseif(NOT MSVC AND NOT CMAKE_SYSTEM_NAME MATCHES "AIX|OS390")'
    new_gc = 'elseif(NOT MSVC AND NOT CMAKE_SYSTEM_NAME MATCHES "AIX|OS390|iOS")'
    if content.count(old_gc) != 1:
        raise SystemExit("LLVM iOS linker patch no longer matches pinned source")
    content = content.replace(old_gc, new_gc, 1)
    start = content.index("function(add_llvm_symbol_exports target_name export_file)")
    end = content.index("endfunction(add_llvm_symbol_exports)", start)
    block = content[start:end]
    old_symbols = 'if(${CMAKE_SYSTEM_NAME} MATCHES "Darwin")'
    if block.count(old_symbols) != 1:
        raise SystemExit("LLVM iOS symbol export patch no longer matches pinned source")
    block = block.replace(old_symbols, 'if(${CMAKE_SYSTEM_NAME} MATCHES "Darwin|iOS")', 1)
    cmake.write_text(content[:start] + block + content[end:])


def patch_wine(root: Path) -> None:
    sync = root / "dlls/ntdll/unix/sync.c"
    old = '''#include "../../../../build/madeira_cfg.h"   /* ml1122: before the Wine headers, which ban strncpy by macro */
#include "config.h"'''
    new = '''#include "config.h"
#include "../../../../build/madeira_cfg.h"   /* ml1122: before Wine API headers, which ban strncpy by macro */'''
    replace_once(sync, old, new)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("fex", "llvm", "wine"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.kind == "fex":
        patch_fex(args.root)
    elif args.kind == "llvm":
        patch_llvm(args.root)
    else:
        patch_wine(args.root)


if __name__ == "__main__":
    main()
