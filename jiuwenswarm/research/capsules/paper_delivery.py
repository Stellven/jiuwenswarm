"""Deterministically render the accepted paper summary and exact evidence links."""
from __future__ import annotations

from ..contracts import validate
from ._common import produced
from .paper_summary import SUMMARY, SECTIONS

REPORT = 'urn:ai4r:paper-report:1.0.0'
MANIFEST = 'urn:ai4r:paper-delivery-manifest:1.0.0'


def render(summary):
    citations = {row['citation_id']: row for row in summary['citations']}
    sections = []
    for name in SECTIONS:
        section = summary['sections'][name]
        lines = [section['text'].strip()]
        source_pages = sorted({(int(citations[key]['document_id'][1:]), citations[key]['page'])
                               for key in section['citation_ids']})
        if source_pages:
            lines.append('Sources: ' + ', '.join(f'[PDF {document}, p. {page}]'
                                               for document, page in source_pages))
        sections.append('## ' + name.title() + '\n\n' + '\n\n'.join(lines))
    return ('# ' + summary['title'].strip() + '\n\n' + '\n\n'.join(sections) + '\n').encode('utf-8')


def manifest(summary, brief_ref, summary_ref, report_ref, gates):
    sources = [row['source_ref'] for row in summary['documents']]
    files = [{'path': path, 'artifact_ref': ref, 'media_type': media, 'role': role, 'audience': 'researcher'}
        for path, ref, media, role in [
            ('paper_summary.md', report_ref, 'text/markdown', 'report'),
            ('research_brief.json', brief_ref, 'application/json', 'brief'),
            ('paper_summary.json', summary_ref, 'application/json', 'summary'),
            *[(f'sources/document_{i:03}.txt', ref, 'text/plain', 'source') for i, ref in enumerate(sources, 1)],
            *[(f'gates/gate_{i:03}.json', ref, 'application/json', 'gate_decision') for i, ref in enumerate(gates, 1)]]]
    return {'schema_version': '1.0.0', 'id': 'delivery_manifest', 'brief_ref': brief_ref,
        'summary_ref': summary_ref, 'report_ref': report_ref, 'source_refs': sources,
        'gate_decision_refs': gates, 'files': files, 'missing_evidence': []}


async def execute(ctx, inputs):
    summary = inputs['summary']
    validate(SUMMARY, summary)
    report = render(summary)
    report_ref = ctx.store.put_blob(report, media_type='text/markdown')
    gates = [row['gate_decision_ref'] for row in inputs['gate_decision_index']['entries']]
    value = manifest(summary, ctx.input_ref('brief'), ctx.input_ref('summary'), report_ref, gates)
    for row in value['files']:
        ctx.read_blob(row['artifact_ref'])
    return {'research_report': produced(report, REPORT, media_type='text/markdown', name='paper_summary.md'),
            'delivery_manifest': produced(value, MANIFEST, name='delivery_manifest.json')}
