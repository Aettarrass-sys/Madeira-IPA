# Building the SideStore IPA

Run **Actions → Build Madeira IPA → Run workflow** on this fork's `main`
branch. The workflow is manual so a push does not start a long macOS build.
It builds the **Debug** app for iOS 18 or newer and uploads
`Madeira-Debug-iOS18`, containing `Madeira.ipa`, its SHA-256 checksum, and a
source/build manifest. No Apple signing credentials are stored in GitHub.

The workflow checks out the pinned FEX, Wine, and DXMT submodules. It uses
the Windows PE DLLs and EXEs already committed to this fork, compiles the
missing iOS static libraries, and fetches all twelve x64 Microsoft Visual
C++ runtime DLLs from Microsoft's official redistributable. It stages the
license files, checks the prefix template and converter dylib, then builds,
ad hoc signs, and verifies the IPA. A failed prerequisite or check stops the
workflow rather than uploading an incomplete IPA.

The pinned Wine fork references an `arm64ec_x64_export_iat.c` file absent from
its Git tree. Wine's dependency scanner requires that path even to generate
headers. CI supplies an empty scanner sentinel and does not build PE ntdll;
the app bundles its tracked PE ntdll. Rebuilding Wine's PE ntdll from source
requires the upstream fork to provide the real missing implementation.

Download the IPA artifact from the completed run and install it with
SideStore. SideStore applies the Apple developer signature, so its installed
bundle ID and entitlements must be checked on the phone. The build requests
`com.NotBoodiOS.madeira`, increased memory, and extended virtual addressing;
SideStore may change the final signed identifier. `allow-jit` showing false
on iOS is not the debugger attachment test.

Before starting Wine, enable JIT with StikDebug and leave Madeira idle for at
least two minutes. Compare the small JIT badge with Madeira's timestamped
`CS_DEBUGGED`/`P_TRACED` log and StikDebug's log. A badge change alone does
not prove the debugger detached: a prior log showed both flags still set at
99 seconds. The current `stikjit://` URL integration and debugger script are
left unchanged in this build.

This workflow adapts the process from `Notbood/Madeira-IPA` to the current
`willfaust/Madeira` source. Upstream's clean build record in
`docs/BUILDING.md` marks parts of the native build unverified, so the first
successful Actions run and device install are required to establish that the
whole pipeline works.
