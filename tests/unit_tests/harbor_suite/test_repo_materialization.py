"""Offline upload-asset packaging, without changing authored source or policies."""
import copy
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest

from benchmarks.harbor_suite import prepare as generator
from benchmarks.harbor_suite.contracts import load_cases, pin, resolve_cases_root, task_key
from jiuwenswarm.research.uploads import UploadManager


IMAGE = 'python:3.12-slim-bookworm@sha256:' + '1' * 64
CASE = 'pipeline01-experiment'
pytestmark = pytest.mark.usefixtures("benchmark_case_assets")


def test_single_file_zip_is_deterministic_safe_and_preserves_exact_bytes():
    raw = b'print("unchanged source")\r\n\x00\xff'
    member = 'public/reference_index.py'
    first = generator.single_file_repo_zip(member, raw)
    assert first == generator.single_file_repo_zip(member, raw)
    UploadManager._archive(first)
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert archive.namelist() == [member]
        entry = archive.getinfo(member)
        assert entry.date_time == (1980, 1, 1, 0, 0, 0)
        assert entry.create_system == 3
        assert entry.external_attr >> 16 == stat.S_IFREG | 0o644
        assert entry.compress_type == zipfile.ZIP_STORED
        assert archive.read(member) == raw


@pytest.mark.parametrize('path', ['public/existing.zip', 'public/existing.ZIP'])
def test_existing_archives_pass_through_without_repackaging(path):
    original = generator.single_file_repo_zip('public/existing.py', b'unchanged\n')
    item = {'path': path, 'kind': 'repo'}
    saved = copy.deepcopy(item)
    actual, raw = generator.materialize_input(item, original)
    assert item == saved == actual
    assert raw is original
    UploadManager._archive(raw)


def test_other_upload_kinds_keep_paths_and_bytes():
    for kind in ('docs', 'datasets'):
        item = dict(path='public/reference.py', kind=kind)
        assert generator.materialize_input(item, b'original') == (item, b'original')


@pytest.fixture(scope='module')
def bundle(tmp_path_factory):
    destination = tmp_path_factory.mktemp('repo-assets') / 'bundle'
    generator.prepare(destination, python_image=IMAGE, case_ids=(CASE,))
    return destination


def test_frozen_pins_runner_inventory_and_transform_bindings_agree(bundle):
    tasks = json.loads((bundle / 'task-index.json').read_bytes())['tasks']
    manifest = json.loads((bundle / 'bundle-manifest.json').read_bytes())
    files = {row['path']: row for row in manifest['files']}
    authored = next(case for case in load_cases() if case['id'] == CASE)
    case_root = resolve_cases_root() / CASE
    assert manifest['case_count'] == 1
    assert manifest['task_count'] == len(authored['variants'])
    for task in tasks:
        assert task['case'] == authored
        assert task['variant'] in authored['variants']
        variant = task['variant']
        runner_path = bundle / 'cases' / (task['task_key'] + '.json')
        assert pin(runner_path) == task['runner_case_pin']
        runner = json.loads(runner_path.read_bytes())['cases'][0]
        assert runner['task'] == variant['task']
        assert {row['path']: pin(bundle / 'inputs' / row['path']) for row in runner['inputs']} == task['public_inputs']
        assert task['input_transform']
        for row in task['input_transform']:
            assert row['schema'] == 'ai4r-single-file-repo-zip:1'
            source, asset = row['source'], row['archive']
            source_path = bundle / 'inputs' / source['path']
            asset_path = bundle / 'inputs' / asset['path']
            assert pin(source_path) == {key: source[key] for key in ('sha256', 'size')}
            assert source_path.read_bytes() == (case_root / row['member']).read_bytes()
            assert source['path'] not in task['public_inputs']
            assert task['public_inputs'][asset['path']] == pin(asset_path)
            assert pin(asset_path) == {key: asset[key] for key in ('sha256', 'size')}
            UploadManager._archive(asset_path.read_bytes())
            with zipfile.ZipFile(asset_path) as archive:
                assert archive.namelist() == [row['member']]
                assert archive.read(row['member']) == source_path.read_bytes()
            for description in (source, asset):
                frozen = files['inputs/' + description['path']]
                assert frozen['audience'] == 'visible'
                assert {key: frozen[key] for key in ('sha256', 'size')} == {key: description[key] for key in ('sha256', 'size')}
            matching = [row for row in runner['inputs'] if row['path'] == asset['path']]
            assert len(matching) == 1 and matching[0]['kind'] == 'repo'
            assert matching[0]['destination'] == row['member'] + '.zip'


def test_runner_case_optional_override_preserves_default_compatibility():
    case = next(case for case in load_cases() if case['id'] == CASE)
    variant = case['variants'][0]
    frozen = copy.deepcopy(variant)
    key = task_key(CASE, variant['id'], 1)
    default = generator.runner_case(key, case, variant)['cases'][0]['inputs']
    assert all(row['path'] == CASE + '/' + source['path'] and row['destination'] == source['path']
               for row, source in zip(default, variant['inputs']))
    adapted = [generator.materialize_input(item, b'fixture')[0] for item in variant['inputs']]
    actual = generator.runner_case(key, case, variant, inputs=adapted)['cases'][0]['inputs']
    assert all(row['path'] == CASE + '/' + source['path'] and row['destination'] == source['path']
               for row, source in zip(actual, adapted))
    assert variant == frozen


def test_default_authored_suite_counts_are_unchanged():
    cases = load_cases()
    assert len(cases) == 10
    assert sum(len(case['variants']) for case in cases) == 69
