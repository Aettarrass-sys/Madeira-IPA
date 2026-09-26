#!/usr/bin/env python3
"""Require the newly built command metallib to be embedded in DXMT's PE DLL."""

import argparse
import hashlib
import struct
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metallib", type=Path)
    parser.add_argument("dll", type=Path)
    args = parser.parse_args()
    shader = args.metallib.read_bytes()
    dll = args.dll.read_bytes()
    if not shader.startswith(b"MTLB") or len(shader) < 64:
        raise SystemExit("DXMT command output is not a Metal library")
    declared_size = struct.unpack_from("<Q", shader, 0x10)[0]
    if declared_size != len(shader):
        raise SystemExit(f"Metal library size mismatch: {declared_size} != {len(shader)}")
    if dll.count(shader) != 1:
        raise SystemExit("New DXMT command Metal library is not embedded exactly once in d3d11.dll")
    digest = hashlib.sha256(shader).hexdigest()
    print(f"DXMT command library embedded in d3d11.dll: {len(shader)} bytes, SHA-256 {digest}")


if __name__ == "__main__":
    main()
