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

# All current views preserve the fixed frontend before planned execution.
flow_views = (vault / 'system/information-flow.md').read_text(encoding='utf-8')
from information_views import refresh as check_information
assert check_information(vault, check=True), 'Stale information-flow projection'
for name,obs,rsi in [('full',True,True),('no-observability',False,True),('no-rsi',True,False),('core',False,False)]:
    body = re.search(rf'<!-- generated:information-{name} -->(.*?)<!-- /generated:information-{name} -->',flow_views,re.S).group(1)
    for edge in ['IG1 -->', 'RC -->', 'RG -->', 'PLAN -->', 'VAL -->', 'BIND -->', 'DATA -->', 'DIS -->', 'SAVE -->', 'GATE -->', 'COMMIT -->', 'PUB -->']:
        assert edge in body, name + ' missing fixed/planned boundary ' + edge
    for node in ['STORE[','MODEL[','EXPORT[','VIEW[','HALT[']:
        assert node in body, name + ' removed authority/output boundary'
    assert ('VIEWS[' in body) == obs
    assert ('RSI[' in body) == rsi
    assert 'Eight fixed production work CCs' not in body
    assert 'shared research.verifier' in body
    assert body.count('IC1[') == 1 and 'IC2' not in body, name + ' must have one intent capsule'
print('Four information-flow variants preserve fixed intake/intent/requirements, planned/frozen DAG, Gates and delivery')
from showcase_views import refresh as check_showcase
assert check_showcase(vault, check=True), 'Stale showcase projection'
assert len(list((vault / 'presentation/showcase').glob('*.md'))) == 7
print('Seven showcase pages agree with canonical projections')
