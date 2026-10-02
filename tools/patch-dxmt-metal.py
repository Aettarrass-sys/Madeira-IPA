#!/usr/bin/env python3
"""Target DXMT's embedded command metallib at iOS 18, using pinned Meson rules."""

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one DXMT Metal generator in {path}; found {count}")
    path.write_text(text.replace(old, new, 1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxmt_root", type=Path)
    path = parser.parse_args().dxmt_root / "meson.build"
    replace_once(
        path,
        "arguments : [ '-sdk', 'macosx', 'metal', '-o', '@OUTPUT@', '-c', '@INPUT@', '@EXTRA_ARGS@'],",
        "arguments : [ '-sdk', 'iphoneos', 'metal', '-o', '@OUTPUT@', '-c', '@INPUT@', '-std=metal3.1', '--target=air64-apple-ios18.0', '@EXTRA_ARGS@'],",
    )
    replace_once(
        path,
        "arguments : [ '-sdk', 'macosx', 'metallib', '-o', '@OUTPUT@', '@INPUT@'],",
        "arguments : [ '-sdk', 'iphoneos', 'metallib', '-o', '@OUTPUT@', '@INPUT@'],",
    )


if __name__ == "__main__":
    main()
