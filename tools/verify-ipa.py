#!/usr/bin/env python3
"""Check that the SideStore-ready IPA contains Madeira's required runtimes."""

import argparse
import hashlib
import pathlib
import plistlib
import struct
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app/Madeira"
VCRUNTIME_NAMES = (
    "concrt140.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll", "vcamp140.dll",
    "vccorlib140.dll", "vcomp140.dll", "vcruntime140.dll",
    "vcruntime140_1.dll", "vcruntime140_threads.dll",
)


def pe_machine(data: bytes) -> int:
    if len(data) < 256 or data[:2] != b"MZ":
        raise ValueError("not a PE file")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset + 24 > len(data) or data[offset : offset + 4] != b"PE\0\0":
        raise ValueError("invalid PE header")
    return struct.unpack_from("<H", data, offset + 4)[0]


def has_macho_signature(data: bytes) -> bool:
    if len(data) < 32 or struct.unpack_from("<I", data)[0] != 0xFEEDFACF:
        return False
    command_count = struct.unpack_from("<I", data, 16)[0]
    offset = 32
    for _ in range(command_count):
        if offset + 8 > len(data):
            return False
        command, size = struct.unpack_from("<II", data, offset)
        if size < 8 or offset + size > len(data):
            return False
        if command == 0x1D and size >= 16:
            signature_offset, signature_size = struct.unpack_from("<II", data, offset + 8)
            return signature_size > 0 and signature_offset + signature_size <= len(data)
        offset += size
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ipa", type=pathlib.Path)
    parser.add_argument("--bundle-id", required=True)
    args = parser.parse_args()
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "app/Madeira/arm64ec-windows", "app/Madeira/aarch64-windows"],
        cwd=ROOT,
    ).decode().split("\0")
    expected = [pathlib.Path(p) for p in tracked if p and pathlib.Path(p).suffix.lower() in (".dll", ".exe")]
    expected.extend(pathlib.Path("app/Madeira/x86_64-vcruntime") / name for name in VCRUNTIME_NAMES)
    if len(expected) < 250:
        raise SystemExit(f"Runtime inventory unexpectedly small: {len(expected)} files")

    with zipfile.ZipFile(args.ipa) as archive:
        names = set(archive.namelist())
        info_name = "Payload/Madeira.app/Info.plist"
        exe_name = "Payload/Madeira.app/Madeira"
        if info_name not in names or exe_name not in names:
            raise SystemExit("IPA is missing Madeira.app Info.plist or executable")
        for code_name in (
            exe_name,
            "Payload/Madeira.app/Madeira.debug.dylib",
            "Payload/Madeira.app/d3d12/libmetalirconverter.dylib",
        ):
            if code_name not in names or not has_macho_signature(archive.read(code_name)):
                raise SystemExit(f"Missing Mach-O code signature: {code_name}")
        info = plistlib.loads(archive.read(info_name))
        if info.get("CFBundleIdentifier") != args.bundle_id:
            raise SystemExit(f"Wrong Bundle ID: {info.get('CFBundleIdentifier')}")
        if float(info.get("MinimumOSVersion", "0")) < 18:
            raise SystemExit(f"Deployment target below iOS 18: {info.get('MinimumOSVersion')}")
        for source in expected:
            bundled = "Payload/Madeira.app/" + "/".join(source.parts[2:])
            if bundled not in names:
                raise SystemExit(f"Missing bundled runtime: {bundled}")
            data = archive.read(bundled)
            if data != (ROOT / source).read_bytes():
                raise SystemExit(f"Bundled runtime differs from source: {bundled}")
            folder = source.parts[2]
            machine = pe_machine(data)
            want = 0xAA64 if folder == "aarch64-windows" else 0x8664
            if machine != want:
                raise SystemExit(f"Wrong PE machine in {bundled}: {machine:#x}")
        for name in ("prefix-template.tar.gz", "cacert.pem", "d3d12/libmetalirconverter.dylib"):
            bundled = "Payload/Madeira.app/" + name
            if bundled not in names:
                raise SystemExit(f"Missing bundle resource: {bundled}")
        for directory in ("licenses", "nls"):
            if not any(p.startswith(f"Payload/Madeira.app/{directory}/") for p in names):
                raise SystemExit(f"Missing bundle directory: {directory}")
        digest = hashlib.sha256(args.ipa.read_bytes()).hexdigest()
        print(f"Verified {len(expected)} PE files; bundle={args.bundle_id}; SHA-256={digest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"IPA validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
