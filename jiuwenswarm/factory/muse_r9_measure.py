"""Run the approved R9 comparison in a single capped, factory-queued server load."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import time

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.lab_mailbox import canonical
from jiuwenswarm.factory.lab_manager import LabManager
from jiuwenswarm.factory.store import ScopeDenied
from scripts.factory import lab_v4_fast as lab, lab_v4_quiet as quiet
from scripts.factory import r8_bench_cells, r8_bench_score, r8_final_benchmark, r8_derive_p_ttft, r9_prefix_check
from jiuwenswarm.factory.ccs.paired_accuracy import paired

RECIPE = 'muse_r9_measure'
TASK = 'muse-2bit-demo-r9'
ARM = 'AQBC'
CONTROL = 'AQB-control'
PROMPTS = ('p512', 'p2048')
REPEATS = (0, 1, 2)
REF_KEYS = ('proposal', 'aqb_speed', 'aqb_ttft', 'aqb_mmlu')
FORMAT = 'factory.muse-r9-measurements/1'
MMLU_FORMAT = 'muse-r9-mmlu/2'
MMLU_IDENTITY = dict(mode='ordered-letter-identity', question_count=25, min_matches=24,
                     source_question_count=250, reference_correct=229, zero_external_reuse=True)
DEVICE_BUDGET = 110000
TASK_LOG = re.compile(r'\bid\s+(\d+)\s*\|\s*task\s+(\d+)\s*\|\s*(.*)')
NEW_PROMPT = re.compile(r'\bnew prompt, .*?task\.n_tokens = (\d+)')
CACHED = re.compile(r'^cached n_tokens = (\d+), memory_seq_rm \[(\d+), end\)')


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def pinned(pin):
    path = Path(pin['path'])
    if not path.is_absolute() or digest(path) != pin['sha256']:
        raise ValueError(f'Reference digest mismatch: {path}')
    return path


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def admit(store, task_id, args, node_id):
    """Resolve all launch inputs from the immutable, sent delivery and operator evidence."""
    from jiuwenswarm.factory.scheduler import operator_inputs

    capped_run._fields(args, {'request_id'})
    task = store.get_task(task_id)
    if task.get('contract_id') != TASK or node_id != 'measure_engine':
        raise ScopeDenied('Only the R9 measure_engine node can use this capped recipe')
    limits = capped_run._resources(task)
    if (limits.get('memory_cap') != capped_run.CAP or limits.get('device_budget_mib') != DEVICE_BUDGET
            or limits.get('need_available_gib') != capped_run.NEED_GIB):
        raise ScopeDenied('R9 requires the pinned memory and device grant')
    if RECIPE not in (task.get('constraints') or {}).get('approved_capped_recipes', {}).get(node_id, []):
        raise ScopeDenied('The R9 measure_engine recipe lacks an explicit host grant')
    request_id = args['request_id']
    if not isinstance(request_id, str) or not re.fullmatch(r'labreq-[0-9a-f]{24}', request_id):
        raise ValueError('R9 measurement requires a sent lab request ID')
    sent = store._get('observations', task_id, f'{request_id}:request')
    package = LabManager(store)._package_for(task_id, request_id)
    if (sent['kind'] != 'lab_request' or sent['values']['package_id'] != package['package_id']
            or package['origin'].get('node_id') != 'deliver_to_lab' or package['contract']['id'] != TASK):
        raise ScopeDenied('R9 measurement requires its deliver_to_lab package')
    contract = package['contract']['document']
    accuracy = contract.get('extensions', {}).get('muse.r9-protocol', {}).get('accuracy')
    if contract.get('version') != 10 or accuracy != MMLU_IDENTITY:
        raise ScopeDenied('R9 measurement requires the delivered amendment 004 MMLU identity protocol')
    subjects = package['subjects']
    subject = subjects['factory_stage']
    artifact_id = subject['payload']['artifact_id']
    raw_stage = store.artifact_bytes(task_id, artifact_id)
    if hashlib.sha256(raw_stage).hexdigest() != subject['payload']['sha256']:
        raise ValueError('Factory-stage bytes differ from the sealed package')
    stage = json.loads(raw_stage)
    images = [s for s in subjects.values() if s['kind'] == 'container_image'
              and s.get('verification', {}).get('verified') is True
              and s['identity'].get('id') == stage['image_id']]
    if (len(images) != 1 or stage.get('status') != 'passed'
            or stage.get('format') != 'factory.r9-factory-stage/1'):
        raise ValueError('Delivery lacks one verified configured image and a passing factory stage')
    ref_pin = operator_inputs(store, task_id)['r9_reference']
    reference = read(pinned(ref_pin))
    if set(reference) != {*REF_KEYS, 'output_dir'}:
        raise ValueError('R9 reference requires the four R8 pins and its lab output directory')
    root = Path(reference['output_dir'])
    if not root.is_absolute() or root.parent.name != 'r9-aqbc' or root.name != 'measure-engine':
        raise ValueError('R9 measurement output must be an absolute lab/r9-aqbc/measure-engine path')
    return dict(recipe=RECIPE, request_id=request_id, package_id=package['package_id'], stage=stage,
                factory_stage_artifact_id=artifact_id, reference=reference, reference_pin=ref_pin)


def references(reference, stage):
    """Check the exact R8 inputs used for speed context and paired MMLU scoring."""
    refs = {key: read(pinned(reference[key])) for key in REF_KEYS}
    proposal = refs['proposal']
    proposal['speed_lengths'] = list(PROMPTS)
    prepared = r8_bench_score.prepare(proposal)
    prompts = r8_bench_cells.read_prompts(proposal)
    expected_engine = proposal['engine']
    expected_pack = proposal['pack_pins']['MIXED_2BIT']
    if (stage['executable_sha256'] != expected_engine['required_image_executable_sha256']
            or stage['pack'] != expected_pack or stage['image_id'] == expected_engine['required_verified_image_id']):
        raise ValueError('R9 image must preserve the exact R8 executable and pack and have a distinct image ID')
    checked_manifest = read(pinned(dict(path=expected_pack['manifest'], sha256=expected_pack['manifest_sha256'])))
    files = checked_manifest['files']
    pack_root = Path(expected_pack['manifest']).parent
    if (len(files) != expected_pack['shard_count'] or sum(f['bytes'] for f in files) != expected_pack['bytes']
            or files[0]['sha256'] != expected_pack['first_shard_sha256']
            or Path(expected_pack['first_shard']).resolve() != (pack_root / files[0]['name']).resolve()
            or any(Path(f['name']).name != f['name'] or (pack_root / f['name']).stat().st_size != f['bytes']
                   for f in files)):
        raise ValueError('The staged pack does not match its accepted shard manifest and size census')
    ref_mmlu = refs['aqb_mmlu']
    ids = prepared.source['question_ids_in_order']
    ref_server = ref_mmlu['server']
    expected = (expected_engine['required_verified_image_id'], stage['executable_sha256'],
                expected_pack['manifest_sha256'])
    if (ref_mmlu['status'] != 'complete' or ref_mmlu['leg'] != '8' or ref_mmlu['source'] != prepared.source
            or ref_mmlu['request'] != dict(path='/completion', **r8_bench_score.REQUEST)
            or list(ref_mmlu['rows']) != ids or len(ids) != MMLU_IDENTITY['source_question_count']
            or sum(row['correct'] for row in ref_mmlu['rows'].values()) != MMLU_IDENTITY['reference_correct']
            or (ref_server['image_id'], ref_server['llama_server_sha256'],
                ref_server['pack_manifest_sha256']) != expected):
        raise ValueError('AQB MMLU reference is incomplete or belongs to another benchmark')
    for question in prepared.questions:
        row = ref_mmlu['rows'][question['id']]
        if (row['prompt_sha256'], row['answer']) != (paired.sha(question['prompt']), question['answer']):
            raise ValueError(f'MMLU reference prompt or answer mismatch: {question["id"]}')
    speed = refs['aqb_speed']
    ttft = refs['aqb_ttft']
    if (speed['status'] != 'completed' or speed['leg']['id'] != '3' or ttft['source_sha256'] != reference['aqb_speed']['sha256']
            or (speed['identity']['image_id'], speed['identity']['llama_server_sha256'],
                speed['identity']['pack_manifest_sha256']) != expected):
        raise ValueError('AQB speed reference differs from R8 load 3')
    leg = speed['leg']
    launch = stage['launch_config']
    args = [*proposal['base_args'], '-c', str(leg['ctx']), '-np', str(leg['np']), '-b', str(leg['batch']),
            '-ub', str(leg['ubatch']), '--moe-cache-mib', str(leg['moe_cache_mib']),
            '--swa-full', '--ctx-checkpoints', '32']
    if (launch != dict(format='factory.r9-launch/1', args=args, request={'cache_prompt': True})
            or hashlib.sha256(canonical(launch).encode()).hexdigest() != stage['launch_config_sha256']
            or leg['np'] != 1):
        raise ValueError('The staged launch config differs from AQB plus the approved prefix-store changes')
    speed_rows = []
    for row in ttft['rows']:
        if row['request'] not in PROMPTS or row['repeat'] not in REPEATS:
            continue
        pointer = row['source_pointer']
        original = speed['rows'][int(pointer.removeprefix('/rows/'))]
        speed_rows.append(dict(request=row['request'], state=row['state'], repeat=row['repeat'],
                               quiet_status=row['quiet_status'], client_ttft_ms=row['derived_ttft_ms'],
                               decode_tokens_per_second=original['decode_tokens_per_second'],
                               request_total_ms=original['request_total_ms'], source_pointer=pointer))
    return prepared, prompts, leg, speed_rows, ref_mmlu


def verify_image(stage, directory):
    image_id = stage['image_id']
    details, = json.loads(subprocess.run(['docker', 'image', 'inspect', image_id], check=True,
                                        capture_output=True, text=True, timeout=45).stdout)
    launch = stage['launch_config']
    config = details['Config']
    config_values = [value.partition('=')[2] for value in config.get('Env', [])
                     if value.startswith('FACTORY_LAUNCH_CONFIG=')]
    if (details['Id'] != image_id or config_values != [canonical(launch)]
            or config['Cmd'] != launch['args']):
        raise ValueError('Installed image launch configuration differs from the sealed factory stage')
    binary_dir, observed = lab.from_image('r9-aqbc',
        dict(image=image_id, expect_image_id=image_id, expect_sha256=stage['executable_sha256']), directory)
    observed.update(launch_config=launch, launch_config_sha256=stage['launch_config_sha256'])
    return Path(binary_dir) / 'llama-server', observed


def first_cached_tasks(raw):
    """Return the first cache count after each request starts, with exact supporting log lines."""
    tasks = {}
    for line in raw.decode('utf-8', errors='replace').splitlines():
        match = TASK_LOG.search(line)
        if not match:
            continue
        slot_id, task_id = map(int, match.groups()[:2])
        message = match[3]
        key = (slot_id, task_id)
        if message.startswith('processing task, '):
            tasks[key] = dict(slot_id=slot_id, task_id=task_id, start=line)
        if key not in tasks:
            continue
        task = tasks[key]
        prompt = NEW_PROMPT.search(message)
        if prompt:
            task.update(prompt_tokens=int(prompt[1]), prompt_line=line)
        cached = CACHED.match(message)
        if cached and 'prompt_tokens' in task and 'cached_tokens' not in task:
            if cached[1] != cached[2]:
                raise ValueError('Server cache count disagrees with the memory erase start')
            task.update(cached_tokens=int(cached[1]), cache_line=line)
        if message.startswith(('restored context checkpoint', 'restoring context checkpoint')):
            task.setdefault('checkpoint_lines', []).append(line)
        if message.startswith('stop processing:'):
            task['end'] = line
    return list(tasks.values())


def speed_schedule():
    """Alternate request order across lengths and repeats to reduce order effects."""
    rows = []
    for length_index, name in enumerate(PROMPTS):
        for repeat in REPEATS:
            order = (ARM, CONTROL) if (length_index + repeat) % 2 == 0 else (CONTROL, ARM)
            for arm in order:
                rows.append(dict(arm=arm, request=name, repeat=repeat, role='speed',
                                 state='warm' if repeat else 'cold', evict_pages=repeat == 0))
    for length_index, name in enumerate(PROMPTS):
        order = (CONTROL, ARM) if length_index == 0 else (ARM, CONTROL)
        for arm in order:
            for role in ('followup_seed', 'followup'):
                rows.append(dict(arm=arm, request=name, repeat=0, role=role,
                                 state='follow-up', evict_pages=False))
    return rows


def workload(server, proposal, prompts):
    counts = r8_bench_cells.tokenize(server, proposal, prompts)
    cases = {(name, 'speed'): (prompt, counts[name]) for name, prompt in prompts.items()}
    for name, prompt in prompts.items():
        for role, text in zip(('followup_seed', 'followup'), r9_prefix_check.questions(prompt)):
            reply = server.post(dict(content=text, add_special=True, parse_special=True), timeout=60, path='/tokenize')
            tokens = reply['tokens']
            if (not all(type(token) is int for token in tokens) or not 30 <= len(tokens) - counts[name] <= 60):
                raise ValueError(f'{name}: follow-up is outside the planned document/question token range')
            cases[name, role] = (text, len(tokens))
    return cases


def quiet_request(monitor, call):
    """Use the R8 quiet measurements around one request or score batch."""
    start, _ = monitor.wait('start', 'during', lab.log)
    error = result = None
    try:
        result = call()
    except BaseException as exc:
        error = exc
    end = monitor.mark('end', 'between_rows')
    samples = monitor.samples[start:end + 1]
    reasons = quiet.evidence_issues(samples, monitor.limits)
    if error:
        reasons.append(str(error) or type(error).__name__)
    return result, dict(status='excluded' if reasons else 'accepted', reasons=reasons, samples=samples), error


def read_log(server, start):
    with server.log.open('rb') as handle:
        handle.seek(start)
        return handle.read()


def run_speed(server, monitor, out, proposal, prompts, stage, speed_rows):
    path = out / 'speed.json'
    report = dict(format='muse-r9-speed/1', status='running', quiet_policy=monitor.limits, rows=[],
                  reference_aqb=speed_rows, measurements={'n_predict': 32, 'seed': 1, 'temperature': 0,
                  'ignore_eos': True}, cold_definition='Pinned pack files advised DONTNEED before each cold cell',
                  first_request_policy='Disable prompt reuse for both first requests and both follow-up seeds; '
                  'the first cached token count must be zero. Only the AQBC follow-up enables reuse.',
                  pack_page_eviction='posix_fadvise advisory; cache residency is not measured')
    cases = workload(server, proposal, prompts)
    lab.save(path, report)
    try:
        for cell in speed_schedule():
            role, name = cell['role'], cell['request']
            prompt, tokens = cases[name, role]
            # cache_prompt=False starts from token zero, while the completed
            # prompt remains in the slot for the explicitly cache-on follow-up.
            cache = (stage['launch_config']['request']['cache_prompt']
                     and cell['arm'] == ARM and role == 'followup')
            row = dict(cell, cache_prompt=cache, n_predict=32, tokenized_prompt_tokens=tokens,
                       prompt_sha256=paired.sha(prompt), image_id=stage['image_id'],
                       pack_manifest_sha256=stage['pack']['manifest_sha256'])
            report['rows'].append(row)
            lab.save(path, report)
            if cell['evict_pages']:
                lab.evict(stage['pack']['first_shard'])
            offset = server.log.stat().st_size
            metrics, evidence, error = quiet_request(monitor, lambda: lab.request(
                server, prompt, 32, benchmark=True, cache_prompt=cache, retain_output=True))
            row['quiet'] = evidence
            row['server_log_start'] = offset
            raw = read_log(server, offset)
            row['server_log_end'] = offset + len(raw)
            observations = first_cached_tasks(raw)
            if len(observations) == 1:
                row['reuse'] = observations[0]
            if metrics:
                row.update(metrics)
                clock = r8_derive_p_ttft.derive(row)
                row.update({key: clock[key] for key in (
                    'derived_ttft_ms', 'direct_client_ttft_ms', 'derived_minus_direct_ms',
                    'recorded_first_progress_arrival_ms', 'server_elapsed_at_first_progress_ms',
                    'server_elapsed_at_first_sampled_token_ms')})
            filename = f'{name}-{role}-{cell["state"]}-{cell["repeat"]}-{cell["arm"].lower()}.json'
            lab.save(out / filename, row)
            lab.save(path, report)
            server.run.log(f'{cell["arm"]} {name} {cell["state"]} {role} {cell["repeat"]}: {evidence["status"]}')
            if error:
                raise error
        report['status'] = 'complete'
    finally:
        lab.save(path, report)
        sidecar = ('arm', 'request', 'state', 'repeat', 'role', 'ttft_method', 'client_ttft_ms',
                   'direct_client_ttft_ms', 'derived_ttft_ms', 'derived_minus_direct_ms', 'stream_arrivals',
                   'recorded_first_progress_arrival_ms', 'server_elapsed_at_first_progress_ms',
                   'server_elapsed_at_first_sampled_token_ms')
        rows = [dict(source_pointer=f'/rows/{index}', **{key: row[key] for key in sidecar if key in row})
                for index, row in enumerate(report['rows'])]
        lab.save(out / 'ttft.json', dict(format='muse-r9-client-ttft/1', source='speed.json',
                 formula='recorded_first_progress_arrival_ms + prompt_ms - first_prompt_progress.time_ms',
                 source_sha256=digest(path), rows=rows))
    return report


def mmlu_reference_summary(reference, sample_ids):
    rows = reference['rows']
    return dict(settings=reference['server'], rows={qid: rows[qid] for qid in sample_ids},
                source_question_count=len(rows), correct=sum(row['correct'] for row in rows.values()))


def accuracy_identity(report, tasks):
    reference = report['reference']
    rows = report['rows']
    ids = list(reference['rows'])
    if list(rows) != ids or len(ids) != MMLU_IDENTITY['question_count']:
        raise ValueError('MMLU identity requires exactly the first 25 ordered responses')

    # With zero letter probability the legacy argmax defaults to A. Such a
    # response did not pick a letter, so it cannot support identity.
    def matched(qid):
        row = rows[qid]
        return (row['pick'] == reference['rows'][qid]['pick']
                and any(token.strip() == row['pick'] for token, _ in row['top_logprobs']))

    letters = sum(matched(qid) for qid in ids)
    independent = sum(task.get('cached_tokens') == 0 and task.get('slot_id') == 0 and bool(task.get('end'))
                      for task in tasks)
    total = reference['source_question_count']
    correct = reference['correct']
    if (total != MMLU_IDENTITY['source_question_count'] or correct != MMLU_IDENTITY['reference_correct']):
        raise ValueError('Pinned AQB reference does not establish its declared 229/250 score')
    minimum = MMLU_IDENTITY['min_matches']
    accepted = (letters >= minimum and len(tasks) == independent == len(ids)
                and len({task['task_id'] for task in tasks}) == len(ids))
    return dict(mode='identity_check', status='passed' if accepted else 'refused',
                question_count=len(ids), matched_letters=letters, zero_external_reuse=independent,
                min_matches=minimum, source_question_count=total, reference_correct=correct,
                reference_accuracy=correct / total, inherited_correct=correct if accepted else None,
                inherited_accuracy=correct / total if accepted else None)


def score(server, monitor, prepared, reference, out, settings):
    path = out / 'mmlu.json'
    request = dict(path='/completion', **r8_bench_score.REQUEST)
    questions = prepared.questions[:MMLU_IDENTITY['question_count']]
    ids = [q['id'] for q in questions]
    report = dict(format=MMLU_FORMAT, status='running', request=request, settings=settings,
                  source=prepared.source, protocol=MMLU_IDENTITY, quiet_policy=monitor.limits, rows={},
                  reference=mmlu_reference_summary(reference, ids))
    lab.save(path, report)
    try:
        offset = server.log.stat().st_size
        t0 = time.monotonic()
        rows, evidence, error = quiet_request(
            monitor, lambda: r8_bench_score._scores(server, questions, retain_distribution=True))
        raw = read_log(server, offset)
        tasks = first_cached_tasks(raw)
        report['batch'] = dict(question_ids=ids, quiet=evidence, server_log_start=offset,
                               server_log_end=offset + len(raw), cache_evidence=tasks,
                               elapsed_including_admission_seconds=round(time.monotonic() - t0, 3))
        if rows:
            report['rows'] = rows
        if error:
            raise error
        report['comparison'] = accuracy_identity(report, tasks)
        report['status'] = 'complete'
        result = report['comparison']
        server.run.log(f'MMLU identity {result["status"]}: {result["matched_letters"]}/25 letters matched, '
                       f'{result["zero_external_reuse"]}/25 started without cached tokens')
    except BaseException:
        report['status'] = 'stopped'
        raise
    finally:
        lab.save(path, report)
    return report


def execute(run):
    from jiuwenswarm.factory.muse_r9_runtime import OWNER_006, verify_runtime_stage

    req = run.req
    # Preserve the R8/Phase 0b resident-server watchdog policy.
    run.task = dict(run.task, resources=dict(run.task['resources'], floor_gib=8))
    stage = req['stage']
    reference = req['reference']
    if reference != read(pinned(req['reference_pin'])):
        raise ValueError('Operator reference changed since admission')
    prepared, prompts, leg, reference_speed, reference_mmlu = references(reference, stage)
    out = Path(reference['output_dir'])
    # Exclusive even across graph home directories or retries. A reserved load is
    # never dispatched again, including after an interruption or a memory stop.
    out.mkdir(mode=0o750, parents=True, exist_ok=False)
    load_path = out / 'load.json'
    record = dict(format='muse-r9-load/1', status='admitting', load_id=run.run_id,
                  request_id=req['request_id'], package_id=req['package_id'], started_utc=now(),
                  identity=stage, reference={key: reference[key] for key in REF_KEYS},
                  memory_cap=run.cap, swap_cap_bytes=0, device_budget_mib=DEVICE_BUDGET)
    lab.save(load_path, record)
    limits = quiet.policy(quiet.SHARED)
    server = None
    try:
        with TemporaryDirectory(dir=out, prefix='image-') as scratch:
            executable, image = verify_image(stage, Path(scratch))
            record['image'] = image
            with quiet.Monitor(limits, slots=1, stop_on_gate=True) as monitor:
                try:
                    monitor.wait('arm_start', 'loading', lab.log)
                    record['gate'] = run.gate()
                    lab.evict(stage['pack']['first_shard'])
                    monitor.wait('pre_launch', 'loading', lab.log)
                    record['gate_before_load'] = run.gate()
                    record['status'] = 'launch_reserved'
                    lab.save(load_path, record)
                    server = capped_run.Server(run, str(executable), stage['pack']['first_shard'],
                        stage['launch_config']['args'], capped_run.user_bus_env(), 'server.log', log_path=out / 'server.log')
                    monitor.server = server
                    monitor.mark('ready', 'between_rows')
                    settings = r8_final_benchmark.validate_ready(server, leg)
                    if sum(settings['device_mib'].values()) > DEVICE_BUDGET:
                        raise ValueError('Observed device and host compute buffers exceed the GB10 budget')
                    raw = server.log.read_text(errors='replace')
                    actual_slots = re.search(r'\bn_seq_max\s*=\s*(\d+)', raw)
                    if (not actual_slots or actual_slots[1] != '1'
                            or 'using full-size SWA cache' not in raw
                            or not re.search(r'context checkpoints enabled, max = 32\b', raw)):
                        raise ValueError('Server log did not confirm one slot, full SWA, and 32 checkpoints')
                    record.update(status='loaded', argv=server.argv, pid=server.proc.pid, load_seconds=server.ready_s,
                                  placement=server.placement, observed=dict(settings, n_seq_max=1))
                    lab.save(load_path, record)
                    run_speed(server, monitor, out, prepared.proposal, prompts, stage, reference_speed)
                    score(server, monitor, prepared, reference_mmlu, out,
                          dict(record['observed'], mode='sequential_on_one_slot',
                               requests='first 25 ordered questions queued on one slot'))
                    record['status'] = 'complete'
                finally:
                    if server:
                        record.update(sampled_peak_memory_bytes=run.peak or None,
                                      peak_process_rss_bytes=lab.server_peak_rss(server.proc.pid),
                                      min_available_bytes=run.low)
                        server.close()
                        monitor.server = None
                        record['server_closed'] = server.proc.poll() is not None
                    monitor.mark('arm_end')
                    lab.save(out / 'admission.json',
                             [sample for sample in monitor.samples if sample['phase'] not in ('during', 'end')])
    except (Exception, KeyboardInterrupt, SystemExit) as error:
        record.update(status='stopped', error=dict(code=getattr(error, 'code', type(error).__name__),
                      message=str(error)))
    record['ended_utc'] = now()
    lab.save(load_path, record)
    files = {path.name: digest(path) for path in sorted(out.glob('*')) if path.is_file()}
    result = dict(format=FORMAT, root=str(out), files=files, identity=stage, load_id=run.run_id,
                  request_id=req['request_id'], status=record['status'])
    lab.save(out / 'runtime.json', verify_runtime_stage(result, policy=OWNER_006))
    lab.save(out / 'measurements.json', result)
    run.files.update({path.name: path for path in out.iterdir() if path.is_file()})
    return result
