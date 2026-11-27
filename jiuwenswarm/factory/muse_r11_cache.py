"""Independent capped acquisition of Run 4 cache evidence on the target."""
from pathlib import Path
import struct

from . import capped_run
from .muse_r9_measure import digest, read, verify_image, quiet_request, now, first_cached_tasks, read_log
from .store import ScopeDenied, Store
from scripts.factory import lab_v4_fast as lab, lab_v4_quiet as quiet, lab_warmup as w2
from scripts.factory import r8_bench_cells, r8_final_benchmark, r9_prefix_check
from scripts.factory.warmup_w1 import document_shell, fit_notebook

ROOT = Path.home() / 'muse-demo'
TASK = 'muse-r11-independent-lab'
RECIPE = 'muse_r11_cache'
PARENT = 'cc7332b247770208f3c6e3808d062b11a6c7686c0c7e7c82d99345902f9c69c0'
OVERLAY = '2ab64f3e75d09f5f94aa4e4e3714b79b9ee9f5e3ad7980860f57837d2e0bd7bc'
OUT = ROOT/'lab/r11-aqbce'
PROFILE_LIB = ROOT/'r11/instrumentation/libllama.so.1'


def admit(store, task_id, args, node_id):
    capped_run._fields(args, {'arm'})
    task = store.get_task(task_id)
    arm = args['arm']
    if (task_id != TASK or Path(store.home).resolve() != ROOT/'r11/lab-home' or node_id
            or task['constraints'].get('attempt_limits') != {'model_run': 3}
            or task['resources'].get('memory_cap') != '96G'
            or task['resources'].get('device_budget_mib') != 110000):
        raise ScopeDenied('This recipe requires the independent Run 4 target lab grant.')
    if arm != 'profile':
        raise ScopeDenied('Candidate measurements require the sealed build and delivery.')
    from .muse_r11_gate import graph, check_for
    native_home = ROOT/'r11/graph'
    if not (native_home/'factory.sqlite').is_file():
        raise ScopeDenied('Run 4 has no admitted graph')
    native = Store(native_home)
    try:
        factory_id = 'muse-2bit-demo-r11'
        native_task = native.get_task(factory_id)
        nodes = graph(native, factory_id)
        if (native_task['constraints']['model_runs'] is not False or nodes['pin_inputs']['state'] != 'done'
                or nodes['check_seeding_premise']['state'] in {'done', 'failed', 'superseded', 'cancelled'}):
            raise ScopeDenied('A profile needs the pinned live AQBC inputs and an outstanding premise')
        check_for(native, factory_id, nodes, 'pin_inputs', 'pinned_inputs')
    finally:
        native.close()
    if digest(ROOT/'r10/parent-reference.json') != PARENT or digest(PROFILE_LIB) != OVERLAY:
        raise ValueError('Pinned AQBC parent or profiling instrument differs')
    return dict(recipe=RECIPE, arm=arm, parent_sha256=PARENT, profiling_library_sha256=OVERLAY)


def header_end(path):
    with path.open('rb') as f:
        magic, _, _, groups = struct.unpack('<4sIII', f.read(16))
        if magic != b'MCT2' or not 1 <= groups <= 256:
            raise ValueError('Missing native profiling header')
        for _ in range(groups):
            _, _, layers = struct.unpack('<III', f.read(12))
            f.seek(4*layers + 40, 1)
            tensors, = struct.unpack('<I', f.read(4))
            f.seek(8*tensors, 1)
        return f.tell()


def acquire(server, out, monitor):
    proposal = read(ROOT/'bench/proposed-engine-benchmark.json')
    proposal['speed_lengths'] = ['p512', 'p2048']
    prompts = r8_bench_cells.read_prompts(proposal)
    counts = r8_bench_cells.tokenize(server, proposal, prompts)
    trace = out/'trace.mct'
    requests = [dict(id='startup', cell='startup', cohort='warmup',
                     trace_start=header_end(trace), trace_end=trace.stat().st_size)]
    measurements = []
    head, tail = document_shell(prompts['p512'])
    def tokenize(text):
        return w2._tokenize(server, text)
    def notebook(words, n):
        return fit_notebook(head, tail, words, tokenize, n)[0]
    first = notebook('granite marble basalt slate quartz sandstone chalk limestone gneiss crystal', counts['p512'])
    calibration = [notebook(words, counts[size]) for words, size in [
        ('valley ridge beach island orchard forest desert meadow river ocean shore', 'p512'),
        ('pitch melody scale flute piano chorus octave rhythm tempo score brass', 'p2048')]]
    questions = {n: r9_prefix_check.questions(doc) for n, doc in prompts.items()}
    measured = [first, *prompts.values(), *(q for pair in questions.values() for q in pair)]
    if set(measured) & set(calibration) or len(set(calibration)) != len(calibration):
        raise ValueError('Calibration overlaps held-out prompts')
    def record(name, cell, cohort, text, cache):
        ids = tokenize(text)
        start = trace.stat().st_size
        log_start = server.log.stat().st_size
        row, evidence, error = quiet_request(monitor, lambda: lab.request(
            server, text, 32, benchmark=True, cache_prompt=cache, retain_output=True, retain_tokens=True))
        if error:
            raise error
        tasks = first_cached_tasks(read_log(server, log_start))
        if len(tasks) != 1 or row['generated_tokens'] != 32:
            raise ValueError('Incomplete request evidence')
        item = dict(id=name, cell=cell, cohort=cohort, prompt_sha256=w2._sha(text),
                    token_ids_sha256=w2._ids_sha(ids), prompt_n=len(ids), generated_n=row['generated_tokens'],
                    cache_prompt=cache, trace_start=start, trace_end=trace.stat().st_size)
        requests.append(item)
        measurements.append(dict(**item, **row, quiet=evidence, server_task=tasks[0]))
        lab.save(out/'speed.json', dict(rows=measurements))
        server.run.log('sealed request', name)
    record('first-512', 'first-request', 'heldout', first, True)
    # W2 owns the requests; record exact trace offsets around each completion on this same server.
    native_post = server.post
    def observed_post(body, *args, **kwargs):
        if kwargs.get('path', '/completion') != '/completion':
            return native_post(body, *args, **kwargs)
        start = trace.stat().st_size
        result = native_post(body, *args, **kwargs)
        text = body['prompt']
        requests.append(dict(id=f'w2-{len(requests)}', cell='w2', cohort='warmup',
                             trace_start=start, trace_end=trace.stat().st_size,
                             prompt_sha256=w2._sha(text), prompt_n=result['prompt_tokens'],
                             generated_n=result['generated_tokens'], cache_prompt=body['cache_prompt']))
        return result
    server.post = observed_post
    try:
        w2.run(server, monitor, out, template=prompts['p512'], measured_prompts=measured+calibration)
    finally:
        server.post = native_post
    for name, text in prompts.items():
        record(f'warm-{name}', 'warm-'+name[1:], 'heldout', text, True)
    for name, (seed, follow) in questions.items():
        record('prime-'+name, 'prime', 'warmup', seed, True)
        record('follow-'+name, 'follow-up', 'heldout', follow, True)
    for i, text in enumerate(calibration):
        record(f'calibration-{i+1}', 'calibration', 'calibration', text, False)
    return requests


