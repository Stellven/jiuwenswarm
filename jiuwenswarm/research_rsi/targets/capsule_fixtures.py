"""Regenerate source fixture expectations through the selected independent checker.

Run explicitly with ``python -m jiuwenswarm.research_rsi.targets.capsule_fixtures
--capsule NAME --write``. Default is a dry run. This is offline authoring, never
a runtime job or admission. Historical fixture snapshots remain untouched.
"""
from __future__ import annotations
import argparse
import asyncio
import copy
import json
import re
from pathlib import Path
from . import capsules


def _ordered(value, previous):
    if isinstance(value, dict) and isinstance(previous, dict):
        keys = [*previous, *(key for key in value if key not in previous)]
        return {key: _ordered(value[key], previous.get(key)) for key in keys if key in value}
    if isinstance(value, list) and isinstance(previous, list):
        return [_ordered(item, previous[index] if index < len(previous) else None)
                for index, item in enumerate(value)]
    return value


def _formatted(value, original_text):
    match = re.search(r'\n([ \t]+)"', original_text)
    indent = match.group(1) if match else ' '
    return json.dumps(value, indent=indent, ensure_ascii=False) + '\n'


async def regenerate(name, *, write=False):
    target = capsules.registered_capsule(name)
    if name not in capsules._STEMS:
        raise ValueError(target.adapter_blocker)
    import importlib
    # Stale fixture bindings are deliberately unavailable for execution, but
    # this explicit authoring command can revalidate them for the new release.
    execute = importlib.import_module(target.selected_worker_module).execute
    check = importlib.import_module(target.checks_module).check
    key = target.task_output_key
    stem = capsules._STEMS[name]
    manifest_path = capsules._EXTENSIONS / stem / 'fixtures/manifest.json'
    manifest_text = manifest_path.read_text('utf-8')
    manifest = json.loads(manifest_text)
    prepared, changes = [], []
    for group in capsules.FIXTURE_SETS:
        path = manifest_path.parent / manifest['sets'][group]
        original_text = path.read_text('utf-8')
        raw = json.loads(original_text)
        prior_changes = len(changes)
        for source, case in zip(raw['cases'], json.loads(capsules._fixture_set(stem, group))):
            before = copy.deepcopy(case['packet'])
            working = copy.deepcopy(before)
            output = json.loads((await execute(None, {target.input_name: working}))['result'].data)
            if capsules.encoded(working) != capsules.encoded(before):
                raise ValueError('Selected parent mutates its input: ' + case['id'])
            _, valid = capsules._checked(check, before, output, target.check_ids, input_name=target.input_name)
            if not valid:
                raise ValueError('Selected parent fails its checker: ' + case['id'])
            expected = copy.deepcopy(output)
            expected['data'][key] = case['expected_task_output']
            _, valid = capsules._checked(check, before, expected, target.check_ids, input_name=target.input_name)
            if not valid:
                source['expected_task_output'] = _ordered(output['data'][key], source['expected_task_output'])
                changes.append({'fixture_group': group, 'fixture_id': case['id']})
        if len(changes) != prior_changes:
            prepared.append((path, raw, original_text))
    # Finish every checker validation before modifying any authoring input.
    if write:
        for path, raw, original_text in prepared:
            path.write_text(_formatted(raw, original_text), encoding='utf-8')
        if manifest.get('release_module') != target.release_module:
            manifest['release_module'] = target.release_module
            manifest_path.write_text(_formatted(manifest, manifest_text), encoding='utf-8')
        capsules._manifest.cache_clear()
        capsules._raw_set.cache_clear()
        capsules._fixture_set.cache_clear()
    return {'capsule_name': name, 'version_label': target.version_label,
        'release_manifest_sha256': target.release_manifest_sha256,
        'declaration_sha256': target.declaration_sha256,
        'checks_sha256': target.checks_sha256, 'changes': changes, 'written': write}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capsule', required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(regenerate(args.capsule, write=args.write)), indent=2))


if __name__ == '__main__':
    main()
