"""Check active navigation and inventory; does not establish semantic PRD compliance."""
import json
import re
from pathlib import Path
from urllib.parse import unquote

vault = Path(__file__).resolve().parents[1]
skip_dirs = {'archive', 'reviews', '.obsidian', 'prd'}
skip_names = {'OVERVIEW.md', 'm1.md', 'model_router_design_en.md',
              'model_router_design_en-v1.4-2026-10-01.md', 'capsule-inventory-proposal.md'}


def slugs(path):
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'^```[^\n]*\n.*?^```[ \t]*$', '', text, flags=re.S | re.M)
    result, counts = set(), {}
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, re.M):
        heading = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', heading).lower()
        slug = re.sub(r'[^\w\- ]', '', heading).replace(' ', '-')
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug + (f'-{count}' if count else ''))
    result.update(re.findall(r'(?:id|name)=["\']([^"\']+)["\']', text))
    return result


errors, checked = [], 0
cache = {}
for page in sorted(vault.rglob('*.md')):
    if any(part in skip_dirs for part in page.relative_to(vault).parts) or page.name in skip_names:
        continue
    text = re.sub(r'^```[^\n]*\n.*?^```[ \t]*$', '', page.read_text(encoding='utf-8'), flags=re.S | re.M)
    for destination in re.findall(r'(?<!!)\[[^]\n]*\]\(([^)\n]+)\)', text):
        if destination.startswith(('http:', 'https:', 'mailto:', 'app:', 'codex:')):
            continue
        location, _, fragment = destination.strip('<>').partition('#')
        target = (page.parent / unquote(location)).resolve() if location else page
        if not target.exists():
            errors.append(f'{page.relative_to(vault)}: missing {destination}')
        elif fragment and target.suffix == '.md':
            if target not in cache:
                cache[target] = slugs(target)
            if unquote(fragment).lower() not in cache[target]:
                errors.append(f'{page.relative_to(vault)}: missing anchor {destination}')
        checked += 1

pipeline = (vault / 'm1/pipeline.md').read_text(encoding='utf-8')
plan = json.loads(re.search(r'```json\s*\n(.*?)```', pipeline, re.S).group(1))
expected = {step['capsule_name'] for step in plan['steps']}
expected.update(step['gate_capsule_name'] for step in plan['steps'])
expected.update(re.findall(r'`(op\.[a-z_]+)`', pipeline.split('Total: twelve')[0]))
guide = (vault / 'm1/capability-designs.md').read_text(encoding='utf-8')
actual = re.findall(r'^### \d+\. `([^`]+)`', guide, re.M)
assert len(actual) == len(set(actual)), 'Duplicate capsule design packet'
assert set(actual) == expected, (set(actual) - expected, expected - set(actual))
coverage = (vault / 'prd/coverage.md').read_text(encoding='utf-8')
for stage in range(10):
    assert re.search(rf'^\| {stage} \(6\.', coverage, re.M), f'PRD stage {stage} missing'
for track in range(1, 4):
    assert f'| Track {track}:' in coverage
if errors:
    print('\n'.join(errors))
    print(f'{len(errors)} navigation errors across {checked} checked links')
    raise SystemExit(1)
print(f'{checked} active local file/anchor links agree; {len(actual)} capability packets match inventory')
print('Three tracks and ten PRD construction stages have navigation rows; semantic compliance and runtime remain separately reviewed.')

# Simplified presentation must show every current capsule without inventing identities.
overview = (vault / 'system/overall-draft.md').read_text(encoding='utf-8')
first_view = re.search(r'```mermaid\s*\n(.*?)```', overview, re.S).group(1)
overview_capsules = re.findall(r'CC: ([a-z_]+\.[a-z_]+)', first_view)
assert len(overview_capsules) == len(set(overview_capsules)), 'Duplicate capsule in overview'
assert set(overview_capsules) == expected, 'Overview differs from canonical capsule inventory'
print(f'{len(overview_capsules)} overview CC identities match the production/operator inventory')

flow_views = (vault / 'system/information-flow.md').read_text(encoding='utf-8')
step_nodes = {step['step_id']: f'P{i}' for i,step in enumerate(plan['steps'])}
expected_bindings = set()
for step in plan['steps']:
    for port,binding in step['inputs'].items():
        producer,payload = binding.split('.',1)
        expected_bindings.add(('IN' if producer == 'launcher' else step_nodes[producer],payload,port,step_nodes[step['step_id']]))
for name,has_views,has_rsi in [('full',True,True),('no-observability',False,True),('no-rsi',True,False),('core',False,False)]:
    body = re.search(rf'<!-- generated:information-{name} -->(.*?)<!-- /generated:information-{name} -->',flow_views,re.S).group(1)
    actual_bindings = re.findall(r'([A-Z0-9]+) -->\|"([a-z_]+) to ([a-z_]+)"\| (P\d+)',body)
    assert len(actual_bindings) == len(set(actual_bindings)),name+' duplicate input edge'
    assert set(actual_bindings) == expected_bindings,name+' missing/extra canonical binding'
    assert ('VIEWS[' in body) == has_views,name+' incorrect observation filter'
    assert ('RSI[' in body) == has_rsi,name+' incorrect RSI filter'
    assert all(node+'[' in body for node in ('STORE','GATE','MODEL','EXPORT')),name+' removed required authority/I/O'
    for publication_input in ('poc_bundle_ref','benchmark_payload_ref','stage_context_ref','destination_ref'):
        assert publication_input in body,name+' omitted publisher input '+publication_input
print(f'Four information-flow variants preserve all {len(expected_bindings)} canonical input bindings and required boundaries')

# Showcase is a seven-page derived reading package.
from showcase_views import refresh as check_showcase
assert check_showcase(vault, check=True), "Stale showcase projection"
assert len(list((vault / "presentation/showcase").glob("*.md"))) == 7
for name in ("full", "no-observability", "no-rsi", "core"):
    body = re.search(rf"<!-- generated:information-{name} -->(.*?)<!-- /generated:information-{name} -->", flow_views, re.S).group(1)
    assert 'P3 -->|"query, repository snapshot and top_k"| CODE' in body
    assert 'CODE -->|"code_hits: mechanism source ranges"| P3' in body
print("Seven showcase pages and generated owner projections agree; Hypothesis CodeSearch flow retained")

# Corrected main flow is derived from its owner, not the fixed research baseline.
control = (vault / "m1/control-flow.md").read_text(encoding="utf-8")
for required in ("SwarmFlow", "shared research.verifier", "RSI mutable components: 0", "no next or sibling capsule starts", "Delivery: ordinary processing and publication"):
    assert required in control, "Corrected diagram missing " + required
print("Corrected M1 flow includes shared verifier, zero Gate RSI mutability, whole-run halt and ordinary delivery")
