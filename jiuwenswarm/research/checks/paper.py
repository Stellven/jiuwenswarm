"""Protected paper source/structure checks, independent from synthesis."""
from __future__ import annotations

import re

from ..contracts import ResearchError, validate
from ..run_inputs import local_document_refs
from ..capsules.paper_summary import SUMMARY, SECTIONS, documents
from ..capsules.paper_delivery import REPORT, MANIFEST, render, manifest

SUMMARY_CHECKS = ('summary_schema', 'paper_source_identity', 'paper_citation_spans', 'paper_section_coverage')
DELIVERY_CHECKS = ('research_report_schema', 'delivery_manifest_schema', 'paper_delivery_exact_links', 'paper_delivery_exact_render')


def require(value, detail):
    if not value:
        raise ResearchError('paper_check', detail)


def summary_checks(ctx, inputs, outputs):
    value = outputs['summary']
    validate(SUMMARY, value)
    refs = local_document_refs(ctx.store, ctx.input_ref('documents'),
        intake_ref=inputs['brief']['intake_ref'], run_id=ctx.contract['run_id'])
    require(value['brief_ref'] == ctx.input_ref('brief') and value['documents_ref'] == ctx.input_ref('documents'),
            'Summary changed its exact governing inputs')
    docs = documents(ctx.store, refs)
    require(value['documents'] == [{'document_id': doc['document_id'], 'source_ref': doc['source_ref'],
            'page_count': len(doc['pages'])} for doc in docs], 'Summary document identities/page counts differ from canonical sources')
    ids = [row['citation_id'] for row in value['citations']]
    require(len(ids) == len(set(ids)), 'Summary citation identities are ambiguous')
    for citation in value['citations']:
        doc = next((doc for doc in docs if doc['document_id'] == citation['document_id']), None)
        require(doc is not None, 'Citation source is outside qualified document buffer')
        page = next((page for page in doc['pages'] if page['page'] == citation['page']), None)
        require(page is not None, 'Citation page is outside canonical source')
        start = citation['start'] - page['start']
        end = citation['end'] - page['start']
        require(0 <= start < end <= len(page['text']) and page['text'][start:end] == citation['quote'],
                'Citation exact canonical source quote/span/page differs')
    used = set()
    for name in SECTIONS:
        section = value['sections'][name]
        require(not re.search(r'^\s*#', section['text'], re.MULTILINE), 'Section prose contains structural Markdown headings')
        require(set(section['citation_ids']) <= set(ids), 'Section cites an absent citation')
        if section['status'] == 'supported':
            require(bool(section['citation_ids']), 'Supported section has no original source citation')
        else:
            require(not section['citation_ids'] and bool(re.search(r'not (?:stated|reported|specified|provided|discussed)|未|没有|無', section['text'], re.I)),
                    'Unstated section requires explicit missing-information language and no invented support')
        used.update(section['citation_ids'])
    require(used == set(ids), 'Summary contains unused citations')


def delivery_checks(ctx, inputs, outputs):
    summary = inputs['summary']
    validate(SUMMARY, summary)
    report = outputs['research_report']
    if isinstance(report, str):
        report = report.encode('utf-8')
    require(type(report) is bytes, 'Paper report is not captured UTF-8 Markdown')
    validate(REPORT, report.decode('utf-8', errors='strict'))
    validate(MANIFEST, outputs['delivery_manifest'])
    require(ctx.store.is_accepted(ctx.input_ref('summary'), run_id=ctx.contract['run_id'])
            and ctx.store.is_accepted(ctx.input_ref('brief'), run_id=ctx.contract['run_id']),
            'Delivery requires current-run accepted summary and Brief')
    require(summary['brief_ref'] == ctx.input_ref('brief'), 'Accepted summary and delivery Brief differ')
    require(report == render(summary), 'Report changed accepted summary prose or source citations')
    gates = [row['gate_decision_ref'] for row in inputs['gate_decision_index']['entries']]
    require(bool(gates) and len(gates) == len({(ref['id'], ref['sha256']) for ref in gates}), 'Gate index is empty or ambiguous')
    expected = manifest(summary, ctx.input_ref('brief'), ctx.input_ref('summary'), ctx.output_refs['research_report'], gates)
    require(outputs['delivery_manifest'] == expected, 'Delivery manifest differs from exact accepted inputs/report/gate index')
    for row in expected['files']:
        ctx.read_blob(row['artifact_ref'])
    for ref in gates:
        gate = ctx.read_json(ref)
        validate('gate-decision', gate)
        require(gate['run_id'] == ctx.contract['run_id'] and gate['action'] == 'advance'
                and gate['verdict'] in {'PASS', 'PASS_WITH_KNOWN_LIMITATIONS'},
                'Delivery includes a non-advancing or foreign governing gate')


class PaperChecks:
    def __init__(self, stage):
        self.stage = stage

    def __call__(self, ctx, inputs, outputs):
        ids = SUMMARY_CHECKS if self.stage == 'paper_summary' else DELIVERY_CHECKS
        schemas = {'summary_schema': ('summary', SUMMARY)} if self.stage == 'paper_summary' else {
            'research_report_schema': ('research_report', REPORT),
            'delivery_manifest_schema': ('delivery_manifest', MANIFEST)}
        results = []
        for key, (port, schema) in schemas.items():
            try:
                value = outputs[port]
                if schema == REPORT and isinstance(value, bytes):
                    value = value.decode('utf-8', errors='strict')
                validate(schema, value)
                outcome, reason = 'PASS', 'Exact output conforms to its declared schema'
            except (ResearchError, ValueError, TypeError, KeyError, UnicodeError) as error:
                outcome, reason = 'FAIL', str(error)[:800] or type(error).__name__
            results.append({'check_id': key, 'outcome': outcome, 'reason': reason,
                            'evidence_refs': [ctx.output_refs[port]]})
        try:
            (summary_checks if self.stage == 'paper_summary' else delivery_checks)(ctx, inputs, outputs)
            outcome, reason = 'PASS', 'Exact declared structure, original source identities and citation/delivery links validated'
        except (ResearchError, ValueError, TypeError, KeyError, UnicodeError) as error:
            outcome, reason = 'FAIL', str(error)[:800] or type(error).__name__
        return [*results, *[{'check_id': key, 'outcome': outcome, 'reason': reason,
                 'evidence_refs': list(ctx.output_refs.values())} for key in ids if key not in schemas]]
