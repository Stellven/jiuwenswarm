"""Read-only projections of admitted Factory node contracts and their evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from fastapi import HTTPException

from jiuwenswarm.factory import demo_board, story
from jiuwenswarm.factory.node_contract import from_contract
from jiuwenswarm.factory.node_finalize import digest
from jiuwenswarm.factory.run_pause import current_in
from .capsule_catalog import SECTION_KEYS

# These capsule guides describe the pinned stock comparison. Attach the citation even when
# the current run has only reached admission, and label it as a guide or briefing finding.
COMPARISONS = {
    ('ingest_nvfp4', 'weights.build_muse_nvfp4_reader'): (
        'Stock reads per-expert NVFP4 tensors. The Muse reader splits the stacked gate/up experts and preserves the packed blocks.',
        'muse_nvfp4_reader/GUIDE.md'),
    ('wire_expert_scales', 'weights.build_expert_scale_wiring'): (
        'The tiny CPU fixture recorded NaN KLD on the stock graph and about 0.0013 with expert scale wiring.',
        'expert_scale_wiring/METHOD.md'),
    ('requant_2bit', 'weights.build_weight_pack_compiler'): (
        'The mixed recipe uses IQ2_XXS for gate and up and Q2_K for down, carrying the BF16 and scale tensors from the input pack.',
        'weight_pack_compiler/METHOD.md'),
}


def recent_rows(data, kind):
    tid = data['tasks'][0]['task_id']
    return sorted((o for o in data.get('observations', [])
                   if o['kind'] == kind and o.get('task_id', tid) == tid), key=lambda o: o.get('created') or 0)


def final_rows(data):
    return {(o['values']['node_id'], o['values']['digest']): o for o in recent_rows(data, 'node_contract_final')}


def contract_view(data, node, record, briefs):
    current = from_contract(data.get('_contract') or {}) or {}
    expected = node.get('node_contract') or node['node_id']
    preliminary = next((n for n in current.get('nodes', []) if n.get('node_id') == expected), None)
    source = f"{data['tasks'][0].get('contract_id')}.json" if preliminary else None
    final = None
    if record:
        v = record['values']
        final = v['final']
        if preliminary is None or digest(preliminary) != v.get('preliminary_digest'):
            try:
                rebuilt = demo_board.rebuild_preliminary(final, v.get('diff'))
                preliminary = rebuilt if digest(rebuilt) == v.get('preliminary_digest') else None
            except (ValueError, TypeError, KeyError, AttributeError):
                preliminary = None
            source = f"{record['obs_id']} (digest-verified reconstruction)" if preliminary else None
    elif preliminary and preliminary.get('stage') == 'final':
        final, preliminary = preliminary, None
    refusals = [dict(id=o['obs_id'], created=o.get('created'), **{k: o['values'].get(k) for k in ('problems', 'rationale', 'by')})
                for o in recent_rows(data, 'node_contract_refusal') if o['values'].get('node_id') == node['node_id']]
    return dict(preliminary=preliminary, final=final, briefing=(preliminary or final or {}).get('briefing'),
                refusals=refusals, scheduler=[s for s in briefs if s['node_id'] == node['node_id']],
                rationale=record['values'].get('rationale') if record else None, source=source,
                final_source=record['obs_id'] if record else None)


def cc_row(catalog, cc, version, *, materials=False):
    try:
        path = catalog.resolve(cc)
    except HTTPException:
        return dict(id=cc, version=version, kind=None, purpose=None, materials={})
    atlas = catalog.names['capsules'].get(Path(path).parent.as_posix(), {})
    detail = catalog._detail(path) if materials or not atlas else {}
    kind = atlas.get('kind') or detail.get('cc_kind') or detail.get('kind')
    if kind not in {'tool', 'verifier', 'builder', 'methodology'}:
        kind = 'verifier' if set(detail.get('capabilities', [])) == {'verify'} else 'tool'
    pinned = version is not None and version == detail.get('version')
    return dict(id=cc, version=version, kind=kind, title=atlas.get('title') or detail.get('cc_title'),
                purpose=atlas.get('summary') or detail.get('description'),
                materials=detail.get('materials', {}) if pinned else {},
                sections=detail.get('sections', {}) if pinned else {}, files=detail.get('files', []) if pinned else [],
                catalog_name=detail.get('name'), material_version=detail.get('version'),
                material_digest=detail.get('digest') if pinned else None, material_source='catalog' if pinned else None)


def sealed_releases(root):
    """Read immutable release indexes without opening the mutable capsule host database."""
    result = {}
    for directory in root.iterdir() if root.is_dir() else []:
        if directory.is_symlink() or not re.fullmatch(r'[0-9a-f]{64}', directory.name):
            continue
        manifest = directory / 'manifest.json'
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 1024 * 1024:
            continue
        try:
            raw = manifest.read_bytes()
            if hashlib.sha256(raw).hexdigest() != directory.name:
                continue
            value = json.loads(raw)
            decl = value['declaration']
            result.setdefault((decl['id'], decl['version']), []).append((directory.name, value))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return result


def sealed_materials(releases, cc, version, preferred=()):
    matches = releases.get((cc, version), [])
    exact = [row for row in matches if row[0] in preferred]
    matches = exact if exact else matches
    if len(matches) != 1:
        return {}
    release, value = matches[0]
    declaration = value['declaration']
    materials = {k: v['path'] for k, v in declaration.get('materials', {}).items()}
    sections = {section: path for section, keys in SECTION_KEYS.items()
                if (path := next((materials[k] for k in keys if k in materials), None))}
    return dict(materials=materials, sections=sections, material_version=version,
                material_digest=release, material_source='sealed',
                files=[dict(path=f['path'], sha256=f['sha256'], expected_sha256=f['sha256'], size=f['size'], integrity='sealed')
                       for f in value.get('files', [])])


def bindings(record, contract=None):
    values = (record or {}).get('values', {})
    final = values.get('final') or contract or {}
    return [(cc, (values.get('cc_versions') or {}).get(cc)) for cc in (final.get('work') or {}).get('bound_ccs') or []]


def capsule_checks(cc, checks, output_ids=()):
    linked = []
    for output in checks:
        if output['name'] in output_ids or str(output.get('verifier') or '').rpartition('.')[0] == cc:
            linked.append(output)
        elif any((row.get('verifier') or {}).get('cc') == cc for row in output['checks']):
            linked.append(output)
    return linked


def verdict(checks):
    if not checks:
        return 'unchecked'
    relevant = []
    for output in checks:
        countable = [r for r in output['checks'] if not r['superseded'] and r['state'] == 'finished'
                     and (r['same_settings'] or r['cited'])]
        if countable:
            relevant.append(countable[-1]['passed'])
    return 'failed' if False in relevant else 'passed' if relevant else 'pending'


def overview(data, plan, checks, catalog):
    records = final_rows(data)
    declared = {n['node_id']: n for n in (from_contract(data.get('_contract') or {}) or {}).get('nodes', [])}
    result = {}
    for node in plan.get('nodes', []):
        key = node['node_id']
        record = records.get((key, node.get('final_contract')))
        authored = declared.get(node.get('node_contract') or key, {})
        bound = bindings(record, authored if authored.get('stage') == 'final' else None)
        outputs = checks.get(key, {}).get('outputs', [])
        result[key] = [cc_row(catalog, cc, version) | dict(verdict=verdict(capsule_checks(
            cc, outputs, native_output_names(cc, record, authored if authored.get('stage') == 'final' else None))))
                       for cc, version in bound]
    return result


def _json_object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def worker_calls(transcript):
    """Index actual CC calls, using explicit node IDs or the only runnable node in a worker turn."""
    rows, pending = [], {}
    if not transcript.is_file():
        return rows
    node, turn = None, None
    with transcript.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                break
            if not any(tag in line for tag in (b'turn.start', b'chat.tool_call', b'chat.tool_result')):
                continue
            outer = _json_object(line.decode(errors='replace'))
            kind = outer.get('event_type', outer.get('event'))
            if kind == 'turn.start':
                q = _json_object(outer.get('query'))
                runnable = (q.get('next_work') or {}).get('runnable') or []
                node = outer.get('node_id') or q.get('node_id') or (runnable[0].get('node_id') if len(runnable) == 1 else None)
                turn = outer.get('turn')
            elif kind == 'chat.tool_call':
                tool = _json_object(outer.get('tool_call'))
                if not str(tool.get('name', '')).endswith('cc_call'):
                    continue
                args = _json_object(tool.get('arguments'))
                if not (args.get('cc') and args.get('capability') and tool.get('tool_call_id')):
                    continue
                inputs = _json_object(args.get('inputs'))
                node_id = inputs.get('node_id') or _json_object(inputs.get('request')).get('node_id') or node
                row = dict(id=tool['tool_call_id'], node_id=node_id, request_node_id=node_id, cc=args['cc'], capability=args['capability'],
                           created=outer.get('t'), turn=turn, state=None, reason=None,
                           attempt_id=inputs.get('attempt_id'))
                rows.append(row)
                pending[row['id']] = row
            elif kind == 'chat.tool_result' and (row := pending.pop(outer.get('tool_call_id'), None)):
                result = _json_object(outer.get('result'))
                receipt = _json_object(demo_board._tool_text(outer.get('result')))
                outputs = _json_object(receipt.get('outputs'))
                nested = _json_object(outputs.get('result'))
                state = receipt.get('state') or result.get('status')
                assessment = outputs if isinstance(outputs.get('checks'), list) else nested
                done = assessment.get('done')
                assessed = receipt.get('cc') == row['cc'] and receipt.get('capability') == row['capability']
                row.update(state=state, reason=receipt.get('reason'),
                           attempt_id=outputs.get('attempt_id') or nested.get('attempt_id') or row.get('attempt_id'),
                           node_id=outputs.get('node_id') or nested.get('node_id') or row['node_id'], release=receipt.get('release'),
                           verifier_passed=done if assessed and isinstance(assessment.get('checks'), list) and type(done) is bool else None,
                           result_at=outer.get('t'), receipt_id=receipt.get('call'),
                           failed=bool(result.get('error') or result.get('failed') or result.get('is_error')
                                       or _json_object(result.get('result')).get('isError') or state in {
                                           'failed', 'error', 'refused', 'rejected', 'failure', 'incomplete'}))
    return rows


def _node_runs(data, node):
    records = {o['values'].get('attempt_id'): o for o in recent_rows(data, 'capped_run')}
    rows = []
    for attempt in data.get('attempts', []):
        aid = attempt['attempt_id']
        record = records.pop(aid, None)
        values = record['values'] | {'_created': record['created']} if record else None
        row = demo_board.run_view(attempt, values)
        if row['node_id'] == node['node_id'] or aid in node.get('attempt_ids', []):
            rows.append(row | dict(source=record['obs_id'] if record else aid,
                                   artifact_ids=record.get('source_artifacts', []) if record else []))
    for record in records.values():
        if record['values'].get('node_id') == node['node_id']:
            rows.append(demo_board.run_view(None, record['values'] | {'_created': record['created']}) |
                        dict(source=record['obs_id'], artifact_ids=record.get('source_artifacts', [])))
    return sorted(rows, key=lambda r: r.get('t_queued') or r.get('t_start') or 0)


def native_output_names(cc, record, contract=None):
    """Relate host production/check records to the capsule responsible for their output type."""
    final = (record or {}).get('values', {}).get('final') or contract or {}
    names = []
    for output in final.get('outputs', []):
        name, kind = output.get('name'), output.get('kind')
        if ((cc == 'factory.capped_runner' and ('pack' in name or name in {'smoke', 'image_check'}))
                or (cc == 'factory.builder' and kind in {'source_bundle', 'image'})
                or (cc == 'factory.lab_manager' and kind in {'lab_request', 'source_bundle'})):
            names.append(name)
    return names


def _manifest_summary(manifest):
    if not isinstance(manifest, dict):
        return {}
    fields = ('name', 'architecture', 'format', 'digest', 'census', 'census_by_type', 'tensor_count', 'file_type')
    result = {k: manifest[k] for k in fields if k in manifest}
    files = manifest.get('files') or manifest.get('shards')
    if isinstance(files, list) and files:
        result['shard_count'] = len(files)
        sizes = [f.get('bytes') for f in files if isinstance(f, dict)]
        if len(sizes) == len(files) and all(isinstance(size, int) for size in sizes):
            result['bytes'] = sum(sizes)
    for key in ('bytes', 'total_bytes'):
        if key in manifest:
            result['bytes'] = manifest[key]
            break
    return result


def _output_summary(kind, refs):
    result = {}
    for o in refs:
        v = o['values']
        run = _json_object(v.get('result'))
        if kind == 'pack':
            value = v.get('hashed_shard_manifest') or v.get('manifest') or run.get('manifest')
            if isinstance(value, dict):
                result.update(_manifest_summary(value))
            elif v.get('recipe') in {'convert', 'quantize', 'manifest'} and not run.get('probe'):
                for key, item in _manifest_summary(run).items():
                    result.setdefault(key, item)
        elif kind == 'plan':
            if plan := v.get('batch_plan') or v.get('plan') or run.get('plan'):
                result.update(_json_object(plan))
            elif v.get('format') == 'factory.prefill-batch-plan/1' or (
                    'device_budget_mib' in v and any(k in v for k in ('argv', 'server_args', 'batch', 'ubatch', 'b', 'ub'))):
                result.update(v)
        elif kind in {'image', 'source_bundle'}:
            for source in (v, run, _json_object(v.get('image')), _json_object(v.get('build'))):
                result.update({k: source[k] for k in ('image_id', 'image_tag', 'tag', 'retention_tag', 'binary_digest', 'binary_sha256',
                                                     'binaries', 'name', 'build_s', 'commit', 'base_commit', 'build_receipt')
                               if source.get(k) is not None})
            image = _json_object(v.get('image'))
            if image_id := image.get('id') or image.get('Id'):
                result['image_id'] = image_id
            if image.get('RepoTags') and not result.get('tag'):
                result['tag'] = image['RepoTags'][0]
            if executable := v.get('executable_sha256') or _json_object(v.get('executable')).get('sha256'):
                result['binary_sha256'] = executable
    return result


def outputs_view(data, node, checks, read_artifact=None):
    obs = {o['obs_id']: o for o in data.get('observations', [])}
    artifacts = {a['artifact_id']: a for a in data.get('artifacts', [])}
    outputs = []
    for output in checks:
        selected = [r for r in output['checks'] if r['state'] == 'finished' and not r['superseded']]
        check = next((r for r in reversed(selected) if r['cited']), None) or (selected[-1] if selected else {})
        record = obs.get(check.get('obs_id'), {})
        values = record.get('values') or {}
        refs = values.get('refs') or {}
        row_ids = list(refs.get('evidence_ids') or [])
        records = [obs[k] for k in row_ids if k in obs]
        for row in records[:]:
            for field in ('capped_run_id', 'hash_capped_run_id'):
                if key := row['values'].get(field):
                    if key in obs and obs[key] not in records:
                        records.append(obs[key])
        direct = [*check.get('artifacts', []), *(refs.get('artifact_ids') or [])]
        if attempt_id := refs.get('build_attempt_id'):
            direct.extend([f'{attempt_id}:receipt', f'{attempt_id}:build-record'])
        ids = list(dict.fromkeys(a for a in [*direct, *row_ids, *(a for r in records for a in (r.get('source_artifacts') or []))]
                                if a in artifacts))
        name, kind = output['name'], output['kind']
        if kind == 'evidence':
            kind = 'pack' if 'pack' in name else 'plan' if name == 'batch_plan' else kind
        summary = _output_summary(kind, records)
        if kind == 'image' and read_artifact:
            for aid in ids:
                if aid.endswith((':receipt', ':build-record')):
                    receipt = read_artifact(artifacts[aid])
                    summary.update(_output_summary(kind, [dict(values=receipt)]))
                    if receipt and aid.endswith(':receipt'):
                        summary['build_receipt'] = aid
        if kind == 'plan' and read_artifact and not summary:
            for aid in ids:
                if artifacts[aid].get('media_type') == 'application/json':
                    summary.update(_output_summary(kind, [dict(values=read_artifact(artifacts[aid]))]))
        diff_id = next((a for a in ids if kind == 'diff' and (a.endswith(('-diff', '.diff', '.patch'))
                        or artifacts[a].get('media_type') in {'text/x-diff', 'text/x-patch'})), None)
        if diff_id:
            producer = min((o for o in obs.values() if o.get('kind') == 'node_check'
                            and diff_id in (o.get('source_artifacts') or []) and not o['values'].get('reused_from')),
                           key=lambda o: o.get('created') or 0, default=record)
            summary.update(diff_artifact_id=diff_id, diff_source=producer.get('obs_id'),
                           base=(producer.get('values') or {}).get('head'), sha256=artifacts[diff_id].get('sha256'))
        replay = next((r['values']['replayed_from'] for r in records if r['values'].get('replayed_from')), None)
        outputs.append(dict(id=name, name=name, kind=kind, artifact_ids=ids, summary=summary, replayed_from=replay,
                            replay_source=story.replay_origin(replay), source=check.get('obs_id'),
                            evidence_ids=[r['obs_id'] for r in records]))
    return outputs


def _comparison(key, cc, contract, outputs, runs):
    if key == 'size_prefill_batch' and cc == 'engine.size_prefill_batch':
        fact = next((f for f in (contract.get('briefing') or {}).get('facts', []) if '287 s to 114 s' in f), None)
        if fact:
            return dict(text=fact, source=f"{contract.get('source')} · planner briefing / report-abcde.json arms C and D")
    if (entry := COMPARISONS.get((key, cc))) and (key != 'requant_2bit' or any(
            o['summary'].get('census') for o in outputs if o['kind'] == 'pack')):
        return dict(text=entry[0], source=entry[1], material=entry[1].split('/', 1)[1])
    if cc == 'factory.capped_runner':
        replay = next((r for r in runs if r['replay_source'] and r['state'] == 'succeeded'), None)
        if replay:
            return dict(text=f"The original production job made the pack. This node verified its retained output in "
                        f"{replay['verification_duration'] or 'a separately recorded job'}: {replay['replay_source']}.",
                        source=replay['source'])
    return None


def _recorded_fact(cc, record, checks, calls):
    finished = [(o['name'], r) for o in checks for r in o['checks'] if r['state'] == 'finished' and not r['superseded']]
    if finished:
        output, check = max(finished, key=lambda pair: pair[1].get('created') or 0)
        return dict(text=f"The host recorded {'a pass' if check['passed'] else 'a failure'} for {output}.",
                    source=check['obs_id'])
    if calls:
        call = calls[-1]
        state = f" ({call['state']})" if call['state'] else ''
        return dict(text=f"The worker called {call['capability']}{state}.", source=call['id'])
    if record:
        author = record['values'].get('by') or 'The scheduler'
        return dict(text=f"{author} bound {cc} when it finalized this node.", source=record['obs_id'])
    return None


def node_detail(data, node, check_view, catalog, briefs, all_calls, releases, read_artifact):
    key = node['node_id']
    record = final_rows(data).get((key, node.get('final_contract')))
    contract = contract_view(data, node, record, briefs)
    checks = check_view.get('outputs', [])
    outputs = outputs_view(data, node, checks, read_artifact)
    runs = _node_runs(data, node)
    bound = bindings(record, contract['final'])
    capsule_ids = {cc for cc, _ in bound}
    pack_owners = {output['name']: str(output.get('verifier') or '').rpartition('.')[0] for output in checks}
    capsules = []
    for cc, version in bound:
        calls = [c for c in all_calls if c['node_id'] == key and c['cc'] == cc]
        attempt_ids = {c['attempt_id'] for c in calls if c.get('attempt_id')}
        owned_checks = capsule_checks(cc, checks, native_output_names(cc, record, contract['final']))
        names = {o['name'] for o in owned_checks}
        own_outputs = [o for o in outputs if o['name'] in names
                       and (o['kind'] != 'pack' or pack_owners[o['name']] not in capsule_ids
                            or pack_owners[o['name']] == cc)]
        own_runs = [r for r in runs if r['attempt_id'] in attempt_ids or (cc == 'factory.capped_runner' and r['recorded'])]
        preferred = {c.get('release') for c in calls} | {(r.get('verifier') or {}).get('release')
                    for o in owned_checks for r in o['checks'] if (r.get('verifier') or {}).get('cc') == cc}
        pinned = sealed_materials(releases, cc, version, preferred)
        comparison = _comparison(key, cc, contract, own_outputs, own_runs)
        capsules.append(cc_row(catalog, cc, version, materials=True) | pinned | dict(
            verdict=verdict(owned_checks), calls=dict(count=len(calls), first=calls[0]['created'] if calls else None,
                last=calls[-1]['created'] if calls else None, failures=sum(bool(c.get('failed')) for c in calls), records=calls),
            runs=own_runs, outputs=own_outputs, checks=owned_checks, comparison=comparison,
            evidence_fact=None if comparison else _recorded_fact(cc, record, owned_checks, calls)))
    return dict(node_id=key, contract=contract, capsules=capsules, outputs=outputs, runs=runs)


def run_state(data, plan, markers, running, now):
    state = data['_meta']['controller_state']
    outcome = data['_meta'].get('outcome')
    latest = max(data.get('decisions', []), key=lambda row: row.get('rev', 0), default={})
    decision_outcome = (latest.get('action') or {}).get('type')
    if not outcome and (decision_outcome in story.TERMINAL or str(decision_outcome).startswith('stop_')):
        outcome = decision_outcome
    stopped = str(outcome or '').startswith('stop_')
    result = dict(state='idle', reason=state.get('stop_reason'), by=None, since=None, node_id=None, job=None, markers=markers)
    if outcome in story.TERMINAL:
        decision = max((row for row in data.get('decisions', []) if (row.get('action') or {}).get('type') == outcome),
                       key=lambda row: row.get('rev', 0), default={})
        return result | dict(state='finished', outcome=outcome, reason=None,
                             since=state.get('finished') or decision.get('created'), source=decision.get('decision_id'))
    if pause := current_in(data):
        return result | dict(state='paused', reason=pause.get('reason'), by=pause.get('by'), since=pause.get('at'),
                             source=pause.get('obs_id'))
    if not running and 'PAUSE.md' in markers and not recent_rows(data, 'operator_pause'):
        return result | dict(state='paused', since=markers['PAUSE.md']['mtime'], source='PAUSE.md')
    if not running and outcome not in story.TERMINAL and (
            'HALT.md' in markers or (not stopped and 'HALT.md' in (result['reason'] or ''))):
        halts = recent_rows(data, 'operator_halt')
        halt = halts[-1] if halts else {}
        values = halt.get('values') or {}
        return result | dict(state='halted', reason=values.get('reason') or result['reason'],
                             node_id=values.get('node_id'), since=halt.get('created') or markers.get('HALT.md', {}).get('mtime'),
                             source=halt.get('obs_id') or 'HALT.md')
    holds = [n for n in plan['nodes'] if str(n.get('hold', '')).startswith(demo_board.STEP_PREFIX)]
    if holds:
        return result | dict(state='step', node_id=holds[0]['node_id'], reason=holds[0]['hold'],
                             since=markers.get('STEP.md', {}).get('mtime'), source='STEP.md' if 'STEP.md' in markers else None)
    completed = {o['values']['attempt_id'] for o in recent_rows(data, 'capped_run')
                 if o['values'].get('attempt_id') and o['values'].get('outcome')}
    jobs = [a for a in data.get('attempts', []) if a.get('state') in story.ACTIVE
            and not a.get('ended') and a['attempt_id'] not in completed]
    if jobs:
        job = jobs[-1]
        request = job.get('request') or {}
        since = job.get('started') or next((h.get('created') for h in job.get('history', []) if h.get('created')), None)
        return result | dict(state='waiting', reason=None, node_id=request.get('node_id'), since=since, job=dict(
            attempt_id=job['attempt_id'], effect=request.get('recipe') or job.get('kind'), state=job['state'],
            since=since, elapsed_seconds=max(0, now - since) if since is not None else None,
            replayed_from=request.get('replayed_from'), replay_source=story.replay_origin(request.get('replayed_from'))))
    if running:
        active = [node['node_id'] for node in plan['nodes'] if node.get('state') == 'running']
        return result | dict(state='running', reason=None, since=state.get('started'),
                             node_id=active[0] if len(active) == 1 else None)
    if stopped:
        # The controller can retain a checkpoint's stop_reason after a new terminal decision.
        decision = max((row for row in data.get('decisions', []) if (row.get('action') or {}).get('type') == outcome),
                       key=lambda row: row.get('rev', 0), default={})
        return result | dict(state='stopped', outcome=outcome, reason=decision.get('reason_for_change'),
                             source=decision.get('decision_id'),
                             node_id=(decision.get('observations') or {}).get('node_id'),
                             since=state.get('finished') or decision.get('created'))
    if outcome:
        return result | dict(state='paused' if outcome == 'paused' else 'finished', outcome=outcome, since=state.get('finished'))
    return result | dict(reason=None) if 'STEP.md' in (result['reason'] or '') else result


def native_replay(data, plan, files, source_home, *, trails=None):
    """Project a completed, contracted native run onto the Nov 20 curated step format."""
    task = data['tasks'][0]
    outcome = data.get('_meta', {}).get('outcome')
    if (task.get('contract_id') != 'muse-2bit-demo-r8' or str(outcome or '').startswith('stop_') or not plan['nodes']
            or any(n['state'] not in {'done', 'cancelled', 'superseded'} for n in plan['nodes'])):
        return None
    steps = []
    reruns = recent_rows(data, 'capped_run')
    file_by_id = {aid: row for row in files if row['integrity'] == 'verified' for aid in row['artifact_ids']}
    observations = {o['obs_id']: o for o in data.get('observations', [])}
    finals = final_rows(data)
    patch_rows = recent_rows(data, 'taskgraph_patch')
    completed = {}
    for row in patch_rows:
        value = row['values']
        patch = value.get('patch') or {}
        for change in patch.get('update', []):
            if change.get('state') == 'done':
                completed[change['node_id']] = row
        if value.get('origin') == 'operator' and (changes := patch.get('revise')):
            graph_nodes = [c['node_id'] for c in changes]
            steps.append(dict(node_id=graph_nodes[0], graph_nodes=graph_nodes, recorded_plan_nodes=graph_nodes,
                              presentation_title=f"Graph revision {value['rev']}", original_kind='revise',
                              original_summary=', '.join(f"{c['action']} {c['node_id']}" for c in changes),
                              primary_record=row['obs_id'], created=row.get('created') or 0,
                              records=[dict(id=row['obs_id'], table='observations', task_id=task['task_id'],
                                            source_home=source_home)], key_files=[], graph_rev=value['rev']))
    for node in plan['nodes']:
        key = node['node_id']
        final = finals.get((key, node.get('final_contract')))
        rows = [observations[r] for r in node.get('evidence_ids', []) if r in observations]
        if final:
            rows.insert(0, final)
        if not rows:
            continue
        records = [dict(id=o['obs_id'], table='observations', task_id=task['task_id'], source_home=source_home)
                   for o in rows]
        ids = dict.fromkeys(aid for row in rows for aid in (row.get('source_artifacts') or []) if aid in file_by_id)
        key_files = [dict(path=file_by_id[aid]['path'], label=file_by_id[aid]['display_path']) for aid in list(ids)[:5]]
        latest = max(rows, key=lambda row: row.get('created') or 0)
        done = completed.get(key, latest)
        replay = next((o['values']['replayed_from'] for o in reruns
                       if o['values'].get('node_id') == key and o['values'].get('replayed_from')), None)
        steps.append(dict(node_id=key, graph_nodes=[key], recorded_plan_nodes=[key], presentation_title=node['title'],
                          original_kind=latest['kind'], original_summary=node.get('reason') or node['title'],
                          primary_record=latest['obs_id'], created=done.get('created') or 0, records=records,
                          key_files=key_files, replayed_from=replay, replay_source=story.replay_origin(replay),
                          say=node.get('reason', '')))
    for key, trail in (trails or {}).items():
        for correction in trail['events']:
            kind, source = correction['kind'], correction['source']
            ids = list(dict.fromkeys([source, *(correction.get('evidence_ids') or [])]))
            key_files = [dict(path=file_by_id[aid]['path'], label=file_by_id[aid]['display_path'])
                         for aid in ids if aid in file_by_id][:5]
            title = {'finding': 'Finding', 'note': 'Operator note', 'repair': 'Recorded repair',
                     'passing_check': 'Passing output check'}[kind]
            steps.append(dict(node_id=key, graph_nodes=[key], recorded_plan_nodes=[key],
                              presentation_title=f'{key} · {title}', original_kind=kind, correction=correction,
                              original_summary=correction['text'], primary_record=source,
                              created=correction['created'], key_files=key_files,
                              records=[dict(id=source, table='operator-inbox' if kind == 'note' else
                                           'observations' if source in observations else 'artifacts',
                                           task_id=task['task_id'], source_home=source_home)]))
    correction_order = {'finding': 0, 'note': 1, 'repair': 2, 'passing_check': 3}
    steps.sort(key=lambda step: (step['created'], correction_order.get(step['original_kind'], 4)))
    for cursor, step in enumerate(steps, 1):
        step.update(step=cursor, event_cursor=cursor)
    return dict(schema='factory.curated-replay/1', title=task['task_id'], summary=task['objective'], native=True,
                source_homes=[source_home], steps=steps) if steps else None
