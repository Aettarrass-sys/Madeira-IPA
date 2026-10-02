# DSR build on the official Madeira baseline

## Source and scope

Branch: `codex/dsr-official-fixes` in `Aettarrass-sys/Madeira-IPA`.
Base updated to official Madeira 0.1.1, `ca3183ea3dfb0fd706aff1bea2abb871b5d27aec`.
Original base: 0.1.0, `3ccbf9b8bc97f7a59727d10bb9e98717d2c91d64`.
Wine, FEX and DXMT gitlinks remain pinned to that release. This is separate
from the BCD/PTDE branch. Bundle ID remains `com.willfaust.mythicemu`.
Minimum iOS version: 26.0, matching the official converter/runtime baseline.

The functional patches come from meshoklv's published, device-tested patch
set in [issue 56](https://github.com/willfaust/Madeira/issues/56#issuecomment-5910055474).
That report is evidence for the approach, not verification of this IPA on
the user's phone. The source comment targeted a slightly later UI commit;
foreground handling and the fault watchdog were adapted to the release.

## Included fixes

1. **Relocated DLL image aliases (patch 01).** Register the low 32-bit name
   of a high-address image whose preferred base is below 4 GB. This handles
   the user's exact `steamclient64.dll` instruction that truncates
   `steam_api64.dll` at `0x71fe340000` and reads `0xfe34003c`. Canonical
   returned addresses remain high; aliases refuse collisions and crossing
   the 4 GB boundary and are retired when their image is unmapped.
2. **Fixed-base executable window floor (01).** Add
   `MADEIRA_EXE_WIN_FLOOR_MB`; DSR needs 32 instead of the default 64 MB.
3. **VirtualQuery host mapping and JIT pool clipping (01).** Report
   unavailable host memory as reserved and prevent an allocation walker
   from stepping into the JIT pool and getting an answer below its cursor.
4. **Balance the ARM64EC protection callback (10).** Call
   `leave_syscall_callback()` before the existing executable-protect early
   return. Otherwise later protection/allocation notifications bypass FEX.
5. **Builtin XInput routing (30).** Prefer Wine's system32 XInput instead
   of the game's Microsoft DLL, which searches for unavailable XUSB drivers.
6. **Foreground controller activation (36).** During controller polling,
   periodically activate the process's largest top-level game window if a
   different process or no window owns foreground focus. A foreground
   dialog belonging to the game is preserved.
7. **Touch/mouse gate (37).** Suppress direct-touch mouse events while the
   landscape controller overlay is active. Swallowed touches stay swallowed
   until release; physical mouse input remains available.
8. **Settings-menu fault watchdog (39).** Count consecutive identical faults
   per thread, rather than lifetime hits for recurring fault addresses.
   DSR's cycling protected-code writes no longer falsely accumulate to the
   terminal threshold. A repeated identical fault still reaches the guard.
9. **Profile folders.** Create AppData Local/LocalLow/Roaming and Documents
   under both mobile and madeira profiles after legacy cleanup, preserving
   existing contents.

## Diagnostics

New image/query/foreground/touch diagnostics are optional. Set
`env.MADEIRA_DIAG = 1` for a troubleshooting run; `0` disables those logs
without disabling the fixes. The environment flag is wired to the native
diagnostic switch used by the UI. Existing official release logging is
otherwise retained; this branch does not import the BCD diagnostic suite.

The original root patch files (01/36/37/39) are reference copies, not applied
again by CI. Their adapted changes are committed directly in Madeira's
source. Wine patches 10 and 30 are applied by CI to the public pinned Wine
checkout; no unpublished Wine gitlink is needed.

## Build wiring and verification

- Rebuild the patched ARM64EC PE `ntdll.dll`, strip it and pad to
  `SizeOfImage + 0x50000`, then stage it into the app DLL farm.
- Rebuild ntdll/win32u/wineserver, FEX and DXMT native static libraries.
- Native FEX uses the official system-allocator configuration without the
  Windows-module `FEX_IOS_HOST` flag. The existing BCD portability helper
  guards Windows-only diagnostic probes and provides a no-snapshot fallback
  when rpmalloc is absent. Windows FEX PE DLLs retain their release binaries.
- Keep the unchanged, matched official FEX/DXMT PE binaries for 64-bit.
- Build the i386 runtime farm and its DXMT DLLs for the official WoW64 path.
- Build FFmpeg before compiling the native media backend.
- Generate Wine's complete configured header set upfront and expose it to
  every native Wine consumer (ntdll, win32u and both wineserver stages); abort
  native archiving on any compilation failure.
- The optional page-wait statistic is reported as `n/a` because the public
  iPhoneOS SDK does not expose that field.
- Prepare MetalToolchain before the first DXMT PE shader build.
- Cache LLVM/toolchains and native outputs; native cache identity includes
  source/build helper content, Wine patches and recursive submodule pins.
- Build Debug, ad hoc sign nested Mach-O files and the app with the checked-in
  entitlements. Verify extended virtual addressing, increased memory limit,
  the bundle ID, signatures, DLL architecture and packaged/source equality.
- `python tools/check-dsr-fixes.py` compiles the production alias registry
  and watchdog code in a host harness. Checks cover the exact logged address,
  span bounds, collisions, ownership, unmap, cycling settings faults and a
  genuine repeated fault sequence. This does not emulate iOS Mach handling.

## First phone test

Use the DSR executable already imported in the library. Add these settings
to Documents/madeira.cfg (keep the correct executable path for the device):

```ini
env.MADEIRA_EXE_WIN_FLOOR_MB = 32
env.MADEIRA_INSTALLED_PHYS_MB = 6144
env.SteamAppId = 570940
env.SteamGameId = 570940
env.MADEIRA_PAD_EARLY_SLOT = 1
env.MADEIRA_DIAG = 1
```

Leave image aliases, query clipping, builtin XInput and foreground activation
at their enabled defaults. Do not carry PTDE-specific D3D9/DSfix overrides
into DSR. Enable JIT, launch DSR, test menu/controller input, open Settings,
then try gameplay. Export the log if startup fails or the game stops.
After a successful test, use `env.MADEIRA_DIAG = 0` for normal play.

Optional compatibility switches:

| Setting | Default | Purpose |
| --- | --- | --- |
| `MADEIRA_EXE_WIN_FLOOR_MB` | 64 | Use 32 for this DSR executable |
| `MADEIRA_NO_IMAGE_LOW_ALIAS` | 0 | 1 disables image aliases |
| `MADEIRA_NO_LOW_ALIAS` | 0 | 1 disables all low aliases |
| `MADEIRA_NO_QUERY_CLIP` | 0 | 1 restores prior query behavior |
| `MADEIRA_NATIVE_XINPUT` | 0 | 1 permits game-folder native XInput |
| `MADEIRA_FOREGROUND_FIX` | 1 | 0 disables activation |
| `MADEIRA_TOUCH_MOUSE` | auto | 0 never sends direct-touch mouse events; 1 always sends |

Use `env.` before each environment setting in madeira.cfg. This branch does
not require replacing game DLLs or adding a new game mod.

## Official 0.1.1 update and installed-memory gate

Includes upstream optional Liquid Metal (off by default), JIT attachment and
launch reporting fixes, small fixed-base executable support, shared section
alignment handling, and profile/Steam error improvements. Runtime submodule
pins remain unchanged. CI follows the renamed dxmt/ and tests/x86/ paths.
The configurable executable floor is retained alongside the upstream
relocations-stripped exception; profile fixes are combined.

The exact tested DSR executable calls GetPhysicallyInstalledSystemMemory at
0x14015c102, shifts the KB result right by 20 and compares against 6 at
0x14015c115. This is a 6 GiB installed-memory gate. The previous run reported
4095 MiB and displayed the fatal memory requirement dialog after D3D11 init.

Patch 40 adds an opt-in MADEIRA_INSTALLED_PHYS_MB (6144 for DSR) only to that
API. Absent, zero, malformed and out-of-range values use ordinary reporting.
GlobalMemoryStatusEx, available memory and jetsam/allocation limits are not
changed. Passing the startup gate does not establish gameplay stability.
CI rebuilds ARM64EC kernelbase.dll after applying all Wine patches and checks
that the packaged DLL equals the rebuilt module. docs/DSR-test.cfg is uploaded
with the IPA. Fully restart the app after changing the config.

## Follow-up build path repair

Run 37055851297 rebuilt the patched PE modules, i386 runtime, native Wine
and FEX successfully, then failed compiling DXMT winemetal_unix.c. The pinned
DXMT still used its old research/dxmt-relative config include. Its three
remote-Metal includes would also fail after that; remote-metal remains under
research/. The DXMT source preparation helper now repairs all four before
compilation, and check-build-layout.py checks external includes, workflow
script targets and Xcode source references at the start of every build.
