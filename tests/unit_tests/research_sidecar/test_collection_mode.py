"""Optional provenance archive transport, using real offline collection fixtures."""
import asyncio
import copy
import hashlib
import json

import httpx
import pytest

from benchmarks.harbor_suite import prepare as generator
from benchmarks.harbor_suite.contracts import load_cases, task_key
from jiuwenswarm.research_sidecar.archive_collection import encoded
from jiuwenswarm.research_sidecar.sequential import SequentialRunner, load_campaign, read_json
from jiuwenswarm.research_sidecar.sequential_cases import validate_cases
from tests.unit_tests.research_sidecar.test_archive_collection import ArchiveClient, fixture
from tests.unit_tests.research_sidecar.test_sequential import campaign, drive, InterfaceFixture


def document(**values):
    return {'schema_version': 'sequential-cases:1', 'cases': [dict(id='small', task='Collect originals', **values)]}


@pytest.mark.parametrize('mode', ['auto', 'archive'])
def test_collection_mode_is_validated_serialized_and_frozen(tmp_path, mode):
    normalized = validate_cases(document(collection_mode=mode))
    assert json.loads(json.dumps(normalized))['cases'][0]['collection_mode'] == mode
    folder, value = campaign(tmp_path, normalized['cases'])
    assert value['cases'][0]['collection_mode'] == mode
    assert load_campaign(folder)[1]['cases'][0]['collection_mode'] == mode


@pytest.mark.parametrize('mode', ['', None, True, 1, 'individual', 'ARCHIVE', [], {}])
def test_invalid_modes_cannot_enter_a_frozen_campaign(mode):
    with pytest.raises(ValueError, match='collection_mode'):
        validate_cases(document(collection_mode=mode))


def test_absent_mode_defaults_to_auto_and_old_frozen_cases_still_collect_individually(tmp_path):
    assert validate_cases(document())['cases'][0]['collection_mode'] == 'auto'
    folder, value = campaign(tmp_path, document()['cases'])
    value['cases'][0].pop('collection_mode')
    client = InterfaceFixture()
    assert drive(client, folder, value) == 0
    row = read_json(folder / 'runs/small-r1/run_record.json')
    assert row['collection_state'] == 'complete'
    assert all(item['source'] == 'app' for item in row['artifacts'])
    assert 'archive_collection' not in row


class SmallOriginalClient(ArchiveClient):
    def __init__(self, source, raw, *, lost=False):
        super().__init__(raw)
        self.source, self.confirmations, self.lost = source, [], lost

    async def events(self, run_id, after=0):
        return {'events': [], 'metrics': None, 'next_after': after}

    async def artifacts(self, run_id):
        assert run_id == self.source['run_id']
        return self.source

    async def stream_export_archive(self, run_id, destination, **kwargs):
        if self.lost:
            self.calls += 1
            destination.write_bytes(self.raw[:32])
            raise httpx.ReadTimeout('offline interrupted archive fixture')
        await super().stream_export_archive(run_id, destination, **kwargs)

    async def download_artifact(self, *args, **kwargs):
        raise AssertionError('explicit archive mode must use original archive transport')

    async def confirm_collection(self, run_id, manifest_sha256, artifacts):
        assert run_id == self.source['run_id']
        assert manifest_sha256 == self.source['manifest_sha256']
        assert artifacts == self.source['artifacts']
        self.confirmations.append(run_id)
        return {'status': 'confirmed'}


def collect_small(tmp_path, *, bad_hash=False, unsafe=False, lost=False, max_files=128):
    source, raw = fixture(bad_hash=bad_hash, unsafe=unsafe)
    source['execution_terminal'] = True
    source['manifest_sha256'] = hashlib.sha256(encoded({k: v for k, v in source.items() if k != 'manifest_sha256'})).hexdigest()
    client = SmallOriginalClient(source, raw, lost=lost)
    folder, value = campaign(tmp_path, [dict(id='small', task='Collect originals', collection_mode='archive',
                                           limits={'max_files': max_files})])
    runner = SequentialRunner(client, folder, value, progress=lambda _: None)
    case, row = next(runner.rows())
    row.update(app_run_id=source['run_id'], execution_state='completed')
    try:
        result = asyncio.run(runner.collect(case, row))
    finally:
        runner.close()
    return result, folder, row, client


def test_explicit_archive_collects_small_original_manifest_and_real_refs(tmp_path):
    result, folder, row, client = collect_small(tmp_path)
    assert result is True and row['collection_state'] == 'complete'
    assert len(client.source['artifacts']) == 2
    assert client.calls == 1 and client.confirmations == ['run:fixture']
    assert row['archive_collection']['verified_members'] == 2
    archive = folder / 'runs/small-r1/artifacts/originals.zip'
    assert archive.read_bytes() == client.raw
    inventory = read_json(archive.with_suffix('.inventory.json'))
    assert inventory['client_retrieval']['files'][1]['artifact_ref']['id'] == 'original:1'
    assert inventory['client_retrieval']['files'][1]['path'] == 'evidence/after.json'
    assert client.source['artifacts'][1]['path'] == 'evidence/before.json'
    assert {item['source'] for item in row['artifacts']} >= {'app_archive', 'app_archive_inventory'}


@pytest.mark.parametrize('options', [dict(bad_hash=True), dict(unsafe=True), dict(lost=True), dict(max_files=1)])
def test_archive_custody_download_and_file_budget_failures_never_confirm_collection(tmp_path, options):
    result, folder, row, client = collect_small(tmp_path, **options)
    assert result is False and row['collection_state'] == 'failed'
    assert row['execution_state'] == 'completed'
    assert client.confirmations == []
    assert read_json(folder / 'campaign_state.json')['state'] == 'paused'
    assert not (folder / 'runs/small-r1/artifacts/originals.zip').exists()
    assert not list((folder / 'runs/small-r1').rglob('.archive-transfer-*'))
    assert 'archive_collection' not in row


def test_suite_runner_declares_archive_without_changing_authored_case_or_task(benchmark_case_assets):
    case = next(case for case in load_cases() if case['id'] == 'pipeline01-experiment')
    original = copy.deepcopy(case)
    variant = case['variants'][0]
    value = generator.runner_case(task_key(case['id'], variant['id'], 1), case, variant)
    assert value['cases'][0]['collection_mode'] == 'archive'
    assert value['cases'][0]['task'] == variant['task']
    assert case == original
