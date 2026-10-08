"""Read-only documentation experiment checks; no agent trials or runtime claims.

python validate_comparison.py [full-input-root] [cut-input-root]
Default roots resolve from the comparison manifest; the original full input is preserved.
"""
from pathlib import Path
import copy
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / 'm1-comparison.json').read_text(encoding='utf-8'))
FULL = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (HERE / MANIFEST['full_root']).resolve()
CUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else (HERE / MANIFEST['cut_root']).resolve()


def manifest_issues(manifest):
    result = []
    for key in ('full_files', 'cut_files', 'identical_files', 'identical_tables', 'identical_mermaid', 'explanatory_files', 'words', 'immediate_words'):
        if not manifest.get(key):
            result.append('missing/empty collection: ' + key)
    names = manifest.get('identical_files', [])
    required = {p.relative_to(FULL).as_posix() for folder in ('reference', 'sources') for p in (FULL / folder).rglob('*') if p.is_file()}
    required.update({'capsule/declaration.md','capsule/authoring.md','glossary.md','coverage-allocation.md','design-method.md','decision-review.md','principles.md'})
    if set(names) != required or len(names) != len(set(names)):
        result.append('missing/duplicate contract-source identity coverage')
    explanatory = manifest.get('explanatory_files', [])
    if len(explanatory) != 20 or len(set(explanatory)) != 20:
        result.append('incomplete/duplicate explanatory measurement scope')
    expected_tables = {
        ('decision-review.md','Decisions and source amendments'),
        ('delivery-phases.md','Full M1 phases'),
        ('research-design.md','Research path and ports'),
        ('research-design.md','Data and state ownership'),
        ('research-design.md','Architectural component obligations'),
        ('phase-details.md','Every implementation stage'),
        ('phase-details.md','Delivery Phase 3 integration accounting'),
        ('phase-details.md','Source corrections and boundaries'),
        ('README.md','Responsibility and authority'),
        ('m1-design.md','Full M1 and the next build'),
        ('placement.md','Dependency preparation and provisioning'),
    }
    selected = manifest.get('identical_tables', [])
    if len(selected)!=len(expected_tables) or {tuple(x) for x in selected}!=expected_tables:
        result.append('missing/duplicate required responsibility/phase tables')
    return result


assert not manifest_issues(MANIFEST), manifest_issues(MANIFEST)


def issues(root, inventory):
    result = []
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(inventory):
        result.append('missing/extra input files')
    for name, expected in inventory.items():
        p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()) or not p.is_file():
            result.append('escaping/missing file: ' + name)
        elif hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            result.append('changed bytes: ' + name)
    return result


assert not issues(FULL, MANIFEST['full_files']), issues(FULL, MANIFEST['full_files'])
assert not issues(CUT, MANIFEST['cut_files']), issues(CUT, MANIFEST['cut_files'])
for group in MANIFEST['identical_files']:
    assert (FULL / group).read_bytes() == (CUT / group).read_bytes(), group


def block(root, name, heading):
    text = (root / name).read_text(encoding='utf-8')
    m = re.search(r'^## ' + re.escape(heading) + r'\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    assert m, (name, heading)
    return '\n'.join(line for line in m.group(1).splitlines() if line.startswith('|'))


for name, heading in MANIFEST['identical_tables']:
    assert block(FULL, name, heading) == block(CUT, name, heading), (name, heading)
for source in MANIFEST['identical_mermaid']:
    pattern = r'```mermaid\s*\n(.*?)```'
    a = re.findall(pattern, (FULL / source).read_text(encoding='utf-8'), re.S)
    b = re.findall(pattern, (CUT / source).read_text(encoding='utf-8'), re.S)
    assert a and a == b, 'selected diagram meaning changed: ' + source
for condition, root in [('full', FULL), ('cut', CUT)]:
    words = sum(len((root / name).read_text(encoding='utf-8').split()) for name in MANIFEST['explanatory_files'])
    assert words == MANIFEST['words'][condition], 'word-count drift: ' + condition
    immediate=sum(len((root/name).read_text(encoding='utf-8').split()) for name in ['README.md','principles.md','m1-design.md'])
    assert immediate==MANIFEST['immediate_words'][condition], 'immediate-route word-count drift: '+condition
    subprocess.run([sys.executable, str(root / 'reference/validate.py'), str(root)], check=True)

# In-memory negative fixtures prove inventory drift and path escape are rejected.
inventory = MANIFEST['cut_files']
bad = copy.deepcopy(inventory); bad.pop(next(iter(bad)))
assert issues(CUT, bad)
bad = copy.deepcopy(inventory); bad[next(iter(bad))] = '0' * 64
assert issues(CUT, bad)
bad = copy.deepcopy(inventory); bad['../../outside.md'] = '0' * 64
assert issues(CUT, bad)
bad = copy.deepcopy(MANIFEST); bad['identical_files'] = []
assert manifest_issues(bad)
bad = copy.deepcopy(MANIFEST); bad['identical_files'].append(bad['identical_files'][0])
assert manifest_issues(bad)
bad = copy.deepcopy(MANIFEST); bad.pop('identical_tables')
assert manifest_issues(bad)
bad = copy.deepcopy(MANIFEST); bad['identical_tables'].pop()
assert manifest_issues(bad)
bad = copy.deepcopy(MANIFEST); bad.pop('immediate_words')
assert manifest_issues(bad)
notes=json.loads((HERE/'compression-notes.json').read_text(encoding='utf-8'))
for name, counts in notes['final_words'].items():
    for condition, root in [('full',FULL),('cut',CUT)]:
        assert counts[condition]==len((root/name).read_text(encoding='utf-8').split()), 'compression accounting drift'
print('PASS: revised frozen inventories, identical contracts/sources/tables, word counts, both portable validators; 8 negative inventory/manifest fixtures')
print('LIMIT: no paired agent builds, human review completion, model quality or runtime acceptance demonstrated')
