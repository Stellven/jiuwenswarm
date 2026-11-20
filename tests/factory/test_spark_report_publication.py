"""Publication fixtures use native export and synthetic files; no agents/models run."""
import importlib.util
import json
from pathlib import Path

import pytest

import jiuwenswarm.factory.export as native
from jiuwenswarm.factory.store import Store

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('spark_publish_report', ROOT / 'ops/spark/publish_report.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


@pytest.fixture
def publication(tmp_path, monkeypatch):
    factory = tmp_path / 'factory-code'
    (factory / 'ccs').mkdir(parents=True)
    monkeypatch.setattr(native, 'ROOT', factory)
    base = tmp_path / 'evidence'
    base.mkdir()
    with Store(base / 'factory-runs/spark-direct-benchmarks') as store:
        task_id = 'spark-direct-benchmarks-20261120'
        store.create_task(dict(task_id=task_id, objective='Synthetic pre-existing benchmark task'))
        store.put_artifact(task_id, 'retained-benchmark-receipt', b'{"synthetic":true}', 'application/json', None)
        store.append_observation(task_id, dict(kind='synthetic_benchmark', source_artifacts=['retained-benchmark-receipt']))
    return base


def test_draft_exports_only_direct_citations_and_verifies_native_sanitized_addresses(publication):
    base = publication
    evidence = base / 'OPS' / 'data receipt.json'
    evidence.parent.mkdir()
    evidence.write_text(json.dumps({'contact': 'synthetic-person@example.com', 'value': 7}))
    report = base / 'report.md'
    report.write_text('# Synthetic report\n\n[Measured receipt](OPS/data%20receipt.json)\n'
                      '[Same receipt][source]\n\n[source]: <OPS/data receipt.json>\n')
    result = publisher.publish(report, base)
    out = Path(result['export'])
    assert result['status'] == 'draft'
    assert result['citation_count'] == 2
    assert result['verified_link_targets'] == 2
    assert 'DRAFT SNAPSHOT' in (out / 'report.md').read_text()
    mapping = json.loads((out / 'citation-map.json').read_text())
    assert len({row['artifact_id'] for row in mapping['direct_local_citations']}) == 1
    reference = mapping['direct_local_citations'][0]
    assert reference['sha256'] != reference['exported_sha256']
    assert reference['exported_path'] in (out / 'report.md').read_text()
    assert 'synthetic-person@example.com' not in (out / reference['exported_path']).read_text()
    assert native.verify(out) == result['verified_manifest_files']
    with Store(result['home']) as store:
        records = store.dump(result['task_id'])
        assert not records['attempts'] and not records['decisions']
        published = next(record for record in records['observations'] if record['kind'] == 'report_publication')
        assert published['values']['status'] == 'draft'
        source = store.artifact_bytes(result['task_id'], reference['artifact_id'])
        assert source == evidence.read_bytes()
    exported_observations = json.loads((out / 'records/observations.json').read_text())
    assert any(record['kind'] == 'synthetic_benchmark' for record in exported_observations)
    original_receipt = next(record for record in json.loads((out / 'artifacts.json').read_text())
                            if record['artifact_id'] == 'retained-benchmark-receipt')
    assert (out / original_receipt['exported_path']).read_bytes() == b'{"synthetic":true}'


def test_final_is_explicit_and_old_publications_are_not_overwritten(publication):
    report = publication / 'report.md'
    report.write_text('# Synthetic final report\n')
    out = publication / 'factory-runs' / 'exports' / 'reviewed-final'
    result = publisher.publish(report, publication, status='final', out=out)
    assert result['status'] == 'final'
    assert 'FINAL REPORT SNAPSHOT' in (out / 'report.md').read_text()
    with pytest.raises(ValueError, match='must be new'):
        publisher.publish(report, publication, status='final', out=out)


def test_missing_escape_and_credential_citations_fail_before_store_mutation(publication, tmp_path):
    report = publication / 'report.md'
    (tmp_path / 'outside.txt').write_text('outside')
    (publication / 'auth.json').write_text('{}')
    for target in ('missing.json', '../outside.txt', 'auth.json', 'https://example.com/evidence'):
        report.write_text(f'# Synthetic report\n[Evidence]({target})\n')
        with pytest.raises(ValueError):
            publisher.publish(report, publication)
        with Store(publication / 'factory-runs/spark-direct-benchmarks') as store:
            assert len(store.dump('spark-direct-benchmarks-20261120')['observations']) == 1


def test_code_fences_are_not_treated_as_evidence_citations():
    seen = []
    text = '```md\n[Example](not-evidence.json)\n```\n[Real](receipt.json)\n'
    mapped = publisher.map_links(text, lambda uri: seen.append(uri) or 'artifacts/test')
    assert seen == ['receipt.json']
    assert '[Example](not-evidence.json)' in mapped
