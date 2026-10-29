"""Pre-trial documentation/input checks, not implementation tests."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file()}


def safe_inventory(root, expected):
    assert expected, 'Empty input inventory'
    for name in expected:
        p = (root / name).resolve()
        assert p.is_relative_to(root.resolve()), 'Escaping inventory path: ' + name
    assert inventory(root) == expected, 'Missing/extra/changed input files: ' + str(root)


def slug(title):
    title = re.sub(r'<[^>]*>', '', title).lower().replace('`', '').replace('*', '')
    return re.sub(r'[^\w\- ]', '', title).replace(' ', '-')


def check_links(root):
    count = 0
    for p in root.rglob('*.md'):
        # Received CC bibliography has intentionally historical references.
        if 'sources' in p.relative_to(root).parts and 'product' not in p.relative_to(root).parts:
            continue
        text = re.sub(r'```.*?```', '', p.read_text(encoding='utf-8'), flags=re.S)
        links = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text)
        links += re.findall(r'^\[[^\]]+\]:\s+(\S+)', text, flags=re.M)
        for link in links:
            u = urlsplit(link.strip().strip('<>'))
            if u.scheme or link.startswith('//'):
                continue
            target = (p.parent / unquote(u.path)).resolve() if u.path else p
            assert target.is_relative_to(root.resolve()) and target.exists(), (str(p), link)
            if u.fragment and target.suffix in ('.md', '.txt'):
                headings = re.findall(r'^#{1,6}\s+(.+?)(?:\s+#+)?$', target.read_text(encoding='utf-8'), re.M)
                counts, anchors = {}, set()
                for heading in headings:
                    base = slug(heading)
                    n = counts.get(base, 0)
                    counts[base] = n + 1
                    anchors.add(base + (f'-{n}' if n else ''))
                assert unquote(u.fragment) in anchors, (str(p), link)
            count += 1
    return count


def main():
    import io, tempfile, zipfile
    m = json.loads((HERE / 'inputs.json').read_text(encoding='utf-8'))
    cells = json.loads((HERE / 'deliveries.json').read_text(encoding='utf-8'))
    assert len(cells) == 4 and len({c['branch'] for c in cells}) == 4
    assert {(c['depth'], c['coding_method']) for c in cells} == {(d, w) for d in ('full', 'cut-detail') for w in ('direct', 'spec_kit')}
    local = REPO / m['full_source']
    safe_inventory(local, m['full_files'])
    controls, packages, products = [], [], []
    with tempfile.TemporaryDirectory(prefix='compiler-input-check-') as temp:
        for index, cell in enumerate(cells):
            output = Path(temp) / str(index)
            data = subprocess.check_output(['git', '-C', str(REPO), 'archive', '--format=zip', cell['delivery_commit'], m['full_source']])
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert all((output / n).resolve().is_relative_to(output.resolve()) for n in archive.namelist())
                archive.extractall(output)
            source = output / m['full_source']
            package = source / 'Architecture_context/design-package'
            safe_inventory(source, cell['source_files'])
            safe_inventory(package, cell['package_files'])
            assert len(cell['package_files']) == (255 if cell['depth'] == 'full' else 223)
            assert not (source / 'Architecture_context/design-package-compact').exists()
            for n, h in cell['coder_owned_files'].items():
                assert digest((source / n).read_bytes()) == h
            for n in m['shared_package_files']:
                assert digest((package / n).read_bytes()) == m['compact_package_files'][n]
            controls.append([(source / n).read_bytes() for n in ('Architecture_main_body/Architecture_main_body.md', 'Architecture_context/Architecture_context.md', 'Verification/README.md')])
            products.append([re.sub(r'\s+', ' ', (source / n).read_text(encoding='utf-8').replace('*   4.7 Intention Compilers', '').strip()) for n in m['product_sources']])
            packages.append((cell['depth'], cell['package_files']))
            assert check_links(source) > 900
            subprocess.run([sys.executable, str(package / 'reference/validate.py')], check=True)
        assert all(c == controls[0] for c in controls)
        assert all(p == products[0] for p in products)
        for depth in ('full', 'cut-detail'):
            peers = [p for d, p in packages if d == depth]
            assert peers[0] == peers[1]
    assert len(m['shared_package_files']) == 177
    safe_inventory(HERE / 'fixtures', {Path(n).name:h for n,h in m['fixture_hashes'].items()})
    assert digest((HERE / 'cases.csv').read_bytes()) == m['case_matrix_sha256']
    with (HERE / 'cases.csv').open(encoding='utf-8', newline='') as f: cases = list(csv.DictReader(f))
    with (HERE / 'case-results.template.csv').open(encoding='utf-8', newline='') as f: results = list(csv.DictReader(f))
    ids = [c['case_id'] for c in cases]
    assert len(ids) == 40 and len(set(ids)) == 40
    assert ids == [r['case_id'] for r in results] and all(r['status'] == 'NOT_RUN' for r in results)
    for c in cases:
        assert all(c.values()) and c['severity'] in ('critical', 'major', 'minor')
        for name in re.findall(r'fixtures/[a-z0-9-]+\.txt', c['input_or_action']): assert (HERE / name).is_file()
    assert check_links(local) > 1000
    for bad in ({}, {'../outside':'0'*64}, {k:v for k,v in m['full_files'].items() if k != 'README.md'}):
        try: safe_inventory(local, bad)
        except AssertionError: pass
        else: raise AssertionError('Invalid inventory accepted')
    print('PASS: four committed portable inputs; shared 177 files; identical entrypoints/contracts; equivalent product text; coder-owned records; 40 cases; three negative inventory checks')
    print('LIMIT: documentation/input consistency only; no implementation trials or runtime acceptance')


if __name__ == '__main__':
    main()
