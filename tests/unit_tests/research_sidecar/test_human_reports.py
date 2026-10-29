import json

import pytest

from jiuwenswarm.research_sidecar.human_reports import build_human_reports


def campaign(tmp_path):
    (tmp_path / 'campaign.json').write_text(json.dumps({'campaign_id': 'sample'}))
    run = tmp_path / 'runs' / 'case-r1'
    run.mkdir(parents=True)
    (run / 'run_record.json').write_text(json.dumps({
        'run_id': 'case-r1', 'case_id': 'case', 'repeat_index': 1,
        'request_id': 'request-1', 'app_run_id': 'run:original',
        'task': 'Summarize the supplied document.', 'inputs': [],
        'execution_state': 'failed', 'collection_state': 'complete',
        'artifacts': [{'path': 'output.txt', 'sha256': 'a' * 64, 'size': 4}],
        'observations': {'model_usage': None}, 'errors': ['infrastructure failure']}))
    return tmp_path


def test_rebuild_retains_human_annotation_and_infrastructure_failure(tmp_path):
    root = campaign(tmp_path)
    build_human_reports(root)
    path = root / 'report.md'
    text = path.read_text(encoding='utf-8')
    marker = '<!-- review:case-r1:assessment -->\n'
    path.write_text(text.replace(marker, marker + 'Needs human inspection.\n'), encoding='utf-8')
    build_human_reports(root)
    assert 'Needs human inspection.' in path.read_text(encoding='utf-8')
    report = json.loads((root / 'report.json').read_bytes())
    assert report['assessment'] is None
    assert report['runs'][0]['execution_state'] == 'failed'
    assert report['reviews']['case-r1']['assessment'] == 'Needs human inspection.'
    assert 'Needs human inspection.' in (root / 'results.csv').read_text(encoding='utf-8-sig')


def test_existing_unowned_report_is_not_overwritten(tmp_path):
    root = campaign(tmp_path)
    path = root / 'report.md'
    original = b'My original human notes.\n'
    path.write_bytes(original)
    with pytest.raises(ValueError, match='not owned'):
        build_human_reports(root)
    assert path.read_bytes() == original
