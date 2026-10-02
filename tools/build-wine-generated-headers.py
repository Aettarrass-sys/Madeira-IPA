#!/usr/bin/env python3
"""Build the header targets Wine's configured Makefile actually declares."""
from pathlib import Path
import argparse
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('build', type=Path)
args = parser.parse_args()
build = args.build.resolve()
makefile = (build / 'Makefile').read_text(encoding='utf8').replace('\\\n', ' ')
targets = set()
for line in makefile.splitlines():
    if not line or line[0].isspace() or line.startswith('#') or ':' not in line:
        continue
    left = line.split(':', 1)[0]
    targets.update(t for t in left.split() if t.startswith('include/') and t.endswith('.h'))
required = {'include/wtypes.h', 'include/mfobjects.h', 'include/dwrite_3.h'}
if not required <= targets:
    raise SystemExit(f'Wine generated-header rules missing: {sorted(required - targets)}')
print(f'Building {len(targets)} configured Wine header targets', flush=True)
subprocess.run(['make', '-C', str(build), '-j', str(os.cpu_count() or 4), *sorted(targets)], check=True)
missing = [t for t in targets if not (build / t).is_file() or not (build / t).stat().st_size]
if missing:
    raise SystemExit(f'Wine headers not generated: {sorted(missing)}')
