#!/usr/bin/env python3
"""Exercise the production alias registry and DSR fault-counting regression."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
vm = (ROOT / 'build/ntdll-unix/virtual_ios.c').read_text(encoding='utf8')
signal = (ROOT / 'build/ntdll-unix/signal_arm64_ios.c').read_text(encoding='utf8')

def function(name):
    matches = re.findall(r'^(?:static )?(?:int|uint64_t) ' + name + r'\([^;]*?\n\{.*?^\}', vm, re.M | re.S)
    assert len(matches) == 1, (name, len(matches))
    return matches[0]

defs = vm[vm.index('#define IOS_LOWALLOC_MAX'):vm.index('/* ml968:')]
fault = signal[signal.index('        static struct { uint64_t thread;'):signal.index('        else if (++redeliv[rslot].n == 256)')]
fault = fault.replace('        static volatile int ios_redeliv_terminating;\n', '')
program = '''
#include <stdint.h>
#include <pthread.h>
#include <assert.h>
int ios_subfloor_enum(int i, unsigned long long *lo, unsigned long long *real, unsigned long long *size)
{ if (i) return 0; *lo=0x3b400000; *real=0x713b400000; *size=0x10000; return 1; }
''' + defs + '\n'.join(function(n) for n in (
    'ios_lowalias_would_collide', 'ios_lowalias_register',
    'ios_lowalias_retire_by_real', 'ios_lowalloc_translate')) + '''
static unsigned count_fault(uint64_t thread, uint64_t pc, uint64_t fault_addr) {
''' + fault + '''
    else ++redeliv[rslot].n;
    return redeliv[rslot].n;
}
int main(void) {
    unsigned long long real=0; void *owner=0;
    /* Exact module address and failing PE-header read captured in the user's log. */
    assert(ios_lowalias_register(0x71fe340000,0x10000,(void*)1)==0xfe340000);
    assert(ios_lowalloc_translate(0xfe34003c,4,&real,&owner));
    assert(real==0x71fe34003c && owner==(void*)1);
    assert(!ios_lowalloc_translate(0xfe34ffff,2,&real,0));
    assert(!ios_lowalias_register(0x72fe340000,0x10000,(void*)2));
    assert(!ios_lowalias_register(0x713b400000,0x10000,0)); /* image preferred window */
    assert(!ios_lowalias_register(0x71ffff0000,0x20000,0)); /* crosses 4 GB */
    assert(!ios_lowalias_register(0x7100001000,0x1000,0)); /* null-ish */
    assert(!ios_lowalias_register(0x7130000000,0x1000,0)); /* reserved arena */
    assert(!ios_lowalias_retire_by_real(0x71fe340000,(void*)2)); /* foreign owner */
    assert(ios_lowalias_retire_by_real(0x71fe340000,0)==0xfe340000);
    assert(!ios_lowalloc_translate(0xfe34003c,4,&real,0));
    for (unsigned f=0;f<5000;f++) for (unsigned k=0;k<7;k++)
        assert(count_fault(8,0x140000000+k*16,0x141000000+k*4096)==1);
    for (unsigned n=1;n<=2000;n++) assert(count_fault(12,0x140100000,0x142000000)==n);
    assert(count_fault(12,0x140100004,0x142000000)==1);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='dsr-test-', dir=ROOT) as td:
    path = Path(td); (path/'test.c').write_text(program, encoding='utf8')
    if os.name == 'nt':
        posix = '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]
        subprocess.run(['wsl','gcc','-std=c11','-pthread',posix+'/test.c','-o',posix+'/test'],check=True)
        subprocess.run(['wsl',posix+'/test'],check=True)
    else:
        subprocess.run([os.environ.get('CC','clang'),'-std=c11','-pthread',str(path/'test.c'),'-o',str(path/'test')],check=True)
        subprocess.run([str(path/'test')],check=True)

workflow = (ROOT/'.github/workflows/build.yml').read_text(encoding='utf8')
assert workflow.index('Apply published DSR Wine fixes') < workflow.index('Rebuild and stage the patched ARM64EC ntdll') < workflow.index('Build unsigned Debug app')
assert '.github/patches/dsr-*.patch' in workflow
print('PASS: logged truncated address, collision/bounds/ownership/unmap, recurring settings faults, real fault storm, build wiring')
