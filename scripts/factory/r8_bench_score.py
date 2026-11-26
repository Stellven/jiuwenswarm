"""Score the final campaign's two fixed MMLU legs on an existing capped server."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import tarfile
import time

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.ccs.paired_accuracy import paired
from scripts.factory import lab_v4_quiet
from scripts.factory.lab_v4_fast import save, server_peak_rss

LOOKS = (50, 100, 160, 250)
SLOTS = 32
PACKS = {'7': 'NVFP4', '8': 'MIXED_2BIT'}
REQUEST = dict(n_predict=1, n_probs=20, temperature=0, seed=1, cache_prompt=False)
RECOVERABLE_FAILURES = {'REQUEST', 'MMLU_REPLY'}


@dataclass(frozen=True)
class Prepared:
    proposal: dict
    questions: list
    source: dict


def prepare(proposal):
    """Verify the local dataset and ordered case pins before entering the quiet window."""
    proposal = deepcopy(proposal)
    mmlu = proposal['mmlu']
    plan = proposal['request_plans']['mmlu250']
    if (mmlu['planned_looks'] != list(LOOKS) or mmlu['z'] != paired.Z_SEQ
            or mmlu['margin_points'] != 5 or mmlu['role_reference'] != '7' or mmlu['role_candidate'] != '8'
            or mmlu['verifier'] != 'eval.paired_accuracy' or mmlu['order_seed'] != paired.SEED
            or plan != dict(question_scores=250, request_batches=[32] * 7 + [26], path='/completion', **REQUEST)):
        raise ValueError('MMLU protocol differs from the approved paired plan')

    dataset = Path(mmlu['dataset_path']).resolve()
    archive = Path(mmlu['archive_path']).resolve()
    with archive.open('rb') as raw:
        archive_sha = hashlib.file_digest(raw, 'sha256').hexdigest()
        if archive_sha != mmlu['archive_sha256']:
            raise ValueError('MMLU archive digest differs from the ledger')
        raw.seek(0)
        with tarfile.open(fileobj=raw) as tar:
            members = {member.name: member for member in tar.getmembers()
                       if member.isfile() and Path(member.name).parent == Path('data/test')
                       and member.name.endswith('_test.csv')}
            paths = {f'data/test/{path.name}': path for path in dataset.glob('*_test.csv')}
            if not paths or paths.keys() != members.keys():
                raise ValueError('MMLU extracted test file set differs from the pinned archive')
            for name, path in paths.items():
                with tar.extractfile(members[name]) as original:
                    if path.read_bytes() != original.read():
                        raise ValueError(f'MMLU test file differs from the pinned archive: {name}')

    order = paired.mmlu_order(dataset, mmlu['order_seed'])
    full_sha = paired.sha(json.dumps([q['id'] for q in order]))
    questions = [{**q, 'prompt': paired.prompt(q)} for q in order[:LOOKS[-1]]]
    ids = [q['id'] for q in questions]
    case_sha = paired.sha(json.dumps(ids, separators=(',', ':')))
    if (len(ids) != LOOKS[-1] or len(set(ids)) != len(ids) or ids != mmlu['question_ids_in_order']
            or case_sha != mmlu['question_ids_sha256'] or full_sha != mmlu['historical_full_order_sha256']):
        raise ValueError('MMLU question order differs from the ledger')

    historical = mmlu['historical_case_source']
    history_path = Path(historical['path']).resolve()
    history_bytes = history_path.read_bytes()
    history_sha = hashlib.sha256(history_bytes).hexdigest()
    if history_sha != historical['sha256'] or historical['records'] != ['/rows/A', '/rows/B']:
        raise ValueError('Historical case source differs from the ledger')
    history = json.loads(history_bytes)
    for arm in ('A', 'B'):
        rows = history['rows'][arm]
        for q in questions:
            row = rows[q['id']]
            if q['answer'] not in paired.LETTERS or (row['answer'], row['prompt_sha256']) != (
                    q['answer'], paired.sha(q['prompt'])):
                raise ValueError(f'Canonical MMLU case differs from historical case source: {q["id"]}')
    source = dict(dataset_path=str(dataset), archive_path=str(archive), archive_sha256=archive_sha,
                  historical_case_source=dict(path=str(history_path), sha256=history_sha, records=historical['records']),
                  question_ids_in_order=ids, question_ids_sha256=case_sha, full_order_sha256=full_sha,
                  order_seed=mmlu['order_seed'])
    return Prepared(proposal, questions, source)


def _leg(proposal, leg):
    leg_id = leg['id'] if isinstance(leg, dict) else str(leg)
    if leg_id not in PACKS:
        raise ValueError(f'Unsupported MMLU leg: {leg_id}')
    record, = (item for item in proposal['required_loads'] if item['id'] == leg_id)
    if (record['recipe'] != 'paired_mmlu_score' or record['pack'] != PACKS[leg_id]
            or record['request_plan'] != 'mmlu250' or record['np'] != SLOTS or '-kvu' not in record['extra_args']):
        raise ValueError(f'MMLU leg {leg_id} differs from the approved scoring plan')
    return record


def _server_identity(server, proposal, leg):
    argv = list(server.argv)
    pack = proposal['pack_pins'][leg['pack']]
    engine = proposal['engine']
    model_index = argv.index('-m')
    executable = Path(argv[model_index - 1]).resolve()
    model = argv[model_index + 1]
    if Path(model).resolve() != Path(pack['first_shard']).resolve():
        raise ValueError(f'MMLU leg {leg["id"]} has the wrong running server pack')
    for key in ('ctx', 'np', 'batch', 'ubatch', 'moe_cache_mib'):
        flag = proposal['settings_args'][key]
        if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != str(leg[key]):
            raise ValueError(f'MMLU leg {leg["id"]} has the wrong running server setting: {flag}')
    if any(flag not in argv for flag in leg['extra_args']):
        raise ValueError(f'MMLU leg {leg["id"]} is missing an approved server flag')
    with executable.open('rb') as handle:
        binary_sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    manifest = Path(pack['manifest']).resolve()
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if binary_sha != engine['required_image_executable_sha256'] or manifest_sha != pack['manifest_sha256']:
        raise ValueError(f'MMLU leg {leg["id"]} engine executable or pack manifest differs from the ledger')
    return dict(argv=argv, pid=server.proc.pid, log_path=str(server.log), pack_first_shard=model,
                pack_manifest_path=str(manifest), pack_manifest_sha256=manifest_sha,
                image_id=engine['required_verified_image_id'], llama_server_path=str(executable),
                llama_server_sha256=binary_sha, memory_cap=server.run.cap)


def _scores(server, questions):
    body = dict(prompt=[q['prompt'] for q in questions], **REQUEST)
    reply = server.post(body)
    try:
        return _response_rows(reply, questions)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise capped_run.RunError('MMLU_REPLY', str(exc)) from exc


def _response_rows(reply, questions):
    if isinstance(reply, dict):
        reply = [reply]
    if (not isinstance(reply, list) or len(reply) != len(questions)
            or any(not isinstance(item, dict) or type(item.get('index')) is not int for item in reply)
            or {item['index'] for item in reply} != set(range(len(questions)))):
        raise ValueError('Native MMLU reply is missing or has duplicate prompt indices')

    rows = {}
    for q, item in zip(questions, sorted(reply, key=lambda item: item['index'])):
        if (item.get('error') or item.get('stop') is not True or item.get('truncated') is not False
                or item.get('tokens_predicted') != REQUEST['n_predict']
                or type(item.get('tokens_evaluated')) is not int or item['tokens_evaluated'] <= 0):
            raise ValueError(f'MMLU reply did not score one token on the complete prompt: {q["id"]}')
        distributions = item.get('completion_probabilities') or []
        if len(distributions) != 1:
            raise ValueError(f'MMLU reply lacks a single-token distribution: {q["id"]}')
        distribution = distributions[0]
        if 'top_logprobs' in distribution:
            top = [(t['token'], t['logprob']) for t in distribution['top_logprobs']]
        else:
            top = [(t['tok_str'], math.log(max(t['prob'], 1e-12))) for t in distribution.get('probs', [])]
        if len(top) != REQUEST['n_probs'] or any(not math.isfinite(lp) or lp > 0 for _, lp in top):
            raise ValueError(f'MMLU reply lacks the requested top-token probabilities: {q["id"]}')
        probs = paired.letter_probs(top)
        mass = sum(probs.values())
        pick = max(probs, key=probs.get)
        rows[q['id']] = dict(prompt_sha256=paired.sha(q['prompt']), prompt_tokens=item['tokens_evaluated'],
                             probs={key: round(val, 6) for key, val in probs.items()}, letter_mass=round(mass, 4),
                             pick=pick, answer=q['answer'], correct=pick == q['answer'] and mass > 0,
                             top_token=top[0][0], response_index=item['index'], slot_id=item.get('id_slot'))
    return rows


def _after_request_failure(server, batch):
    if server.proc.poll() is not None:
        raise capped_run.RunError('SERVER_EXIT', f'llama-server exited {server.proc.returncode} after failed request')
    server.run.watch(server.proc)
    resources = server.run.task['resources']
    gate = capped_run.machine({'resources': dict(resources, need_available_gib=resources['floor_gib'])},
                              server.run.home, own_pids=[server.proc.pid])
    batch['post_failure_machine_gate'] = gate
    if not gate['ok']:
        raise capped_run.RunError('MACHINE_BUSY', 'resident-server machine gate closed after failed request')


def _paired(out, prepared, legs):
    ids = prepared.source['question_ids_in_order']
    mmlu = prepared.proposal['mmlu']
    accepted = {}
    for leg_id, report in legs.items():
        if report['source'] != prepared.source or report['leg'] != leg_id:
            raise ValueError(f'MMLU leg {leg_id} report has different case or leg identity')
        accepted[leg_id] = {qid: report['rows'][qid] for batch in report['batches']
                            if batch['quiet']['status'] == 'accepted' for qid in batch['question_ids']}
    ref, cand = accepted.get('7', {}), accepted.get('8', {})
    prefix = 0
    for qid in ids:
        if qid not in ref or qid not in cand:
            break
        prefix += 1
    looks = [paired.look(ref, cand, ids[:n], mmlu['margin_points'], mmlu['z'], final=n == LOOKS[-1])
             for n in LOOKS if n <= prefix]
    complete = (prefix == LOOKS[-1] and all(legs[key]['status'] == 'complete' for key in PACKS))
    verdict = next((look for look in looks if look['decision'] in {'pass', 'fail', 'report'}), None)
    report = dict(format='muse-r8-bench-paired/1', verifier=mmlu['verifier'], source=prepared.source,
                  reference_leg='7', candidate_leg='8', planned_looks=list(LOOKS), looks=looks,
                  eligible_paired_prefix=prefix, complete=complete, decision=verdict['decision'] if complete else None,
                  decision_n=verdict['n'] if complete else None,
                  legs={key: dict(path=f'mmlu-{key}.json', status=record['status'], scores=len(record['rows']),
                                  accepted_scores=len(accepted[key])) for key, record in legs.items()})
    save(out / 'mmlu-paired.json', report)


def score(server, monitor, proposal, out, leg):
    """Persist one attempt at a scoring leg. The caller owns server/monitor lifecycle."""
    prepared = proposal if isinstance(proposal, Prepared) else prepare(proposal)
    proposal = prepared.proposal
    leg = _leg(proposal, leg)
    leg_id = leg['id']
    if monitor.server is not server or monitor.limits.get('campaign') != lab_v4_quiet.EMPTY:
        raise ValueError('MMLU requires the amended quiet monitor attached to the running server')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'mmlu-{leg_id}.json'
    report = dict(format='muse-r8-bench-mmlu/1', leg=leg_id, pack=leg['pack'], status='in_progress',
                  source=prepared.source, server=_server_identity(server, proposal, leg), quiet_policy=monitor.limits,
                  request=dict(path='/completion', **REQUEST), batches=[], rows={})
    legs = {leg_id: report}
    if leg_id == '8':
        legs['7'] = json.loads((out / 'mmlu-7.json').read_text())
        if legs['7']['source'] != prepared.source or legs['7']['leg'] != '7' or legs['7']['status'] != 'complete':
            raise ValueError('MMLU candidate requires a complete reference leg on the same ordered cases')
    # Reserve the attempt exclusively. A partial report is evidence of an attempt, including after interruption.
    with path.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=1)
    start = 0
    try:
        for size in proposal['request_plans']['mmlu250']['request_batches']:
            questions = prepared.questions[start:start + size]
            batch = dict(index=len(report['batches']), question_ids=[q['id'] for q in questions],
                         quiet=dict(status='pending', reasons=[], samples=[]))
            report['batches'].append(batch)
            save(path, report)
            first = None
            admission_start = len(monitor.samples)
            error = None
            try:
                server.run.watch(server.proc)
                first, _ = monitor.wait('start', 'during', server.run.log)
                admission = monitor.samples[first]
                if not (admission.get('idle_slot') and (admission.get('resident_machine_gate') or {}).get('ok')):
                    raise capped_run.RunError('MACHINE_BUSY', 'MMLU batch lacks idle-server machine admission')
                t0 = time.monotonic()
                try:
                    report['rows'].update(_scores(server, questions))
                finally:
                    batch['request_seconds'] = round(time.monotonic() - t0, 3)
            except BaseException as exc:
                error = exc
            if first is None:
                samples = monitor.samples[admission_start:]
                reasons = [reason for sample in samples for reason in sample.get('reasons', [])]
            else:
                try:
                    last = monitor.mark('end', 'between_rows')
                    samples = monitor.samples[first:last + 1]
                except Exception as exc:
                    samples = monitor.samples[first:]
                    error = error or exc
                reasons = lab_v4_quiet.evidence_issues(samples, monitor.limits)
                batch['admission_wait_samples'] = monitor.samples[admission_start:first]
            unverified = ('missing ', 'incomplete ', 'probe unavailable', 'quiet probe did not pass',
                          'lacks idle-server machine admission')
            missing_evidence = any(fragment in reason for reason in reasons for fragment in unverified)
            if error:
                reasons.append(str(error) or type(error).__name__)
                batch['error'] = dict(code=getattr(error, 'code', type(error).__name__), message=str(error))
            if missing_evidence and (error is None or getattr(error, 'code', None) in RECOVERABLE_FAILURES):
                error = capped_run.RunError('LAB_NOT_QUIET', 'could not verify MMLU batch quiet evidence')
                reasons.append(str(error))
            if first is not None and getattr(error, 'code', None) in RECOVERABLE_FAILURES:
                try:
                    _after_request_failure(server, batch)
                except BaseException as exc:
                    error = exc
                    reasons.append(str(error) or type(error).__name__)
                else:
                    error = None
            batch['quiet'] = dict(status='excluded' if reasons else 'accepted',
                                  reasons=list(dict.fromkeys(reasons)), samples=samples)
            batch['memory'] = dict(peak_process_rss_bytes=server_peak_rss(server.proc.pid),
                                   sampled_peak_memory_bytes=server.run.peak or None,
                                   min_available_bytes=server.run.low)
            if error:
                raise error
            start += size
            save(path, report)
            _paired(out, prepared, legs)
        report['status'] = 'complete'
    except BaseException as exc:
        report.update(status='failed', error=dict(code=getattr(exc, 'code', type(exc).__name__), message=str(exc)))
        raise
    finally:
        save(path, report)
        _paired(out, prepared, legs)
    return report
