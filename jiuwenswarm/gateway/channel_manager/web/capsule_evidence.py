"""Project capsule evidence from the same run sources as the web replay."""

from collections import defaultdict
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median

from jiuwenswarm.factory.redact import sanitize


# The campaign numbers single-capsule arms by their registered work orders.
STAR_ARMS = {
    'observability.build_runtime_event_recorder': 'C1',
    'engine.build_expert_weight_cache': 'C2',
    'placement.build_weight_placement_planner': 'C3',
    'routing.build_expert_demand_predictor': 'C4',
    'engine.build_batch_layout_mapper': 'C5',
}
BASELINES = {'A', 'A+', 'S'}
VERIFY_OBSERVATIONS = {'verifier_receipt_preserved', 'verify_receipt', 'capsule_verify'}
ANALYSIS_OBSERVATIONS = {'analysis', 'profile_result', 'phase_breakdown', 'gap_attribution', 'analysis_result',
                         'hypothesis_proposal', 'unmeasured_ablation_design', 'deep_profile_analyze'}
ANALYSIS_PRODUCERS = {
    'deep_profile_analyze': 'factory.deep_profile',
    'hypothesis_proposal': 'factory.methodology_hypothesis',
    'unmeasured_ablation_design': 'factory.methodology_ablation',
}


def _records(value):
    return (row for row in value if isinstance(row, dict)) if isinstance(value, list) else ()


