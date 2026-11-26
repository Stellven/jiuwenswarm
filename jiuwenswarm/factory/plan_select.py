"""What the planner may choose from for a single TaskInput: eligible capsules, features,
interference, hardware risks, and merge options.

Everything here is computed deterministically by the host from the TaskInput and the
capsule catalog. The model designs its own step DAG directly in Plan IR (``plan_ir``)
with full visibility into the CC Library, and ``plan_compile`` compiles and verifies it.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

import yaml

from . import plan_catalog
from . import requirements as req

CLUSTER_WEIGHT = 6          # M2 merges units joined by at least this much interference first
STOP = {'build', 'builds', 'the', 'and', 'with', 'for', 'stock', 'llama', 'cpp', 'single', 'only', 'using'}
ARCH_ALIAS = {'aarch64': 'arm64', 'x86_64': 'amd64'}


def _tokens(text):
    return {t for t in re.findall(r'[a-z0-9]+', (text or '').lower()) if len(t) > 2 and t not in STOP}


def _component_spec(capsule):
    paths = glob.glob(str(plan_catalog.CCS / capsule['folder'] / 'components' / '*' / 'component.yaml'))
    for path in sorted(paths):
        spec = yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
        if spec.get('kind') == 'builder_spec':
            return spec
    return {}


def _ontology_regions(capsule):
    path = plan_catalog.CCS / capsule['folder'] / 'ONTOLOGY.yaml'
    if not path.is_file():
        return []
    regions = (yaml.safe_load(path.read_text(encoding='utf-8')) or {}).get('regions') or {}
    return sorted(regions.keys()) if isinstance(regions, dict) else []


def unit_name(capsule_id):
    """Short step name of a capsule: the last word of its name (engine.build_expert_weight_cache -> cache)."""
    return capsule_id.rsplit('.', 1)[-1].removeprefix('build_').rsplit('_', 1)[-1]


def _hardware(spec, target):
    host = (spec.get('supported') or {}).get('host') or {}
    wanted = target if isinstance(target, dict) else {}
    declared = host.get('cuda_arch')
    if wanted.get('sm') and declared:
        match = declared == 'sm_' + str(wanted['sm'])
        return dict(match=match, declared=f"{host.get('name')} {declared}",
                    target=f"{wanted.get('profile')} sm_{wanted['sm']}",
                    detail='declared for the target' if match else
                    f"declared for {host.get('name')} {declared}; the task targets {wanted.get('profile')} sm_{wanted['sm']}")
    host_arch = ARCH_ALIAS.get(host.get('arch'), host.get('arch'))
    target_arch = ARCH_ALIAS.get(wanted.get('arch'), wanted.get('arch'))
    if host_arch and target_arch:
        match = host_arch == target_arch
        return dict(match=match, declared=f"{host.get('name')} {host.get('arch')}",
                    target=f"{wanted.get('profile')} {wanted.get('arch')}",
                    detail='declared for the target architecture' if match else
                    f"declared for {host.get('name')} {host.get('arch')}; the task targets {wanted.get('arch')}")
    return dict(match=None, declared=host.get('name'), target=wanted.get('profile'),
                detail='hardware compatibility not declared')


def _primary_cap(capsule):
    if capsule['builder']:
        return 'verify'
    if 'verify_pack' in capsule['verifiers']:
        return 'verify_pack'
    return capsule['verifiers'][0] if capsule['verifiers'] else ''


def _candidate(capsule, spec, query_text, target, must_include=False):
    component = capsule.get('component')
    comp_name = component['name'] if component else capsule['folder']
    id_words = _tokens(' '.join([capsule['id'].replace('_', ' ').replace('.', ' '), comp_name.replace('_', ' ')]))
    summary_words = _tokens(capsule['summary'][:300])
    wanted = _tokens(query_text)
    score = (2 * len(wanted & id_words) + len(wanted & (summary_words - id_words))) / (2 * len(wanted)) if wanted else 0.0
    regions = component['modifies_region'] if component else _ontology_regions(capsule)
    touches = list(component['touches']) if component else []
    primary_cap = _primary_cap(capsule)
    acceptance = (spec.get('acceptance') or {}).get('type') if spec else ('correctness' if primary_cap != 'verify' else 'observability')
    return dict(
        capsule=capsule['id'], version=capsule['version'], unit=unit_name(capsule['id']),
        kind='builder' if capsule['builder'] else 'tool',
        change_kind=(component or {}).get('change_kind') or capsule.get('atlas_kind') or 'tool',
        verify=f"{capsule['id']}.{primary_cap}" if primary_cap else '',
        verifiers=[f"{capsule['id']}.{v}" for v in capsule['verifiers']],
        component=comp_name, must_include=must_include,
        features=dict(
            hardware=_hardware(spec, target) if spec else dict(match=None, declared=None, target=None,
                                                               detail='tool capsule (host-independent)'),
            name_match=round(score, 2),
            acceptance=acceptance,
            slices=capsule['slices'],
            regions=regions, files=len(touches), touches=touches))


def unit_components(units, catalog=None):
    """{unit: component-like {touches, modifies_region}}: a two-capsule unit changes the union."""
    capsules = (catalog or plan_catalog.load())['capsules']
    result = {}
    for unit, spec in units.items():
        cap_ids = spec['capsules'].values() if isinstance(spec.get('capsules'), dict) else spec.get('capsules', [])
        parts = [capsules[c]['component'] for c in cap_ids if c in capsules and capsules[c]['component']]
        result[unit] = dict(touches=sorted({f for p in parts for f in p['touches']}),
                            modifies_region=sorted({r for p in parts for r in p['modifies_region']}))
    return result


def interference(units):
    """Pairwise shared files and regions of the units' components; weight = files + regions."""
    rows, names = [], sorted(units)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            files = sorted(set(units[a]['touches']) & set(units[b]['touches']))
            regions = sorted(set(units[a]['modifies_region']) & set(units[b]['modifies_region']))
            if files or regions:
                rows.append(dict(a=a, b=b, files=files, regions=regions, weight=len(files) + len(regions)))
    return sorted(rows, key=lambda r: (-r['weight'], r['a'], r['b']))


