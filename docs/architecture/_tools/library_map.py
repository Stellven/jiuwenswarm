"""Generate the library map in README.md and exports/library-manifest.json from page front matter.

Usage: python library_map.py [--check]
The map lists every page by folder with its title, so the README is the one navigation document.
The manifest gives each file's sha256 and size and a bundle revision, so evidence can name what it was run against.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

V = Path(__file__).resolve().parent.parent
CHECK = '--check' in sys.argv
GROUPS = [
    ('Start here (present level)', None, ['README.md', 'terms.md', 'flow.md', 'flow-variants.md', 'placement.md', 'k8s-lens.md', 'reuse.md',
                                         'isolation.md', 'verification.md', 'runtime.md', 'rsi.md', 'build-order.md', 'v-model.md',
                                         'stories.md', 'decisions.md', 'prd-map.md', 'standards.md']),
    ('Capabilities: every CC and ordinary module', 'capabilities', None),
    ('Capsule specification: Declaration, runner, tools, Gates, admission, library, RSI', 'capsule', None),
    ('System: modules, lifecycle, storage, environment, planner, workstation', 'system', None),
    ('Payload types (field tables, one per type)', 'types', None),
    ('Record schemas and policy', 'schemas', None),
    ('Communication contracts: JSON Schemas, fixtures, indexes', 'contracts', None),
    ('Model routing and data foundation (source designs)', None, ['model-routing/README.md', 'model_router_design_en.md',
                                                              'data-foundation/capsule-run-records.md']),
]
SKIP_PARTS = {'.obsidian', '_tools', 'exports'}


def title(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'^# (.+?)$', re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S), re.M)
    t = m.group(1).strip() if m else path.stem
    return re.sub(r'\s*[·|].*$', '', t).replace('|', '/').replace('`', '')[:90]


def files_of(folder):
    out = []
    for p in sorted((V / folder).rglob('*')):
        if p.is_file() and p.suffix in ('.md', '.json') and not (SKIP_PARTS & set(p.relative_to(V).parts)):
            out.append(p)
    return out


def table(paths):
    rows = ['| Page | What it is |', '|---|---|']
    for p in paths:
        rel = p.relative_to(V).as_posix()
        label = rel
        ttl = title(p) if p.suffix == '.md' else ('JSON Schema' if p.name.endswith('.schema.json') else
                                                  'Fixtures' if 'fixtures' in rel else 'Data')
        rows.append(f'| [{label}]({rel}) | {ttl} |')
    return '\n'.join(rows)


def build_map():
    seen, out = set(), []
    for name, folder, listed in GROUPS:
        paths = [V / x for x in listed if (V / x).exists()] if listed else files_of(folder)
        paths = [p for p in paths if p not in seen]
        seen.update(paths)
        out.append(f'### {name}\n\n{table(paths)}\n')
    rest = [p for p in files_of('.') if p not in seen and p.suffix == '.md']
    if rest:
        out.append(f'### Other\n\n{table(rest)}\n')
    return '\n'.join(out)


def manifest():
    entries = []
    for p in sorted(V.rglob('*')):
        if not p.is_file() or (SKIP_PARTS & set(p.relative_to(V).parts)) or p.suffix not in ('.md', '.json'):
            continue
        data = p.read_bytes().replace(b'\r\n', b'\n')
        entries.append({'path': p.relative_to(V).as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    bundle = hashlib.sha256(''.join(f"{e['path']}:{e['sha256']}\n" for e in entries).encode()).hexdigest()
    return {'generated_by': '_tools/library_map.py', 'note': 'Generated. Never edit by hand. bundle_sha256 identifies this exact library.',
            'bundle_sha256': bundle, 'file_count': len(entries), 'files': entries}


def refresh():
    readme = V / 'README.md'
    text = readme.read_text(encoding='utf-8')
    block = '<!-- generated:library-map -->\n' + build_map() + '<!-- /generated:library-map -->'
    pat = r'<!-- generated:library-map -->.*?<!-- /generated:library-map -->'
    if not re.search(pat, text, re.S):
        raise SystemExit('README.md has no library-map markers')
    new = re.sub(pat, lambda _: block, text, flags=re.S)
    m = manifest()
    # the manifest hashes README, which contains the map: write the map first, then hash
    ok = new == text
    if not CHECK:
        readme.write_text(new, encoding='utf-8', newline='\n')
        m = manifest()
    mpath = V / 'exports' / 'library-manifest.json'
    body = json.dumps(m, indent=1) + '\n'
    cur = mpath.read_text(encoding='utf-8') if mpath.exists() else ''
    if CHECK:
        return ok and cur == body
    mpath.write_text(body, encoding='utf-8', newline='\n')
    return True


if __name__ == '__main__':
    good = refresh()
    print('library map and manifest ' + ('current' if good else 'STALE'))
    sys.exit(0 if good else 1)
