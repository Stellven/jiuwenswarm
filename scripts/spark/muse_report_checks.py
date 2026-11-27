"""Render recorded roles and decisions without assigning verifier verdicts to capsule use."""
from html import escape
from functools import cache
import json
from pathlib import Path, PurePosixPath

from scripts.spark.build_muse_lab_reports import a, table

ATLAS = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/ccs/atlas-names.json'
FACTORY_EVIDENCE = 'reports/evidence/factory-verification.json'
NATIVE_REPORT_TABLES = {'records/observations.json', 'records/attempts.json', 'records/decisions.json'}

DEMO_TITLES = {
    'weights.build_muse_nvfp4_reader': 'Checkpoint converter',
    'weights.build_expert_scale_wiring': 'Expert scale wiring',
    'weights.build_weight_pack_compiler': 'Quantization',
    'engine.size_prefill_batch': 'Prefill plan',
    'engine.kv_reuse_lab': 'Prefix reuse',
    'engine.gpu_kernel_lab': 'Routed expert batching',
    'factory.source_workbench': 'Source integration workbench',
    'factory.capped_runner': 'Capped run workbench',
    'factory.builder': 'Image assembler',
    'factory.lab_manager': 'Lab manager',
    'factory.node_check': 'Node verifier',
}

LAB_CONTEXT = {
    'pack_2bit_census': 'Target lab · cites the factory pack check',
    'image_starts': 'Target lab · cites the model-free image receipt',
}


@cache
def report_labels():
    atlas = json.loads(ATLAS.read_text())['capsules']
    return {row['capsule_id']: row['title'] for row in atlas.values()} | DEMO_TITLES


def snapshot_activity(data, home, contract):
    from jiuwenswarm.factory.taskgraph import from_records
    from jiuwenswarm.gateway.channel_manager.web.factory_cc_activity import archive_cutoff, calls_as_of, project
    from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService
    from jiuwenswarm.gateway.channel_manager.web.factory_nodes import sealed_releases, worker_calls

    task = data['tasks'][0]
    task_id = task['task_id']
    graph = from_records(data)
    source = FactoryHttpService.run_id(home.resolve(), task_id)
    as_of = archive_cutoff(data)
    calls = calls_as_of(worker_calls(home / 'sessions' / f'{task_id}.jsonl'), as_of)
    nodes = project(dict(data, _contract=contract), graph, calls, sealed_releases(home / 'ccstore/releases'),
                    {'observations': 'records/observations.json', 'attempts': 'records/attempts.json'},
                    call_run_id=source)
    return dict(schema='factory.muse-cc-activity/1', task_id=task_id, task_created=task['created'],
                source_run_id=source, graph_rev=graph['rev'], as_of=as_of, nodes=nodes)


def check_name(name):
    return str(name).replace('_', ' ')


def node_check_label(values):
    output = check_name(values['output'])
    verifier = values.get('verifier') or {}
    if verifier.get('cc') and type(verifier.get('passed')) is bool:
        return f'CC verifier · {report_labels().get(verifier["cc"], verifier["cc"])} · {output}'
    return f'Node verifier · {output}'


def citation(label, record, *, stage=None, source=None):
    path = source or record.get('path')
    if not isinstance(path, str):
        path = None
    if path:
        candidate = PurePosixPath(path)
        if (candidate.is_absolute() or '..' in candidate.parts or '\\' in path
                or (stage and path not in NATIVE_REPORT_TABLES and not (stage / candidate).is_file())):
            path = None
    if not path:
        path = FACTORY_EVIDENCE if stage else None
    if not path:
        return escape(label)
    return (f'<a href="../{escape(path, quote=True)}" '
            f'title="{escape(str(record["id"]), quote=True)}">{escape(label)}</a>')


def latest_checks(records):
    """Retain the latest recorded check for each output, including later refusals."""
    by_output = {row.get('output') or row.get('capability') or row['id']: row
                 for row in sorted(records, key=lambda row: row['created'])}
    return sorted(by_output.values(), key=lambda row: not (row.get('status') == 'fail'))