def merge_options(unit_ids, pairs):
    """Merge structures over the diff units: each is a list of stages, the last one final."""
    units = sorted(unit_ids)
    if len(units) < 2:
        return {}
    weight = {frozenset((p['a'], p['b'])): p['weight'] for p in pairs}
    options = {'M1': dict(summary='One merge of every change.', stages=[dict(id='combine', members=units)])}
    parent = {u: u for u in units}

    def root(u):
        while parent[u] != u:
            u = parent[u]
        return u

    for pair in pairs:
        if pair['weight'] >= CLUSTER_WEIGHT and pair['a'] in parent and pair['b'] in parent:
            parent[root(pair['a'])] = root(pair['b'])
    clusters = {}
    for unit in units:
        clusters.setdefault(root(unit), []).append(unit)
    heavy = sorted((sorted(c) for c in clusters.values() if len(c) > 1), key=lambda c: (-len(c), c))
    if heavy and not (len(heavy) == 1 and len(heavy[0]) == len(units)):
        stages = [dict(id=f'merge_{i + 1}', members=cluster) for i, cluster in enumerate(heavy)]
        rest = [u for u in units if not any(u in c for c in heavy)]
        stages.append(dict(id='combine', members=[s['id'] for s in stages] + rest))
        options['M2'] = dict(summary=f'Merge the heavily interfering clusters first (weight >= {CLUSTER_WEIGHT}), '
                                     'then the rest.', stages=stages)
    if len(units) > 2:
        first = max(((a, b) for i, a in enumerate(units) for b in units[i + 1:]),
                    key=lambda p: (weight.get(frozenset(p), 0), p))
        merged, stages = list(first), [dict(id='merge_1', members=list(first))]
        while len(merged) < len(units):
            nxt = max((u for u in units if u not in merged),
                      key=lambda u: (sum(weight.get(frozenset((u, m)), 0) for m in merged), u))
            merged.append(nxt)
            stages.append(dict(id=f'merge_{len(stages) + 1}', members=[stages[-1]['id'], nxt]))
        stages[-1]['id'] = 'combine'
        options['M3'] = dict(summary='Add one change at a time, most interfering first; each merge reviewed.', stages=stages)
    return options


