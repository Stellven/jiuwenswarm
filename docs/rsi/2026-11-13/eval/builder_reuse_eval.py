#!/usr/bin/env python3
"""Offline evaluation of a factory.builder reuse key against the recorded Satay builds.

Replays fixtures/builds.json (29 recorded build attempts, 11-12 Nov, chronological) through a
reuse-key function and reports what the builder would have skipped. No Docker, GPU, build or
network. Runs in well under a second.

  python3 -I eval/builder_reuse_eval.py --key baseline         # frozen builder behaviour
  python3 -I eval/builder_reuse_eval.py --key oracle           # upper bound: strict input identity
  python3 -I eval/builder_reuse_eval.py --key path/to/key.py:reuse_key   # your candidate

A candidate is `reuse_key(build) -> str | None`. `build` is one fixture record: `request`
(what builder.submit normalizes), `toolchain`, `jetpack`, `l4t`, `base_runtime` (what the
build prep probes), and `task_id`. It must not read `image_id`, `duration_s` or `state`,
because those are outcomes. Returning None means "never reuse".

Hard constraints (exit 1 if violated):
  * false_hits == 0: no reuse across different semantic build inputs.
  * mutation check: changing any semantic input changes the key (or yields None).
Reported, not gated: hits, seconds saved, oracle opportunities missed, and whether the key
survives non-semantic changes (commit, tag, deadline, node, task, PATH order).
"""
import argparse, copy, importlib.util, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUTCOME_FIELDS = ('image_id', 'duration_s', 'state', 'started', 'ended', 'attempt_id')


def semantic_inputs(b):
    """Reference identity of everything that can change the built engine."""
    q = b['request']
    return json.dumps(dict(tree=q['source']['tree'], recipe=q.get('recipe_sha256'), engine=q.get('engine_sha256'),
                           target=q.get('target'), toolchain=b.get('toolchain'), jetpack=b.get('jetpack'),
                           l4t=b.get('l4t'), base_runtime=b.get('base_runtime')), sort_keys=True)


def baseline_key(b):
    """Frozen behaviour (jobs.fingerprint + builder_reuse_keys): the whole normalized request,
    including commit, tag, deadline and env, plus argv, which names the task. Reuse is task-local."""
    return json.dumps(dict(task=b['task_id'], request=b['request']), sort_keys=True)


def oracle_key(b):
    return semantic_inputs(b)


def load_key(spec):
    if spec == 'baseline':
        return baseline_key
    if spec == 'oracle':
        return oracle_key
    path, _, name = spec.partition(':')
    mod_spec = importlib.util.spec_from_file_location('candidate_key', path)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    return getattr(mod, name or 'reuse_key')


def visible(b):
    """What a candidate may see: drop outcome fields so a key cannot cheat."""
    return {k: copy.deepcopy(v) for k, v in b.items() if k not in OUTCOME_FIELDS}


def replay(builds, key):
    cache, rows = {}, []
    for b in builds:
        k = key(visible(b))
        src = cache.get(k) if k is not None else None
        row = dict(attempt=b['attempt_id'][:8], task=b['task_id'][:16], tree=b['request']['source']['tree'][:10],
                   state=b['state'], duration_s=b['duration_s'], reused_from=src['attempt_id'][:8] if src else None,
                   false_hit=bool(src) and semantic_inputs(src) != semantic_inputs(b))
        rows.append(row)
        if b['state'] == 'succeeded' and k is not None and k not in cache:
            cache[k] = b
    return rows


SEMANTIC_MUTATIONS = {
    'source.tree': lambda q, b: q['request']['source'].__setitem__('tree', '0' * 40),
    'recipe_sha256': lambda q, b: q['request'].__setitem__('recipe_sha256', 'f' * 64),
    'engine_sha256': lambda q, b: q['request'].__setitem__('engine_sha256', 'e' * 64),
    'target': lambda q, b: q['request'].__setitem__('target', 'jetson-thor'),
    'toolchain.nvcc': lambda q, b: q['toolchain'].__setitem__('nvcc', 'Build cuda_12.8.r12.8/compiler.0'),
    'toolchain.gcc': lambda q, b: q['toolchain'].__setitem__('gcc', 'gcc (Ubuntu 13.3.0) 13.3.0'),
    'jetpack': lambda q, b: q.__setitem__('jetpack', '7.0.0'),
    'base_runtime': lambda q, b: q.__setitem__('base_runtime', 'nvcr.io/nvidia/l4t-cuda:13.0-runtime@sha256:' + 'a' * 64),
}
NONSEMANTIC_MUTATIONS = {
    'source.commit': lambda q, b: q['request']['source'].__setitem__('commit', '1' * 40),
    'tag': lambda q, b: q['request'].__setitem__('tag', 'factory/llamacpp:renamed'),
    'deadline_s': lambda q, b: q['request'].__setitem__('deadline_s', 12345),
    'node_id': lambda q, b: q['request'].__setitem__('node_id', 'node-other'),
    'task_id': lambda q, b: q.__setitem__('task_id', 'factory-other-task'),
    'env.PATH order': lambda q, b: q['request']['env'].__setitem__('PATH', ':'.join(reversed(q['request']['env'].get('PATH', '').split(':')))),
}


def mutation_check(builds, key):
    broken, kept, total = {}, {}, 0
    for b in builds:
        if b['state'] != 'succeeded' or not b.get('toolchain'):
            continue
        total += 1
        k0 = key(visible(b))
        for name, mutate in SEMANTIC_MUTATIONS.items():
            m = visible(b); mutate(m, b)
            k1 = key(m)
            if k0 is not None and k1 == k0:
                broken[name] = broken.get(name, 0) + 1
        for name, mutate in NONSEMANTIC_MUTATIONS.items():
            m = visible(b); mutate(m, b)
            if k0 is not None and key(m) == k0:
                kept[name] = kept.get(name, 0) + 1
    return dict(builds_checked=total, semantic_changes_missed=broken,
                nonsemantic_changes_survived={k: f'{v}/{total}' for k, v in kept.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', default='baseline')
    ap.add_argument('--fixture', default=str(HERE / 'fixtures/builds.json'))
    ap.add_argument('--rows', action='store_true', help='print every replayed build')
    a = ap.parse_args()
    builds = json.load(open(a.fixture))['builds']
    key = load_key(a.key)
    rows = replay(builds, key)
    oracle = replay(builds, oracle_key)
    ok = [r for r in rows if r['state'] == 'succeeded']
    hits = [r for r in ok if r['reused_from']]
    failed_avoided = [r for r in rows if r['state'] != 'succeeded' and r['reused_from']]
    oracle_hits = {r['attempt'] for r in oracle if r['state'] == 'succeeded' and r['reused_from']}
    total_s = sum(r['duration_s'] or 0 for r in ok)
    saved_s = sum(r['duration_s'] or 0 for r in hits)
    result = dict(key=a.key, builds=len(rows), succeeded=len(ok), hits=len(hits),
                  false_hits=sum(r['false_hit'] for r in rows),
                  hits_on_failed_or_unfinished_attempts=len(failed_avoided),
                  oracle_hits=len(oracle_hits), missed_vs_oracle=len(oracle_hits - {r['attempt'] for r in hits}),
                  build_seconds_recorded=round(total_s), build_seconds_saved=round(saved_s),
                  saved_fraction=round(saved_s / total_s, 3) if total_s else None,
                  mutation=mutation_check(builds, key))
    if a.rows:
        for r in rows:
            print(json.dumps(r))
    print(json.dumps(result, indent=1))
    bad = result['false_hits'] or result['mutation']['semantic_changes_missed']
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