def _object(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    if (type(value) is int and abs(value) < 2**53) or (type(value) is float and math.isfinite(value)):
        return value
    return None


def _strings(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _capsules(row):
    identities = [row.get(key) for key in ('component_cc', 'capability_cc', 'capsule_id', 'capsule', 'cc')]
    identities.extend(_strings(row.get('capsules')))
    return [value for identity in identities if isinstance(value := _object(identity).get('id', identity), str)]



def _member_ids(value):
    return [identity for row in value if isinstance(identity := _object(row).get('id', row), str)] if isinstance(value, list) else []


def _iteration(values):
    return values if values.get('schema') == 'spark-factory-iteration/1' else {}


def capsule_usage(service, capsule_ids):
    """Count unique native tasks and flag capsules with analysis recorded today (UTC)."""
    task_ids = defaultdict(set)
    latest_analyses = {}
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    for run, root in service.catalog():
        try:
            data = service.load(run, root)
        except (OSError, ValueError, KeyError):
            continue
        task_id = run['task_id']
        used = {cc for task in _records(data.get('tasks')) if task.get('task_id') == task_id for cc in _capsules(task)}
        for decision in _records(data.get('decisions')):
            action = _object(decision.get('action'))
            used.update(_capsules(action))
            capability = action.get('capability')
            if isinstance(capability, str):
                used.add(capability)
                used.add(capability.rsplit('.', 1)[0])
        for record in _records(data.get('observations')):
            if record.get('task_id', task_id) != task_id:
                continue
            kind, values = record.get('kind'), _object(record.get('values'))
            iteration = _iteration(values)
            identity = set(_capsules(record) + _capsules(values))
            producers = set(_member_ids(_object(iteration.get('analysis')).get('ccs')))
            used.update(identity | producers | set(_member_ids(_object(iteration.get('plan')).get('builder_ccs'))))
            if isinstance(kind, str) and kind in ANALYSIS_PRODUCERS:
                producers.add(ANALYSIS_PRODUCERS[kind])
                used.update(producers)
            if (not isinstance(kind, str) or not values or values.get('analysis_obs_id')
                    or not (kind in ANALYSIS_OBSERVATIONS or kind.startswith(('analysis.', 'analysis_', 'profile_analysis')))):
                identity = set()
            created = _number(record.get('created'))
            if created is not None and today <= created <= now.timestamp():
                for capsule_id in (identity | producers) & capsule_ids:
                    latest_analyses[capsule_id] = max(created, latest_analyses.get(capsule_id, 0))
        for capsule_id in used & capsule_ids:
            task_ids[capsule_id].add(task_id)
    return {cc: dict(used_in_runs=len(task_ids[cc]), featured_analysis_at=latest_analyses.get(cc)) for cc in capsule_ids}


def _build_rollup(record, artifacts):
    values = _object(record.get('values'))
    executable = _object(values.get('executable'))
    digest = values.get('executable_sha256') or executable.get('sha256')
    if values.get('status') not in ('success', 'succeeded') or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        return None
    refs = _strings(record.get('source_artifacts'))
    artifact = next((artifacts[aid] for aid in refs if aid in artifacts and artifacts[aid]['kind'] == 'build_record'), None)
    return dict(binary_sha256=digest, artifact=artifact, created=_number(record.get('created')))


def _lab_rollup(record, artifacts):
    values = _object(record.get('values'))
    if record.get('kind') != 'functional_lab':
        return None
    arms = list(_records(values.get('arms')))
    parity = []
    for row in arms:
        checks = _object(row.get('stock_match'))
        if isinstance(row.get('parity'), bool):
            parity.append(row['parity'])
        elif checks and all(isinstance(flag, bool) for flag in checks.values()):
            parity.append(all(checks.values()))
    summary = _object(values.get('session_summary'))
    activation = values.get('activation')
    if not isinstance(activation, bool):
        written = _number(summary.get('written'))
        activation = written > 0 if values.get('schema') == 'spark-functional-lab/1' and written is not None else None
    metrics = dict(_object(values.get('metrics')))
    for key in ('written', 'lost', 'bytes_transferred'):
        if (value := _number(summary.get(key))) is not None:
            metrics[key] = value
    peak = next((_number(arm.get('peak_memory_bytes')) for arm in arms if '-on-' in str(arm.get('arm'))), None)
    if peak is not None:
        metrics['peak_memory_bytes'] = peak
    refs = _strings(record.get('source_artifacts'))
    artifact = next((artifacts[aid] for aid in refs if aid in artifacts and artifacts[aid]['kind'] == 'lab'), None)
    overall_parity = False if False in parity else True if parity and len(parity) == len(arms) else None
    if isinstance(values.get('parity'), bool):
        overall_parity = values['parity']
    return dict(binary_sha256=values.get('binary_sha256'), parity=overall_parity, activation=activation,
                metrics={key: value for key, value in metrics.items() if _number(value) is not None},
                scope=values.get('scope') if isinstance(values.get('scope'), str) else record.get('limitations'),
                limitations=record.get('limitations'), artifact=artifact,
                created=_number(record.get('created')))

def _capsule_version(task, capsule_id):
    """Version of the capsule a run was given, from ``resources.capsules`` (``id@version``)."""
    for reference in _strings(_object(task.get('resources')).get('capsules')):
        name, _, version = reference.partition('@')
        if name == capsule_id and version:
            return version
    return None


def _builder_entry(iteration, capsule_id):
    return next((row for row in _records(_object(iteration.get('plan')).get('builder_ccs'))
                 if row.get('id') == capsule_id), {})


def _iteration_lab(iteration, capsule_id, read_json, created):
    """Lab rollup for a builder from a published quiet comparison in a factory iteration.

    Parity compares the candidate arm's greedy output digests with the control arm's for each prompt
    size; activation reads the candidate's retained profile-activation marker. Both are recomputed
    from the iteration's own verified artifacts.
    """
    analysis = _object(iteration.get('analysis'))
    comparison = _object(analysis.get('focused_comparison'))
    profiles = _object(comparison.get('profiles'))
    arms = [arm for arm in profiles if arm not in BASELINES]
    controls = [arm for arm in profiles if arm in BASELINES]
    lab_ids = _strings(_object(iteration.get('lab')).get('result_artifact_ids'))
    if len(arms) != 1 or len(controls) != 1 or not lab_ids:
        return None
    arm, control = arms[0], controls[0]
    result = _object(analysis.get('result_artifact'))
    parsed, artifact = read_json(result.get('artifact_id'), result.get('sha256'))
    parity = None
    if isinstance(parsed, dict):
        outputs = defaultdict(lambda: defaultdict(set))
        for row in _records(parsed.get('eligible')):
            if isinstance(row.get('output_sha256'), str):
                outputs[row.get('prompt_tokens')][row.get('arm')].add(row['output_sha256'])
        sizes = [by_arm for by_arm in outputs.values() if by_arm.get(arm) and by_arm.get(control)]
        if sizes:
            parity = all(by_arm[arm] == by_arm[control] for by_arm in sizes)
    activation = None
    for reference in lab_ids:
        aid, _, digest = reference.partition('@')
        if aid.endswith('/profile-activation.json') and f'-{arm.lower()}-' in aid:
            marker, _ = read_json(reference, digest)
            text = str(_object(marker).get('marker', ''))
            if text:
                activation = bool(activation) or ': active ' in text + ' '
    metrics = {}
    for row in _records(comparison.get('rows')):
        saved = _number(_object(row.get('paired_ttft_seconds_saved_vs_' + control.replace('+', 'plus'))).get('estimate'))
        size = _number(row.get('prompt_tokens'))
        if saved is not None and size is not None:
            metrics[f'paired_ttft_saved_s_{size}'] = round(saved, 2)
    entry = _builder_entry(iteration, capsule_id)
    scope = f"{iteration.get('iteration_id')}: {arm} vs {control}"
    if isinstance(parsed, dict) and isinstance(parsed.get('mode'), str):
        scope += f" ({parsed['mode']})"
    return dict(binary_sha256=_object(profiles[arm]).get('binary_sha256'), parity=parity, activation=activation,
                metrics=metrics, scope=scope, limitations=None, artifact=artifact, created=created,
                version=entry.get('version'), release=entry.get('release'))


def _artifact_kind(row, verifier_refs, product_refs):
    aid = row['artifact_id']
    if aid in verifier_refs or re.search(r'verif(?:y|ier|ication)[-_]receipts?(?:\.json)?$', aid):
        return 'verify_receipt'
    if aid.endswith(':build-record'):
        return 'build_record'
    if aid.endswith((':receipt', '-receipt.json')):
        return 'receipt'
    if row.get('media_type') in ('text/x-diff', 'text/x-patch') or aid.endswith(('.diff', '.patch')):
        return 'diff'
    return 'product' if aid in product_refs else None


def _receipt_row(receipt, source, capsule_id, release, inferred=False):
    row = _object(receipt)
    if row.get('capability') != 'verify' or not isinstance(row.get('call'), str):
        return None
    if not (inferred or capsule_id in _capsules(row) or (release and row.get('release') == release)):
        return None
    outputs = _object(row.get('outputs'))
    verification = _object(outputs.get('verification'))
    created = _number(_object(row.get('provenance')).get('finished'))
    checks = [{key: v for key in ('name', 'stage', 'status', 'detail') if isinstance(v := check.get(key), str)}
              for check in _records(outputs.get('checks'))]
    return source | {key: row.get(key) if isinstance(row.get(key), str) else None
                     for key in ('call', 'release', 'state', 'completeness', 'reason')} | dict(
                         created=created if created is not None else source['created'],
                         done=next((value for value in (outputs.get('done'), outputs.get('verified'), verification.get('done'))
                                    if isinstance(value, bool)), None),
                         checks=checks)


def _transcript_receipts(target, capsule_id, release):
    requests = {}
    with target.open('rb') as stream:
        for line in stream:
            if b'cc_call' not in line:
                continue
            try:
                event = _object(json.loads(line))
                tool = _object(event.get('tool_call'))
                if str(tool.get('name', '')).endswith('cc_call'):
                    args = tool.get('arguments')
                    args = _object(json.loads(args) if isinstance(args, str) else args)
                    if args.get('cc') == capsule_id and isinstance(tool.get('tool_call_id'), str):
                        requests[tool['tool_call_id']] = args.get('capability')
                if event.get('event_type') != 'chat.tool_result' or not str(event.get('tool_name', '')).endswith('cc_call'):
                    continue
                payload = event.get('result')
                result = _object(_object(json.loads(payload) if isinstance(payload, str) else payload).get('result'))
                requested = requests.pop(event.get('tool_call_id'), None)
                payloads = [result.get('structuredContent')]
                for child in _records(result.get('content')):
                    try:
                        payloads.append(json.loads(child.get('text', '{}')))
                    except (TypeError, ValueError):
                        continue
                for receipt in map(_object, payloads):
                    inferred = isinstance(requested, str) and receipt.get('capability') == requested
                    if isinstance(receipt.get('call'), str) and (inferred or capsule_id in _capsules(receipt)
                            or (release and receipt.get('release') == release)):
                        yield receipt, _number(event.get('t'))
            except (TypeError, ValueError):
                continue


def _analysis_row(record, source, call=None):
    history = _object(_object(record.get('values')).get('receipt_history'))
    receipt_key = {'hypothesis_proposal': 'proposal_call', 'unmeasured_ablation_design': 'ablation_call'}.get(record['kind'])
    return source | dict(observation_id=record.get('obs_id'), call=call or history.get(receipt_key), kind=record['kind'],
                         created=_number(record.get('created')), limitations=record.get('limitations'),
                         artifact_ids=_strings(record.get('source_artifacts')), values=record['values'])


def _analysis_call(receipt, source, analysis):
    outputs = _object(receipt.get('outputs'))
    values = _object(outputs.get('analysis'))
    if analysis and not values:
        values = {key: value for key in ('report', 'profile', 'phase_breakdown', 'gap_attribution', 'proposal')
                  if (value := outputs.get(key)) is not None}
    capability = receipt.get('capability')
    if not values or capability in ('plan', 'profile_plan') or not isinstance(capability, str):
        return None
    evidence = _object(outputs.get('evidence'))
    record = dict(evidence, kind=evidence.get('kind', capability), values=values,
                  obs_id=evidence.get('obs_id') or outputs.get('observation_id'),
                  created=_number(_object(receipt.get('provenance')).get('finished')) or source['created'])
    return _analysis_row(record, source, receipt['call'])


def _measurements(task, observations, capsule_id, task_owns_capsule, starred, source):
    groups = defaultdict(list)
    star_contract = task.get('contract_id') == 'star-deepseek-v1'
    for observation in observations:
        values = _object(observation.get('values'))
        arm, prompt, ttft = values.get('arm'), _number(values.get('prompt_tokens')), _number(values.get('ttft_s'))
        if (observation.get('kind') != 'measurement' or values.get('measurement_eligible') is not True
                or values.get('warm') is False or values.get('discarded') or values.get('discard')
                or values.get('ok') is False or not isinstance(arm, str) or type(prompt) is not int or prompt <= 0
                or ttft is None or ttft <= 0):
            continue
        explicitly_attributed = _capsules(values)
        if arm not in BASELINES:
            attributed = task_owns_capsule
            if star_contract and (arm == 'D' or arm in STAR_ARMS.values()):
                attributed = starred and arm in (STAR_ARMS.get(capsule_id), 'D')
            if explicitly_attributed:
                attributed = capsule_id in explicitly_attributed
            if not attributed:
                continue
        # Keep deltas inside matching campaign inputs and avoid mixing binaries
        # within an arm. Baseline comparisons require an unambiguous group.
        inputs = tuple(str(values.get(key, '')) for key in ('contract_sha256', 'prompt_manifest_sha256', 'prompt_sha256'))
        binary = str(values.get('binary_sha256', ''))
        groups[(prompt, inputs, arm, binary)].append((observation, values))

    controls = defaultdict(list)
    for (prompt, inputs, arm, _), rows in groups.items():
        if arm in BASELINES:
            controls[(prompt, inputs, arm)].append(median(values['ttft_s'] for _, values in rows))

    for (prompt, inputs, arm, binary), rows in sorted(groups.items()):
        if arm in BASELINES:
            continue
        ttft = median(values['ttft_s'] for _, values in rows)
        matched = [controls[(prompt, inputs, baseline)] for baseline in ('A', 'A+', 'S')]
        stock, cache, strata = (values[0] if len(values) == 1 else None for values in matched)
        stats = {key: summarize(sample) if (sample := [v for _, values in rows
                                                      if (v := _number(values.get(key))) is not None]) else None
                 for key, summarize in (('decode_tps', median), ('peak_memory_bytes', max), ('load_time_s', median))}
        yield source | stats | dict(
            arm=arm, scope='combined' if arm == 'D' else 'capsule', prompt_tokens=prompt, samples=len(rows), ttft_s=ttft,
            binary_sha256=binary or None, delta_vs_stock_s=ttft - stock if stock else None,
            inverse_vs_stock=stock / ttft if stock else None, inverse_vs_cache=cache / ttft if cache else None,
            gap_closed=(stock - ttft) / (stock - strata) if stock and strata and stock > strata else None,
            observation_ids=[r['obs_id'] for r, _ in rows if isinstance(r.get('obs_id'), str)],
            limitations=list(dict.fromkeys(r['limitations'] for r, _ in rows if isinstance(r.get('limitations'), str) and r['limitations'])),
        )


def collect_capsule_evidence(service, capsule_id, *, release=None, starred=False, analysis=False):
    """Read native run sources, preserving replay links and integrity state."""
    from .factory_http import MAX_FILE, _inside, _json

    related_runs, artifacts, measurements, receipts, analyses, builder_summaries = [], [], [], [], [], []
    seen_artifacts, seen_measurements, seen_analyses = set(), set(), set()
    catalog = sorted(service.catalog(), key=lambda entry: (entry[0]['kind'] != 'live', -entry[0]['updated']))
    for run, root in catalog:
        try:
            data = service.load(run, root)
            task_id = run['task_id']
            task = next(t for t in _records(data.get('tasks')) if t.get('task_id') == task_id)
            bundle = run['kind'] == 'bundle'
            exported = _inside(root, 'artifacts.json') if bundle else None
            inventory = _json(exported) if bundle and exported.is_file() else data.get('artifacts')
            manifest = service.expected(run, root, data) if bundle else {}
        except (OSError, ValueError, KeyError, StopIteration):
            continue

        source = dict(run_id=run['id'], run_name=run['name'])
        owns_capsule = (task.get('component_cc') or task.get('capability_cc')) == capsule_id
        observations = [row for row in _records(data.get('observations')) if row.get('task_id', task_id) == task_id]
        relevant = [r for r in observations if capsule_id in _capsules(_object(r.get('values'))) or
                    (owns_capsule and not _capsules(_object(r.get('values'))))]
        run_analyses = []
        analysis_reports = defaultdict(list)
        iteration_outputs = set()
        iteration_reports = {}
        builder_reports = []
        built_iterations = []
        lab_refs = set()
        consumes_analysis = False
        for record in observations:
            kind, values = record.get('kind'), _object(record.get('values'))
            if not isinstance(kind, str) or not values:
                continue
            if iteration := _iteration(values):
                results = _object(iteration.get('analysis'))
                plan = _object(iteration.get('plan'))
                contributed_analysis = capsule_id in _member_ids(results.get('ccs'))
                contributed_build = capsule_id in _member_ids(plan.get('builder_ccs'))
                if contributed_analysis:
                    iteration_outputs.update(_strings(results.get('output_artifact_ids')))
                if contributed_analysis or contributed_build:
                    report = _object(iteration.get('report'))
                    if isinstance(report.get('artifact_id'), str) and isinstance(report.get('sha256'), str):
                        iteration_reports[report['artifact_id']] = report['sha256']
                        if contributed_build:
                            entry = _builder_entry(iteration, capsule_id)
                            builder_reports.append(dict(report, created=_number(record.get('created')),
                                                        version=entry.get('version'), release=entry.get('release')))
                if contributed_build and not analysis:
                    built_iterations.append((iteration, _number(record.get('created'))))
            if kind == 'functional_lab' and record in relevant:
                lab_refs.update(aid for aid in _strings(record.get('source_artifacts')) if aid.rsplit('/', 1)[-1] == 'lab.json')
            explicit = capsule_id in _capsules(record) or capsule_id in _capsules(values)
            named = kind in ANALYSIS_OBSERVATIONS or kind.startswith(('analysis.', 'analysis_', 'profile_analysis'))
            structured = any(key in values for key in ('analysis', 'phase_breakdown', 'gap_attribution'))
            producer = ANALYSIS_PRODUCERS.get(kind)
            associated = explicit or (producer == capsule_id if producer else analysis and owns_capsule)
            if explicit and values.get('analysis_obs_id') and not structured and 'rows' not in values:
                consumes_analysis = True
                continue
            if associated and (named or structured or analysis and explicit):
                row = _analysis_row(record, source | dict(path=None, integrity=None))
                run_analyses.append(row)
                report_sha = values.get('report_sha256')
                if isinstance(report_sha, str):
                    for artifact_id in row['artifact_ids']:
                        analysis_reports[(artifact_id, report_sha)].append(row)
        verifier_refs = {ref: r for r in relevant if r.get('kind') in VERIFY_OBSERVATIONS
                         for ref in _strings(r.get('source_artifacts'))}
        product_refs = {ref for r in relevant if r.get('kind') == 'capsule_product' for ref in _strings(r.get('source_artifacts'))}
        run_artifacts, run_receipts = [], []
        artifact_index = {}
        for entry in _records(inventory):
            aid = entry.get('artifact_id')
            if (entry.get('task_id', task_id) != task_id or not isinstance(aid, str)
                    or re.match(r'input-\d+:', aid) or entry.get('complete') is False):
                continue
            report_sha = entry.get('sha256')
            report_refs = analysis_reports.get((aid, report_sha), ()) if isinstance(report_sha, str) else ()
            published_report = aid in iteration_reports and iteration_reports[aid] == report_sha
            if not (owns_capsule or aid in verifier_refs or aid in product_refs or report_refs
                    or aid in iteration_outputs or aid in lab_refs or published_report):
                continue
            kind = _artifact_kind(entry, verifier_refs, product_refs)
            if published_report:
                kind = 'report'
            elif aid in lab_refs:
                kind = 'lab'
            elif report_refs or (aid in iteration_outputs and not kind):
                kind = 'analysis_report'
            if not kind:
                continue
            relative = entry.get('exported_path' if bundle else 'location')
            if (not isinstance(relative, str) or not Path(relative).parts or Path(relative).parts[0] != 'artifacts'):
                continue
            try:
                target = _inside(root, relative)
                expected = manifest.get(relative) if bundle else entry.get('sha256')
                can_read_receipt = kind == 'verify_receipt' and target.is_file() and target.stat().st_size <= MAX_FILE
                blob = target.read_bytes() if can_read_receipt else None
                digest = (hashlib.sha256(blob).hexdigest() if blob is not None else service.file_hash(target)) if target.is_file() else None
            except (OSError, ValueError):
                continue
            integrity = 'missing' if not digest else ('verified' if digest == expected else 'mismatch') if expected else 'untracked'
            artifact = source | dict(path=relative, artifact_id=aid, kind=kind, integrity=integrity, sha256=digest,
                                     media_type=entry.get('media_type'), created=_number(entry.get('created')))
            artifact_index[aid] = artifact
            for analysis_row in report_refs:
                analysis_row.update(path=relative, integrity=integrity, report_artifact_id=aid)
            key = (task_id, aid, entry.get('sha256'), integrity)
            if key not in seen_artifacts:
                run_artifacts.append(artifact)
                seen_artifacts.add(key)
            if blob is None or integrity != 'verified':
                continue
            try:
                saved = json.loads(blob)
            except (ValueError, UnicodeDecodeError):
                continue
            saved = saved if isinstance(saved, list) else [saved]
            receipt_source = artifact | {'limitations': verifier_refs.get(aid, {}).get('limitations')}
            for receipt in saved:
                if row := _receipt_row(receipt, receipt_source, capsule_id, release, aid in verifier_refs or aid in iteration_outputs):
                    run_receipts.append(row)

        session = 'session.jsonl' if bundle else f'sessions/{task_id}.jsonl'
        try:
            target = _inside(root, session)
            if target.is_file() and target.stat().st_size <= MAX_FILE:
                wanted = manifest.get(session)
                integrity = 'verified' if wanted and service.file_hash(target) == wanted else 'untracked'
                if not wanted or integrity == 'verified':
                    session_source = source | dict(path=session, artifact_id=None, integrity=integrity, created=None)
                    for receipt, created in _transcript_receipts(target, capsule_id, release):
                        call_source = session_source | {'created': created}
                        if row := _receipt_row(receipt, call_source, capsule_id, release, inferred=True):
                            run_receipts.append(row)
                        if row := _analysis_call(receipt, call_source, analysis):
                            run_analyses.append(row)
        except (OSError, ValueError):
            pass

        run_measurements = []
        for row in _measurements(task, observations, capsule_id, owns_capsule, starred, source):
            key = (task_id, row['arm'], row['prompt_tokens'], tuple(sorted(row['observation_ids'])))
            if key not in seen_measurements:
                run_measurements.append(row)
                seen_measurements.add(key)
        if not analysis and (owns_capsule or builder_reports):
            run_version = _capsule_version(task, capsule_id)
            builds = [item | dict(version=run_version) for row in relevant if row.get('kind') == 'build_result'
                      if (item := _build_rollup(row, artifact_index))]
            labs = [item | dict(version=run_version) for row in relevant if (item := _lab_rollup(row, artifact_index))]
            entries = {entry.get('artifact_id'): entry for entry in _records(inventory)
                       if entry.get('task_id', task_id) == task_id and isinstance(entry.get('artifact_id'), str)}

            def read_json(reference, digest):
                aid = reference.split('@', 1)[0] if isinstance(reference, str) else None
                entry = entries.get(reference) or entries.get(aid)
                relative = entry.get('exported_path' if bundle else 'location') if entry else None
                if not isinstance(relative, str) or not isinstance(digest, str):
                    return None, None
                try:
                    target = _inside(root, relative)
                    if not target.is_file() or target.stat().st_size > MAX_FILE:
                        return None, None
                    blob = target.read_bytes()
                except (OSError, ValueError):
                    return None, None
                if hashlib.sha256(blob).hexdigest() != digest:
                    return None, None
                artifact = source | dict(path=relative, artifact_id=entry['artifact_id'], kind='lab',
                                         integrity='verified', sha256=digest, media_type=entry.get('media_type'),
                                         created=_number(entry.get('created')))
                try:
                    return json.loads(blob), artifact
                except (ValueError, UnicodeDecodeError):
                    return None, artifact

            for iteration, created in built_iterations:
                if item := _iteration_lab(iteration, capsule_id, read_json, created):
                    labs.append(item)
            reports = [artifact_index[row['artifact_id']] | dict(version=row.get('version'), release=row.get('release'),
                                                                 revision=row.get('revision'), created=row['created'])
                       for row in builder_reports if row['artifact_id'] in artifact_index]
            if builds or labs or reports or run_measurements:
                builder_summaries.append(dict(builds=[source | item for item in builds],
                                              labs=[source | item for item in labs], reports=reports))
        if (capsule_id in _capsules(task) or consumes_analysis or run_artifacts
                or run_receipts or run_measurements or run_analyses):
            related_runs.append({key: run[key] for key in ('id', 'name', 'kind')})
        artifacts.extend(run_artifacts)
        measurements.extend(run_measurements)
        receipts.extend(run_receipts)
        for row in run_analyses:
            ids = {value for value in (row['observation_id'], row['call']) if isinstance(value, str)}
            keys = {(task_id, value) for value in ids} or {(task_id, row['kind'], row['created'])}
            if keys.isdisjoint(seen_analyses):
                analyses.append(row)
                seen_analyses.update(keys)

    return sanitize(dict(
        latest_verify_receipt=max(receipts, key=lambda row: (row['created'] or 0, row['integrity'] == 'verified',
                                                           row['artifact_id'] is not None), default=None),
        artifacts=sorted(artifacts, key=lambda row: row['created'] or 0, reverse=True),
        measurements=measurements, analyses=sorted(analyses, key=lambda row: row['created'] or 0, reverse=True),
        runs=related_runs,
        latest_builder_run=_latest_builder_evidence(builder_summaries),
    ))


def _latest_builder_evidence(summaries):
    """Latest lab, its matching build and the latest report, each from whichever run and release produced it.

    Evidence is not limited to the current sealed release: each item carries the capsule version that
    produced it, so earlier releases' builds and labs are shown and labelled instead of "awaiting".
    """
    def newest(rows, extra=lambda row: 0):
        return max(rows, key=lambda row: (row.get('created') or 0, extra(row)), default=None)

    labs = [row for summary in summaries for row in summary['labs']]
    builds = [row for summary in summaries for row in summary['builds']]
    reports = [row for summary in summaries for row in summary['reports']]
    lab = newest(labs, lambda row: (row.get('parity') is not None) + (row.get('activation') is not None))
    build = newest([row for row in builds if lab and row['binary_sha256'] == lab.get('binary_sha256')]) or newest(builds)
    report = newest(reports, lambda row: _number(row.get('revision')) or 0)
    anchor = report or lab or build
    if not anchor:
        return None
    return dict(run_id=anchor['run_id'], run_name=anchor['run_name'], build=build, lab=lab, report=report,
                updated=max((row.get('created') or 0 for row in (build, lab, report) if row), default=0))
