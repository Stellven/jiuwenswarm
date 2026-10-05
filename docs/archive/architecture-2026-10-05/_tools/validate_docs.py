"""Navigation and inventory check. Does not establish semantic correctness or runtime behavior.

Checks: every local link and anchor resolves; the capability inventory in capabilities/README.md agrees with
the example plan, the improvement guide and the pages' `provides`; the flow views are current.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
vault = Path(__file__).resolve().parents[1]
skip_dirs = {'.obsidian'}
skip_names = {'OVERVIEW.md', 'model_router_design_en.md'}


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


errors, checked, cache = [], 0, {}
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

inventory = (vault / 'capabilities/README.md').read_text(encoding='utf-8')
rows = re.findall(r'^\| `((?:research|op)\.[a-z_]+)` \|[^\n]*?\[[^\]]+\]\(([^)#]+)', inventory, re.M)
identities = [r[0] for r in rows]
if len(identities) != len(set(identities)):
    errors.append('capabilities/README.md: duplicate identity in inventory')
plan = json.loads((vault / 'capabilities/research-template.plan.json').read_text(encoding='utf-8'))
used = {s['capsule_name'] for s in plan['steps']} | {s['gate_capsule_name'] for s in plan['steps']}
for name in sorted(used - set(identities)):
    errors.append(f'plan uses {name}, missing from the inventory')
guide = (vault / 'capabilities/improvement.md').read_text(encoding='utf-8')
guided = re.findall(r'^### \d+\. `([^`]+)`', guide, re.M)
for name in sorted(set(guided) - set(identities)):
    errors.append(f'improvement guide has {name}, missing from the inventory')
for name, link in rows:
    page = (vault / 'capabilities' / link).resolve()
    if page.exists() and name not in page.read_text(encoding='utf-8'):
        errors.append(f'{name}: not named on its page {link}')

from jsonschema import Draft202012Validator
rp = json.loads((vault / 'exports/schemas/types/run-plan.schema.json').read_text(encoding='utf-8'))
for name in ('prep.plan.json', 'research-template.plan.json'):
    value = json.loads((vault / 'capabilities' / name).read_text(encoding='utf-8'))
    for e in Draft202012Validator(rp).iter_errors(value):
        errors.append(f'capabilities/{name}: {e.message[:120]}')

import flow_views
if not flow_views.refresh(check=True):
    errors.append('flow.md: generated views are stale; run flow_views.py')

if errors:
    print('\n'.join(errors))
    print(f'{len(errors)} navigation errors across {checked} checked links')
    raise SystemExit(1)
print(f'{checked} local links agree; {len(identities)} capability identities in the inventory; flow views current')
