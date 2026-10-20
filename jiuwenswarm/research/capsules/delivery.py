"""One faithful leaf Delivery; trusted retrieval remains a separate host seam."""
from ..contracts.types import ResearchError
from ._common import ask, produced


async def execute(ctx, inputs):
    reply = await ask(ctx, 'Delivery', 'Return {"research_report":"UTF8 Markdown", "delivery_manifest":{...}}. '
                      'The report has a #title and exactly9 ordered nonempty numbered H2 sections: '
                      '1.Objective;2.Opportunity and citations;3.Hypothesis and registered criteria;4.Method and POC;'
                      '5.Results: baseline vs treatment;6.Scientific verdict and reasoning;7.Limitations and risks;'
                      '8.Follow-up recommendations;9.Reproducibility. Preserve spaces after sectionnumbers. '
                      'Section3 has Metric|Unit|Aggregation|Success rule|Falsification rule|Otherwise table; '
                      'section5 has Metric|Unit|Baseline|Treatment|Delta table. Copy every metric/rule/value exactly; missing is null/unavailable. '
                      'Section6 has exact Classification:,Completeness:,Plausibility: lines plus one metric finding line. '
                      'Copy every verdict blocker,risk,completeness/plausibility note and opportunityrisk verbatim into7; '
                      'every saved followup appears in8 as - Recommendation:. No Recommendation: elsewhere. '
                      'Section9 has Item|Id|sha256 table for Research brief,Hypothesis blueprint,POC manifest,POC bundle,Environment lock,'
                      'Run configuration,Benchmark payload,Evaluation verdict and exactpins/seed/repeats. '
                      'delivery_manifest2.0.0 binds brief_ref,verdict_ref,report_ref,gate_decision_refs,artifact_refs,files,missing_evidence. '
                      'files have safe lowercase relative path,artifact_ref,media_type,role,audience researcher|reviewer. '
                      'Roles include report,brief,candidate_set,screening,opportunity,hypothesis,poc_manifest,poc_bundle,benchmark,verdict,'
                      'atleast1gate_decision,2raw_evidence,2environment. Use exactacceptedrefs only. Host derives report_ref afterwritingreport. '
                      'Scientific FAIL/INCONCLUSIVE still deliver unchanged. No publication or followup execution.',
                      dict({key: value for key, value in inputs.items() if key != 'run_configuration'},
                           input_refs={p: ctx.input_ref(p) for p in inputs}))
    report, manifest = reply.get('research_report'), reply.get('delivery_manifest')
    if not isinstance(report, str) or not isinstance(manifest, dict):
        raise ResearchError('invalid_output', 'Delivery requires a report and manifest pair')
    report_bytes = report.encode('utf-8')
    report_ref = ctx.store.put_blob(report_bytes, media_type='text/markdown')
    files = [f for f in manifest.get('files', []) if f.get('role') == 'report']
    if len(files) != 1:
        raise ResearchError('invalid_output', 'Delivery requires exactly one report file')
    manifest['report_ref'] = report_ref
    files[0]['artifact_ref'] = report_ref
    return {'research_report': produced(report_bytes, 'research-report', media_type='text/markdown', name=files[0]['path']),
            'delivery_manifest': produced(manifest, 'delivery-manifest')}
