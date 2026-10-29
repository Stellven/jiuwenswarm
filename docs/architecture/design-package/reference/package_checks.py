"""Portable delivery boundaries; called by validate.py, also used by negative fixtures."""
import ast
import hashlib
import json
import re
from pathlib import Path


def delivery_issues(root):
    root = Path(root).resolve()
    issues = []
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            issues.append('Escaping package file: ' + rel)
        if 'sources' in path.relative_to(root).parts or 'received' in path.relative_to(root).parts:
            issues.append('Received source collection in delivery: ' + rel)
        if path.suffix.lower() not in ('.md', '.txt', '.json'):
            continue
        text = path.read_text(encoding='utf-8-sig')
        if re.search(r'(?:^|[\s"\x27(/])(?:\.\./)*sources/', text):
            issues.append('Removed source reference: ' + rel)
        if re.search(r'(?:received/|received-prds/|source-archive/|model-router-design-en|capsule-semantic-v|policy-m1\.json)', text, re.I):
            issues.append('Archived input reference: ' + rel)
        if re.search(r'https?://github\.com/[^/]+/jiuwenswarm/(?:tree|blob)/[0-9a-f]{7,40}/docs/', text):
            issues.append('Historical design reading link: ' + rel)
        # A PRD body is excluded regardless of filename or ordinary text extension.
        if len(re.findall(r'^#{2,5}\s+\d+\.\d+(?:\.\d+)?\s+', text, re.M)) >= 100:
            issues.append('Bundled PRD body: ' + rel)
    receipt = json.loads((root / 'reference/native-reuse-evidence.json').read_text(encoding='utf-8'))
    expected_areas = {'workflow', 'workflow_transport', 'agent_execution', 'agent_registration',
                      'codex_transport', 'codex_session', 'web_ui', 'configuration',
                      'observability', 'observability_lifecycle', 'symphony_adapter', 'dependency_pin'}
    rows = receipt.get('jiuwenswarm_files', [])
    if {row.get('area') for row in rows} != expected_areas or len(rows) != len(expected_areas):
        issues.append('Incomplete or duplicate JiuwenSwarm reuse coverage')
    for row in rows:
        p = Path(row['path'])
        if p.is_absolute() or '..' in p.parts or not row.get('observation') or not row.get('required_adaptation'):
            issues.append('Invalid reuse record: ' + row['path'])
        if row.get('commit') != receipt.get('jiuwenswarm_commit') or not re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')):
            issues.append('Invalid reuse identity: ' + row['path'])
    if receipt.get('runtime_compatibility') != 'NOT_RUN':
        issues.append('Source inspection cannot claim runtime compatibility')
    projection = receipt.get('diagram_projection', {})
    if not projection:
        issues.append('Missing native reuse diagram projection')
    if projection:
        document = root / projection['document']
        svg = root / projection['svg']
        block = re.search(r'```mermaid\s*\n(.*?)```', document.read_text(encoding='utf-8'), re.S)
        if not block or hashlib.sha256(block[1].encode()).hexdigest() != projection['mermaid_sha256']:
            issues.append('Native reuse diagram source drift')
        if not svg.is_file() or hashlib.sha256(svg.read_bytes()).hexdigest() != projection['svg_sha256']:
            issues.append('Native reuse diagram projection drift')
    core_rows = receipt.get('openjiuwen_files', [])
    if len(core_rows) != 7 or len({r['path'] for r in core_rows}) != 7 or not re.fullmatch('[0-9a-f]{40}', receipt.get('openjiuwen_dependency_commit', '')):
        issues.append('Missing pinned OpenJiuwen observations')
    for row in core_rows:
        if row.get('commit') != receipt['openjiuwen_dependency_commit'] or not re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')):
            issues.append('Invalid OpenJiuwen source identity: ' + row['path'])
    clause_index = json.loads((root / 'reference/prd-clause-index.json').read_text(encoding='utf-8'))
    provenance = json.loads((root / 'reference/provenance.json').read_text(encoding='utf-8'))
    product = (root / 'reference/product-input.md').read_text(encoding='utf-8')
    if provenance.get('current_product_sha256') != clause_index['source_sha256'] or clause_index['source_sha256'] not in product:
        issues.append('External PRD identity differs from clause mapping')
    catalog = (root / 'side-systems/model-catalog.md').read_text(encoding='utf-8')
    inventory = re.findall(r'^\| `(E|T)` \| `([^`]+)`', catalog, re.M)
    if len(inventory) != 24 or len({i[1] for i in inventory}) != 24 or sum(i[0] == 'E' for i in inventory) != 12:
        issues.append('Incomplete or duplicate adopted routing inventory')
    cases = (root / 'side-systems/routing-acceptance.md').read_text(encoding='utf-8')
    ids = re.findall(r'^\| (A\d\d) \|', cases, re.M)
    if ids != ['A%02d' % i for i in range(1, 41)]:
        issues.append('Incomplete or duplicate routing acceptance identities')
    return issues


def source_issues(root, read_blob):
    """Verify recorded Git blobs via an injected reader; portable checks need no checkout."""
    receipt = json.loads((Path(root) / 'reference/native-reuse-evidence.json').read_text(encoding='utf-8'))
    issues = []
    for repo, rows in (('jiuwenswarm', receipt['jiuwenswarm_files']), ('openjiuwen', receipt['openjiuwen_files'])):
        for row in rows:
            data = read_blob(repo, row['commit'], row['path'])
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                issues.append('Reuse source hash differs: ' + row['path'])
            if row['path'].endswith('.py'):
                symbols = {n.name: n.lineno for n in ast.parse(data).body
                           if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
                for symbol in row.get('symbols', row.get('classes', [])):
                    if symbols.get(symbol['name']) != symbol['line']:
                        issues.append('Reuse source symbol differs: ' + row['path'] + ':' + symbol['name'])
    pin = receipt['openjiuwen_dependency_commit']
    manifest = next(row for row in receipt['jiuwenswarm_files'] if row['area'] == 'dependency_pin')
    if ('agent-core.git@' + pin).encode() not in read_blob('jiuwenswarm', manifest['commit'], manifest['path']):
        issues.append('Reuse dependency differs from actual project pin')
    return issues
