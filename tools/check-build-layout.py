#!/usr/bin/env python3
"""Check source paths before expensive native compilation after a repo move."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
checked = 0
for source in (ROOT / 'dxmt/src').rglob('*'):
    if source.suffix not in ('.c', '.h', '.cpp', '.hpp', '.mm'):
        continue
    for include in re.findall(r'^\s*#\s*include\s+"([^"\n]+)"', source.read_text(encoding='utf8'), re.M):
        if '..' not in include:
            continue
        target = (source.parent / include).resolve()
        if not target.is_relative_to(ROOT / 'dxmt'):
            assert target.is_file(), (source, include, target)
            checked += 1
assert checked >= 4, checked
workflow = (ROOT / '.github/workflows/build.yml').read_text(encoding='utf8')
for target in re.findall(r'(?:bash|python3)\s+((?:tools|build|tests)/[\w./-]+)', workflow):
    assert (ROOT / target).is_file(), target
project = (ROOT / 'app/Madeira.xcodeproj/project.pbxproj').read_text(encoding='utf8')
for target in re.findall(r'path = "?([^";\n]+\.(?:swift|mm|m|c|metal))"?;', project):
    assert (ROOT / 'app/Madeira' / target).is_file(), target
assert 'research/dxmt' not in workflow
assert 'build/x86-tests/' not in workflow
assert 'ln -s ../toolchains dxmt/toolchains' in workflow
print(f'PASS: {checked} external DXMT headers, workflow scripts and Xcode source paths')