def verifier_links(records, *, stage):
    labels = []
    for record in latest_checks(records):
        verdict = record['status'].capitalize()
        if record.get('output'):
            verdict = f'{verdict} · {check_name(record["output"])}'
        labels.append(citation(verdict, record, stage=stage))
    return '<br>'.join(labels)


def render_factory_checks(activity, *, stage=None):
    if not activity or not activity['nodes']:
        return ''
    if stage:
        # Keep only the canonical status projection. Raw worker transcripts can
        # include private material and never belong in the public report bundle.
        report_data = stage / FACTORY_EVIDENCE
        report_data.parent.mkdir(parents=True, exist_ok=True)
        report_data.write_text(json.dumps(activity, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    titles = report_labels()
    capsules = []
    checks = []
    for node_id, entry in activity['nodes'].items():
        node = '<code>' + escape(node_id) + '</code>'
        for capsule in entry.get('capsules', []):
            if not capsule.get('active', True):
                continue
            used = capsule.get('uses') or []
            use = citation('Used', used[-1], stage=stage) if used else 'Bound, not used'
            results = verifier_links(capsule.get('verifier_records') or [], stage=stage)
            if not results:
                results = ('No verifier declared' if capsule.get('verifier_declaration') == 'none'
                           else 'No CC verifier record')
            capsules.append((node, escape(titles.get(capsule['id'], capsule['id'])), use, results))
        closures = entry.get('closures', [])
        reopened = next((row['created'] for row in reversed(closures) if row['state'] == 'reopened'), None)
        node_verdict = verifier_links((row for row in entry.get('node_checks', [])
                                       if reopened is None or row['created'] >= reopened), stage=stage)
        if not node_verdict:
            closure = closures[-1] if closures and closures[-1].get('state') == 'done' else None
            if closure and closure.get('decision_id'):
                decision = citation(closure['decision_id'], closure, stage=stage, source='records/decisions.json')
                node_verdict = f'Closed by decision {decision}, no node check recorded'
            elif closure:
                update = citation('recorded graph update', closure, stage=stage)
                node_verdict = f'Closed by {update}, no node check recorded'
            else:
                node_verdict = 'No node check recorded'
        checks.append((node, node_verdict))
    body = '<h2>Factory verification and capsule use</h2>'
    if capsules:
        body += table(['Task node', 'Bound capsule', 'Use', 'CC verifier'], capsules,
                      'Use records a worker invocation. Bound, not used means no invocation is recorded. '
                      'No CC verifier record means no method or implementation verdict is recorded for that capsule.')
    return body + table(['Task node', 'Node verifier'], checks, 'Native node checks and recorded closures.')


def render_lab_checks(checks, unjudged=(), *, heading='Target lab checks', source=None, prior=False):
    rows = []
    for row in checks:
        name = row.get('check') or row['name']
        raw_verdict = (row.get('verdict') or row['status']).lower().replace('-', '_').replace(' ', '_')
        verdict = {'pass': 'Pass', 'fail': 'Fail', 'not_run': 'No lab verdict recorded',
                   'info': 'Recorded context'}.get(raw_verdict, check_name(raw_verdict).capitalize())
        role = LAB_CONTEXT.get(name, 'Target lab') if prior else 'Target lab'
        link = a(source(row), verdict) if source else escape(verdict)
        rows.append((escape(check_name(name)), escape(row.get('arm', '—')), escape(role), link,
                     escape(row.get('detail', ''))))
    for row in unjudged:
        verdict = 'No complete lab verdict recorded'
        rows.append((escape(check_name(row['test_id'])), '—', 'Target lab',
                     a(source(row), verdict) if source else verdict, escape(row['reason'])))
    return (f'<h2>{escape(heading)}</h2>' + table(['Check', 'Arm', 'Role', 'Verdict', 'Detail'], rows,
                                                'Recorded target evidence and its stated limits.')) if rows else ''
