#!/usr/bin/env python3
"""Target DXMT's embedded command metallib at iOS 18, using pinned Meson rules."""

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one DXMT Metal generator in {path}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxmt_root", type=Path)
    root = parser.parse_args().dxmt_root
    path = root / "meson.build"
    # The pinned DXMT sources predate Madeira 0.1.1's repository move.
    # Repair all includes that reach outside that submodule, not just the
    # first compiler failure. Remote Metal remains in research/remote-metal.
    replace_once(root / "src/winemetal/unix/winemetal_unix.c",
                 '"../../../../../build/madeira_cfg.h"',
                 '"../../../../build/madeira_cfg.h"')
    for filename, header in (
        ("winemetal_unix.c", "host/wmt_decode.h"),
        ("wmt_remote_client.h", "protocol.h"),
        ("wmt_remote_pack.h", "wmt_pack.h"),
    ):
        replace_once(root / "src/winemetal/unix" / filename,
                     f'"../../../../remote-metal/{header}"',
                     f'"../../../../research/remote-metal/{header}"')
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
