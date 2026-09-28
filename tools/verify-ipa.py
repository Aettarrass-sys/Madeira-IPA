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
    i386_dir = pathlib.Path("app/Madeira/i386-windows")
    i386 = sorted(p for p in (ROOT / i386_dir).iterdir()
                  if p.is_file() and p.suffix.lower() in (".dll", ".exe"))
    if len(i386) < 500:
        raise SystemExit(f"i386 runtime inventory unexpectedly small: {len(i386)} files")
    required_i386 = {"ntdll.dll", "kernel32.dll", "user32.dll", "d3d9.dll",
                     "d3d9-emulated.dll", "d3d9shim.dll", "hello-x86.exe",
                     "d3d9-cube-x86.exe"}
    missing_i386 = required_i386 - {p.name.lower() for p in i386}
    if missing_i386:
        raise SystemExit(f"Missing required i386 files: {sorted(missing_i386)}")
    expected.extend(p.relative_to(ROOT) for p in i386)
    required_native_pe = (
        "aarch64-windows/ntdll.dll", "aarch64-windows/wow64.dll",
        "aarch64-windows/wow64win.dll", "aarch64-windows/xtajit.dll",
        "arm64ec-windows/ntdll.dll", "arm64ec-windows/xtajit64.dll",
    )
    expected.extend(pathlib.Path("app/Madeira") / name for name in required_native_pe
                    if pathlib.Path("app/Madeira", name) not in expected)
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
        app_code = archive.read("Payload/Madeira.app/Madeira.debug.dylib")
        for marker in (b"[ptde-zero-layout]", b"[buffer-to-texture-bounds]",
                       b"[wow-reserve] RECOVERED"):
            if marker not in app_code:
                raise SystemExit(f"Packaged app lacks runtime fix: {marker.decode()}")
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
            want = {"aarch64-windows": 0xAA64, "arm64ec-windows": 0x8664,
                    "i386-windows": 0x14C, "x86_64-vcruntime": 0x8664}.get(folder)
            if want is None:
                raise SystemExit(f"Unexpected PE folder: {folder}")
            if machine != want:
                raise SystemExit(f"Wrong PE machine in {bundled}: {machine:#x}")
            if source.as_posix() == "app/Madeira/aarch64-windows/xtajit.dll":
                if b"[wow64-crt] ran skipped constructors" not in data:
                    raise SystemExit("Packaged xtajit.dll lacks the WoW64 constructor repair")
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
