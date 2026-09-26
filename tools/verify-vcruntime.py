#!/usr/bin/env python3
"""Select and verify the twelve original Microsoft x64 VC runtime DLLs."""

import argparse
import hashlib
import pathlib
import struct
import sys

NAMES = (
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcamp140.dll",
    "vccorlib140.dll",
    "vcomp140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcruntime140_threads.dll",
)


def valid_x64_signed_pe(path: pathlib.Path) -> bool:
    data = path.read_bytes()
    if len(data) < 512 or data[:2] != b"MZ":
        return False
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 264 > len(data) or data[pe : pe + 4] != b"PE\0\0":
        return False
    machine = struct.unpack_from("<H", data, pe + 4)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    if machine != 0x8664 or magic != 0x20B:
        return False
    cert_offset, cert_size = struct.unpack_from("<II", data, optional + 112 + 8 * 4)
    return cert_size > 0 and cert_offset > 0 and cert_offset + cert_size <= len(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract", type=pathlib.Path)
    parser.add_argument("--dest", required=True, type=pathlib.Path)
    args = parser.parse_args()
    if args.extract:
        candidates = list(args.extract.rglob("*"))
        args.dest.mkdir(parents=True, exist_ok=True)
        for name in NAMES:
            matches = [
                p for p in candidates
                if p.is_file() and p.name.lower() == name
                and valid_x64_signed_pe(p)
            ]
            if not matches:
                print(f"Missing signed x64 Microsoft runtime: {name}", file=sys.stderr)
                return 1
            # Duplicate files are common inside the redistributable. The largest
            # signed x64 candidate is the complete release payload.
            source = max(matches, key=lambda p: p.stat().st_size)
            (args.dest / name).write_bytes(source.read_bytes())
    missing = []
    for name in NAMES:
        path = args.dest / name
        if not path.is_file() or not valid_x64_signed_pe(path):
            missing.append(name)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{name}\t{path.stat().st_size}\t{digest}")
    if missing:
        print("Invalid or missing VC runtimes: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
