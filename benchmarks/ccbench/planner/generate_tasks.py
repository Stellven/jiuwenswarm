"""Reproduce the fixed synthetic, planning-only research briefs and hidden labels."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from library import REPO, ref


def generate():
    base = json.loads((REPO / 'tests/fixtures/research/planning/lifecycle_research_brief.json').read_text())
    specifications = [
        ('paper', 'normal', 'Summarize the supplied qualified paper, preserving page citations, reported findings and limitations; deliver a Markdown report and evidence manifest.', ['research.paper_summary', 'research.paper_summary_delivery'], 'local_document_buffer', 'local_document_buffer'),
        ('screen', 'normal', 'Screen the supplied candidate set with the installed fixed rubric; return ranked screening results and the selected opportunity card. Do not conduct an experiment.', ['research.screening'], 'candidate_set', 'candidate_set'),
        ('normalize', 'normal', 'Normalize the supplied CSV packet file measurements.csv into ordered scalar rows without conversion or inference.', ['utility.table_normalize'], 'packet', 'work_packet'),
        ('calculate', 'normal', 'Calculate the mean of column accuracy in the supplied table packet using the explicit operation request; preserve the source table and report the numeric result.', ['utility.calculate'], 'packet', 'table_packet'),
        ('report', 'normal', 'Render the supplied explicit report sections and selected JSON data into an escaped Markdown report with a digest manifest; add no research claims.', ['utility.markdown_report'], 'packet', 'work_packet'),
        ('gpu_training', 'infeasible', 'Train a new 70-billion-parameter neural network on eight GPUs using distributed backpropagation and deliver measured held-out performance. GPU training is mandatory.', [], None, None),
        ('live_web', 'infeasible', 'Use a general-purpose live web search and browser to discover papers published today and retrieve arbitrary original publisher pages outside the pinned academic connectors. Live retrieval of those pages is mandatory; supplied documents and academic-connector-only results are not substitutes.', [], None, None),
        ('human_study', 'infeasible', 'Recruit 100 human participants, obtain consent and conduct a prospective randomized user study, delivering newly collected participant measurements.', [], None, None),
        ('budget_time', 'over_budget', 'Render the supplied report packet. Reserve at least 12000 seconds of aggregate node wall-time limits; this reservation is mandatory and may not be reduced. The planning policy permits at most 10800 aggregate seconds.', ['utility.markdown_report'], 'packet', 'work_packet'),
        ('budget_calls', 'over_budget', 'Render the supplied report packet. Reserve at least 100 aggregate model calls across the planned nodes; this reservation is mandatory and may not be reduced. The planning policy permits at most 80 aggregate model calls.', ['utility.markdown_report'], 'packet', 'work_packet'),
        ('missing_paper', 'underspecified', 'Summarize the paper I intended to upload, including exact page quotations and a report. No paper or extracted text has been supplied; do not invent its contents.', ['research.paper_summary', 'research.paper_summary_delivery'], None, None),
        ('missing_values', 'underspecified', 'Calculate the mean accuracy of my experiment. No measurement values or data packet have been supplied; do not invent observations.', ['utility.calculate'], None, None),
    ]
    tasks, expected = [], {}
    for tid, category, text, caps, key, kind in specifications:
        b = copy.deepcopy(base)
        b.update(schema_version='3.0.0', constraints=[], target_metrics=[], resource_refs=[], input_bindings=[], context_refs=[], assumptions=[], unresolved_items=[])
        b['objective'].update(id='objective:' + tid, text=text)
        b['in_scope'] = [dict(b['objective'], id='scope:' + tid)]
        b['mandatory_requirements'] = [dict(b['objective'], id='requirement:' + tid)]
        b['deliverables'] = [dict(id='deliverable:' + tid, name='result', description='The requested checked result and stated limitations', artifact_type='paper_report' if tid in ('paper', 'missing_paper') else 'work_packet')]
        b['acceptance_expectations'] = [dict(id='acceptance:' + tid, requirement_ids=['requirement:' + tid], description='Named output fields or installed check IDs demonstrate the requested outcome.')]
        b['evidence_obligations'] = [dict(id='evidence:' + tid, requirement_ids=['requirement:' + tid], description='Preserve supplied source provenance and expose the checked result without claiming new unperformed research.')]
        resources, external = [], {}
        content = None
        if key:
            content = {}
            if key == 'packet':
                csv_text = 'accuracy\n0.8\n0.9\n'
                content.update(schema_version='1.0.0', data={'table': {'columns': ['accuracy'], 'rows': [[0.8], [0.9]]},
                    'calculation': {'columns': ['accuracy'], 'operations': ['mean'], 'numeric_mode': 'json_numbers'},
                    'table_request': {'file': 'measurements.csv', 'format': 'csv', 'columns': ['accuracy'], 'delimiter': ','},
                    'report': {'path': 'report.md', 'title': 'Supplied measurements', 'sections': [{'heading': 'Results', 'text': 'Two supplied measurements.'}], 'data_keys': ['table']}},
                    files=[{'path': 'measurements.csv', 'text': csv_text, 'sha256': hashlib.sha256(csv_text.encode()).hexdigest()}], trust='provisional', provenance=[], limitations=[])
            elif key == 'local_document_buffer':
                source_text = 'A classifier achieved accuracy 0.85 on the reported test set. No external validation was performed.'
                content.update(schema='ai4r-local-document-buffer:1', id='buffer:paper', run_id='offline:paper', account_id='synthetic', workspace_id='synthetic', intake_ref=b['intake_ref'], source_refs=[ref(source_text, 'paper:canonical-text')])
            elif key == 'candidate_set':
                content.update(schema_version='2.0.0', id='candidate_set', brief_ref=ref(b, 'brief'), scope_ref=ref('supplied local candidates', 'scope'), queries=['supplied classifier candidate'],
                    connector_outcomes=[dict(connector='local_documents', status='used', reason='Supplied source', citations_captured=1)],
                    citations=[dict(id='citation:one', source_ref=ref('Classifier source', 'source'), connector='local_documents', query='supplied classifier candidate', title='Supplied classifier source', locator='page 1', char_start=0, char_end=17, excerpt='Classifier source', excerpt_sha256=hashlib.sha256(b'Classifier source').hexdigest())],
                    ideas=[dict(idea_id='idea:001', title='Linear classifier', summary='Use the supplied linear classifier baseline.', citation_ids=['citation:one'], assumptions=['Supplied data remains fixed'], risks=['Generalization is unmeasured'])])
            # artifact_type is the host-captured type of the supplied bytes; the product's _protected_run_inputs
            # and plan_checks read it from the inventory entry (schema ResourceItem.artifact_type).
            resources.append(dict(resource_key=key, kind='file', available=True, quantity=None, ref=ref(content, key), artifact_type=kind))
            external[key] = {'artifact_type': kind, 'content': content}
            if key == 'local_document_buffer':
                external[key]['source_texts'] = [{'ref': content['source_refs'][0], 'text': source_text}]
        if tid == 'screen':
            resources.append(dict(resource_key='original_request', kind='file', available=True, quantity=None, ref=ref(text, 'original_request'), artifact_type='text'))
            external['original_request'] = {'artifact_type': 'text', 'content': text}
        task = dict(id=tid, brief=b, resource_inventory=dict(schema_version='1.0.0', id='inventory.' + tid, resources=resources), supplied_inputs=external)
        tasks.append(task)
        obligations = [v['id'] for f in ('mandatory_requirements', 'deliverables', 'evidence_obligations') for v in b[f]]
        missing = {'gpu_training': 'distributed GPU training', 'live_web': 'live public web retrieval', 'human_study': 'human participant recruitment and experimentation',
                   'missing_paper': 'qualified original paper input', 'missing_values': 'measurement values input', 'budget_time': 'time_s policy aggregate ceiling', 'budget_calls': 'model_calls policy aggregate ceiling'}
        expected[tid] = dict(feasible=category == 'normal', category=category, required_capabilities=caps,
            required_inputs=[key] if key else (['local_document_buffer'] if tid == 'missing_paper' else ['packet'] if tid == 'missing_values' else []),
            obligations=obligations, missing_capability_or_input=missing.get(tid),
            reason_terms={'gpu_training': ['gpu', 'train'], 'live_web': ['web', 'retriev', 'live'], 'human_study': ['human', 'participant', 'recruit'],
                          'missing_paper': ['paper', 'document', 'input'], 'missing_values': ['measurement', 'values', 'input', 'packet'],
                          'budget_time': ['time', '12000', 'budget'], 'budget_calls': ['call', '100', 'budget']}.get(tid, []),
            minimum_limits={'time_s': 12000} if tid == 'budget_time' else {'model_calls': 100} if tid == 'budget_calls' else {})
    return tasks, expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='directory for tasks.json and expected.json')
    out = parser.parse_args(argv).out
    out.mkdir(parents=True, exist_ok=True)
    tasks, expected = generate()
    for name, value in [('tasks.json', tasks), ('expected.json', expected)]:
        (out / name).write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()

