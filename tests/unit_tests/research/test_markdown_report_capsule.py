from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsule_extensions.markdown_report.worker import render
from jiuwenswarm.research.capsule_extensions.markdown_report.checks import check
from jiuwenswarm.research.contracts import ResearchError


def packet():
    return {'schema_version': '1.0.0', 'data': {'answer': {'count': 2}, 'report': {'path': 'report.md',
        'title': 'Results', 'sections': [{'heading': 'Summary', 'text': 'Supplied claims only.'}], 'data_keys': ['answer']}},
        'files': [], 'trust': 'low', 'provenance': [], 'limitations': ['Not independently established']}


def test_report_is_exact_escaped_and_discloses_low_trust():
    source = packet()
    source['data']['report']['sections'][0]['text'] = '<script>bad</script> [click](http://example.com)'
    result = render(source)
    text = result['files'][-1]['text']
    assert 'Trust: low' in text and '&lt;script&gt;' in text and '\\[click\\]' in text
    assert 'Not independently established' in text and '"count": 2' in text
    assert result == render(source)
    ctx = SimpleNamespace(output_refs={})
    assert all(r['outcome'] == 'PASS' for r in check(ctx, {'packet': source}, {'result': result}))
    result['data']['report_manifest']['trust'] = 'provisional'
    assert check(ctx, {'packet': source}, {'result': result})[-1]['outcome'] == 'FAIL'


@pytest.mark.parametrize('path', ['../report.md', '/report.md', 'C:/report.md', 'a\\report.md'])
def test_report_never_writes_escaping_paths(path):
    source = packet()
    source['data']['report']['path'] = path
    with pytest.raises(ResearchError): render(source)


def test_report_refuses_overwriting_input_and_unknown_data():
    source = packet()
    existing = render(source)['files'][-1]
    source['files'] = [existing]
    with pytest.raises(ResearchError): render(source)
    source = packet()
    source['data']['report']['data_keys'] = ['missing']
    with pytest.raises(ResearchError): render(source)