def _revision_matches(base, engine):
    if not engine or not base:
        return True
    return base == engine or engine.startswith(base) or base.startswith(engine)


def context(task_input, catalog=None):
    """Everything the planner may choose from for one TaskInput, as one JSON-ready document."""
    catalog = catalog or plan_catalog.load()
    subject = task_input['subject']
    target = task_input['target']
    engine = subject['engine']['revision']
    allowed = set(task_input['constraints']['allowed_effects'])
    hints = task_input.get('hints') or {}
    must_include = set(hints.get('must_include') or [])
    excludes = set(hints.get('excludes') or [])

    query_parts = [
        task_input['objective'],
        subject['model']['name'],
        subject['model']['format'],
        *[c['description'] for c in task_input['acceptance_criteria']],
        *(task_input.get('notes') or []),
    ]
    query_text = ' '.join(query_parts)

    candidates, rejected, unrealizable = [], [], []
    all_capsules = sorted(catalog['capsules'].values(), key=lambda c: c['id'])
    specs = {c['id']: (_component_spec(c) if c['builder'] else {}) for c in all_capsules}

    for capsule in all_capsules:
        cid = capsule['id']
        if not capsule['realizable']:
            continue
        if cid in excludes:
            rejected.append(dict(capsule=cid, rule='H1', reason='excluded by TaskInput hints.excludes'))
            continue
        spec = specs[cid]
        base = (spec.get('base') or {}).get('commit')
        if not _revision_matches(base, engine):
            rejected.append(dict(capsule=cid, rule='H2',
                                 reason=f'built against {base[:9]}, the task pins {engine[:9]}'))
            continue
        cap_name = _primary_cap(capsule)
        needs = set(capsule['capabilities'][cap_name]['changes']) if cap_name else set()
        if needs - allowed:
            rejected.append(dict(capsule=cid, rule='H3',
                                 reason=f'{cap_name} needs {sorted(needs - allowed)} beyond the allowed effects'))
            continue
        candidates.append(_candidate(capsule, spec, query_text, target, must_include=(cid in must_include)))

    candidates.sort(key=lambda c: (not c['must_include'], -c['features']['name_match'], c['capsule']))
    eligible_ids = {c['capsule'] for c in candidates}
    for pinned in sorted(must_include - eligible_ids):
        unrealizable.append(f'required capsule {pinned} did not pass hard filters')
    if not candidates:
        unrealizable.append('no realizable capsule in the catalog satisfies the engine revision and allowed effects')

    diff_units = {c['unit']: catalog['capsules'][c['capsule']]['component']
                  for c in candidates if c['kind'] == 'builder' and catalog['capsules'][c['capsule']]['component']}
    pairs = interference(diff_units)
    risks = [dict(unit=c['unit'], capsule=c['capsule'], kind='hardware', detail=c['features']['hardware']['detail'])
             for c in candidates if c['features']['hardware']['match'] is False]

    return dict(
        format='factory.plan-selection/1',
        task_id=req.input_id(task_input),
        engine_revision=engine,
        target=target,
        subject=subject,
        acceptance_criteria=list(task_input['acceptance_criteria']),
        must_include=sorted(must_include),
        candidates=candidates,
        rejected=rejected,
        unrealizable=unrealizable,
        risks=risks,
        interference=pairs,
        merge_options=merge_options(list(diff_units), pairs),
    )
