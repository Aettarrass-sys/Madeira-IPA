#!/usr/bin/env python3
"""Initialize native WoW64 TLS before entering the non-returning 32-bit loader."""

from pathlib import Path
import sys


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Wine loader layout changed: expected one match, found {count}")
    return source.replace(old, new, 1)


loader = Path(sys.argv[1]) / "dlls/ntdll/loader.c"
source = loader.read_text()
source = replace_once(
    source,
    '''static void init_wow64( CONTEXT *context )
{
    if (!imports_fixup_done)
    {
        HMODULE wow64;
        WINE_MODREF *wm;
        NTSTATUS status;
''',
    '''static void init_wow64( CONTEXT *context )
{
    NTSTATUS status;

    if (!imports_fixup_done)
    {
        HMODULE wow64;
        WINE_MODREF *wm;
''',
)
source = replace_once(
    source,
    '''        imports_fixup_done = TRUE;
    }

    RtlLeaveCriticalSection( &loader_section );
    pWow64LdrpInitialize( context );
''',
    '''        imports_fixup_done = TRUE;
    }

    /* The native WoW64 half never returns here: Wow64LdrpInitialize runs the
     * 32-bit process, so loader_init() cannot reach its usual alloc_thread_tls()
     * below. The aarch64 CPU backend has PE static TLS and its compiler reads
     * TEB->ThreadLocalStoragePointer before it can run any guest instructions.
     * Allocate the native thread's TLS now, while the loader lock is held.
     * Modules loaded afterward extend this array in alloc_tls_slot(). */
    if (!NtCurrentTeb()->ThreadLocalStoragePointer)
    {
        if ((status = alloc_thread_tls()))
        {
            ERR( "native WoW64 TLS init failed, status %lx\\n", status );
            NtTerminateProcess( GetCurrentProcess(), status );
        }
        ERR( "[wow-native-tls] TEB=%p TLS=%p\\n", NtCurrentTeb(),
             NtCurrentTeb()->ThreadLocalStoragePointer );
    }

    RtlLeaveCriticalSection( &loader_section );
    pWow64LdrpInitialize( context );
''',
)
loader.write_text(source)