def execute(run):
    admit(run.store, run.task_id, {'arm': run.req['arm']}, None)
    parent = read(ROOT/'r10/parent-reference.json')
    pin = parent['evidence']['factory_verification']
    stage_path = ROOT/pin['path']
    if digest(stage_path) != pin['sha256']:
        raise ValueError('Released AQBC delivery changed')
    stage = read(stage_path)
    load_pin = parent['evidence']['lab_load']
    if digest(ROOT/load_pin['path']) != load_pin['sha256']:
        raise ValueError('Parent lab receipt changed')
    delivered = read(ROOT/load_pin['path'])['identity']
    if (delivered['image_id'] != stage['image_id'] or delivered['launch_config'] != stage['launch_config']
            or delivered['executable_sha256'] != stage['executable_sha256']):
        raise ValueError('Parent lab receipt differs from the native factory stage')
    pack = delivered['pack']
    if digest(pack['manifest']) != parent['pack_manifest_sha256']:
        raise ValueError('Parent pack manifest changed')
    scratch = ROOT/'r11/extracted'
    scratch.mkdir(exist_ok=True)
    binary, image = verify_image(stage, scratch)
    out = OUT/'profile'
    out.mkdir(exist_ok=False)
    trace = out/'trace.mct'
    record = dict(format='muse-r11-load/1', status='admitting', started_utc=now(),
                  load_id=run.run_id, image=image, pack=pack, memory_cap=run.cap, swap_cap_bytes=0,
                  device_budget_mib=110000, parent_sha256=PARENT, profiling_library_sha256=OVERLAY)
    save = lambda: lab.save(out/'load.json', record)
    save()
    env = dict(capped_run.user_bus_env(), LD_LIBRARY_PATH=str(PROFILE_LIB.parent)+':'+str(binary.parent),
               LLAMA_MOE_CACHE_TRACE=str(trace))
    with quiet.Monitor(quiet.policy(quiet.SHARED), slots=1, stop_on_gate=True) as monitor:
        server = None
        try:
            record['gate_before_load'] = run.gate()
            record['status'] = 'launch_reserved'
            save()
            server = capped_run.Server(run, str(binary), pack['first_shard'], stage['launch_config']['args'],
                                       env, 'server.log', log_path=out/'server.log')
            monitor.server = server
            observed = r8_final_benchmark.validate_ready(server, dict(role='AQBC',ctx=8192,batch=2048,
                                                                     ubatch=2048,moe_cache_mib=62464))
            if sum(observed['device_mib'].values()) > 110000:
                raise ValueError('Device-budget accounting exceeded 110000 MiB')
            record.update(status='loaded', load_seconds=server.ready_s, argv=server.argv,
                          placement=server.placement, observed=observed, pid=server.proc.pid)
            save()
            requests = acquire(server, out, monitor)
            record['status'] = 'complete'
        except BaseException as error:
            record.update(status='stopped', error=str(error))
            raise
        finally:
            if server:
                record.update(peak_process_rss_bytes=lab.server_peak_rss(server.proc.pid),
                              min_available_bytes=run.low, peak_memory_bytes=run.peak)
                server.close()
                record['server_closed'] = server.proc.poll() is not None
                monitor.server = None
            record['ended_utc'] = now()
            save()
    if trace.stat().st_size != requests[-1]['trace_end']:
        raise ValueError('Unattributed routing traffic after the last request')
    manifest = dict(format='factory.muse-seeding-profile/1', parent_sha256=PARENT,
                    trace_sha256=digest(trace), profiling_library_sha256=OVERLAY, requests=requests)
    lab.save(out/'manifest.json', manifest)
    run.files.update({p.name:p for p in out.iterdir() if p.is_file()})
    return dict(arm='profile', status='complete', manifest_sha256=digest(out/'manifest.json'))
