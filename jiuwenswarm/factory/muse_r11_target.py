"""Independent AQBC/AQBCE paired acquisition from the accepted Run 4 delivery."""
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
import threading
import time

from . import capped_run, muse_r11_gate as gate
from .contract import load_for_task
from .lab_mailbox import open_mailbox
from .lab_manager import LabManager
from .muse_r9_measure import digest, read, now, quiet_request, first_cached_tasks
from .store import ScopeDenied
from .views.activity import _snapshot_store
from scripts.factory import lab_v4_fast as lab, lab_v4_quiet as quiet, lab_warmup as w2
from scripts.factory import r8_final_benchmark

FACTORY_TASK = 'muse-2bit-demo-r11'
ARMS = ('AQBC', 'AQBCE')
CAP_BYTES = 96 << 30
RSS_RESERVE = 256 << 20
DEVICE_BUDGET = 110000
COUNTER_ENV = 'LLAMA_MOE_CACHE_COUNTERS'
PROFILE_PATH_ENV = 'LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH'
STARTUP_MARKER = 'muse_cache_startup'
COUNTER_MARKER = 'muse_cache_counters'
COUNTERS = (
    'graphs', 'demand_hits', 'demand_misses', 'demand_evictions', 'demand_seeded_hits', 'demand_seeded_evictions',
    'read_only_hits', 'read_only_misses', 'read_only_seeded_hits',
    'hit_bytes', 'host_bytes', 'prefill_hits', 'prefill_misses', 'decode_hits', 'decode_misses',
)
SEED_FIELDS = ('slots_admitted', 'slots_populated', 'charged_bytes', 'uploaded_bytes')
REQUESTS = 'request-receipts.json'
WARMUP = 'warmup-receipts.json'
STARTUP = 'startup-fill-receipts.json'
LOAD = 'load-receipts.json'
REPO = Path(__file__).resolve().parents[2]


def checked(condition, reason):
    if not condition:
        raise ValueError(reason)


def _bytes_sha(data):
    return hashlib.sha256(data).hexdigest()


def _identity(path):
    info = path.stat()
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size, mtime_ns=info.st_mtime_ns)


def _pack_identity(root, parent):
    load_pin = parent['evidence']['lab_load']
    checked(digest(root / load_pin['path']) == load_pin['sha256'], 'Released AQBC lab receipt changed')
    pack = read(root / load_pin['path'])['identity']['pack']
    manifest = Path(pack['manifest']).resolve(strict=True)
    checked(digest(manifest) == parent['pack_manifest_sha256'], 'Released AQBC pack manifest changed')
    files = []
    for row in read(manifest)['files']:
        name = row['name']
        checked(Path(name).name == name, 'Pack manifest has a nonlocal shard')
        path = manifest.parent / name
        file = _identity(path)
        checked(not path.is_symlink() and path.is_file() and file['bytes'] == row['bytes'],
                'Released AQBC pack shard does not match its manifest')
        files.append(dict(path=str(path), sha256=row['sha256'], **file))
    first = str(Path(pack['first_shard']).resolve(strict=True))
    checked(files and first in {f['path'] for f in files}, 'Pack first shard absent from pinned manifest')
    return dict(first_shard=first, manifest=str(manifest), manifest_sha256=parent['pack_manifest_sha256'],
                bytes=sum(row['bytes'] for row in files), files=files)


def _workload(contract, manifest):
    folder = REPO / 'ops/spark/prompts/muse'
    pins = read(folder / 'MANIFEST.json')
    expected = {
        'first_after_start': ('prompt_512', False, 512),
        'p512': ('prompt_512', False, 512),
        'p2048': ('prompt_2048', False, 2048),
        'p512_followup': ('prompt_512', True, 512),
        'p2048_followup': ('prompt_2048', True, 2048),
    }
    requests = {item['id']: item for item in contract['workload']['requests']}
    checked(set(requests) == set(expected) and len(requests) == len(contract['workload']['requests']),
            'Unexpected fixed request set')
    rendered = {}
    for key, (input_id, cache, length) in expected.items():
        item = requests[key]
        params = item['params']
        checked(item['input'] == input_id and item['expect']['rendered_prompt_tokens'] == length
                and params == dict(n_predict=32, temperature=0, seed=1, cache_prompt=cache,
                                   chat_template_kwargs=pins['template_parameters']), 'Unexpected fixed request policy')
        if input_id not in rendered:
            spec = contract['inputs'][input_id]
            raw_path = (REPO / spec['repo_path']).resolve()
            checked(raw_path == folder / f'{length}.txt', 'Unexpected raw fixed prompt path')
            raw = gate.read_pin(dict(path=raw_path, sha256=spec['sha256']), 1 << 20)
            checked(len(raw) == spec['size'] and spec['sha256'] == pins['files'][raw_path.name],
                    'Benchmark raw prompt differs from its manifest')
            rendered_name = f'{length}.rendered.txt'
            rendered_sha = pins['files'][rendered_name]
            rendered_text = gate.read_pin(dict(path=folder/rendered_name, sha256=rendered_sha), 1 << 20).decode()
            rows = [item for item in manifest['requests'] if item.get('cohort') == 'heldout'
                    and item.get('cell') == f'warm-{length}' and item.get('prompt_sha256') == rendered_sha]
            token_pins = {(item['prompt_n'], item['token_ids_sha256']) for item in rows}
            checked(len(token_pins) == 1, 'No unique profiled identity for the fixed rendered prompt')
            actual, token_sha = token_pins.pop()
            checked(type(actual) is int and actual in {length, length-1}
                    and re.fullmatch(r'[0-9a-f]{64}', token_sha), 'Profiled tokenizer identity is invalid')
            rendered[input_id] = dict(text=rendered_text, prompt_sha256=rendered_sha,
                                       token_ids_sha256=token_sha, actual=actual, nominal=length)
    calibration = [row['rendered_prompt'] for row in gate.calibration_requests(contract)]
    calibration_text = {_bytes_sha(text.encode()) for text in calibration}
    calibration_tokens = {row['token_ids_sha256'] for row in manifest['requests']
                          if row.get('cohort') == 'calibration'}
    checked(not calibration_text & {row['prompt_sha256'] for row in rendered.values()}
            and not calibration_tokens & {row['token_ids_sha256'] for row in rendered.values()},
            'Fixed target prompts overlap the amended calibration')
    return requests, rendered, calibration


def delivery(root):
    """Admit only native, checked delivery and the exact attached profile, without changing the graph."""
    home = root / 'r11/graph'
    with _snapshot_store(home) as store:
        task = store.get_task(FACTORY_TASK)
        contract = load_for_task(task, FACTORY_TASK)
        protocol = gate.policy(task)
        checked(contract['version'] == 12 and task['constraints']['model_runs'] is False
                and datetime.now().timestamp() < datetime.fromisoformat(protocol['target_deadline']).timestamp(),
                'Expected live amendments and unexpired independent target authority')
        nodes = gate.graph(store, FACTORY_TASK)
        checkpoint = task['constraints']['seeding_checkpoint']
        for name in ('pin_inputs', checkpoint['premise_node'], checkpoint['patch_node'], checkpoint['fixture_node'],
                     checkpoint['build_node'], checkpoint['delivery_node']):
            checked(nodes[name]['state'] == 'done', 'Independent target requires fully checked native delivery')
        premise = gate.require_eligible(store, FACTORY_TASK, checkpoint, nodes)
        artifact = gate.check_for(store, FACTORY_TASK, nodes, checkpoint['delivery_node'], 'lab_package')
        found = artifact['found']
        request_id = found['request_id']
        sent = store._get('observations', FACTORY_TASK, request_id + ':request')
        manager = LabManager(store, mailbox=open_mailbox(home=home), route='mailbox')
        package = manager._package_for(FACTORY_TASK, request_id)
        contract_sha = task['constraints']['contract_sha256']
        package_id = found['package_id']
        checked(sent['kind'] == 'lab_request' and sent['values']['package_id'] == package_id == package['package_id']
                and package['origin'] == dict(task_id=FACTORY_TASK, node_id=checkpoint['delivery_node'])
                and found['contract_sha256'] == package['contract']['sha256'] == contract_sha
                and package['contract']['document'] == contract, 'Sent package is not the native checked delivery')
        gate.verify_lab_task(store, task, checkpoint, checkpoint['delivery_node'], package['lab_task'])
        arms = package['lab_task']['arms']
        matched = package['subjects'][arms['AQBC']['subject']]
        build_id, image_id = matched['build_attempt_id'], matched['identity']['id']
        checked(matched.get('verification', {}).get('verified') is True,
                'Image is not verified against the native build receipt')
        image_check_id = gate.verify_image(store, task, dict(build_attempt_id=build_id, image_id=image_id))
        image_check = json.loads(store.artifact_bytes(FACTORY_TASK, image_check_id))
        attached = package['subjects']['seeding_profile']['payload']
        profile_sha = premise['profile_sha256']
        raw = store.artifact_bytes(FACTORY_TASK, attached['artifact_id'])
        checked(attached['sha256'] == profile_sha == _bytes_sha(raw) and len(raw) == attached['size']
                and raw == gate.profile_bytes(premise['profile']), 'Sealed profile bytes differ from the accepted premise')
        # Independently validate the exact bytes sent to the lab, not merely the graph attachment.
        path = manager.mailbox.file_path(request_id, attached)
        checked(path.read_bytes() == raw, 'Mailbox attachment differs from the checked seed profile')
        parent = gate.validate_parent(task)
        manifest_path = Path(protocol['profile_directory']) / 'manifest.json'
        manifest = json.loads(gate.read_pin(dict(path=manifest_path, sha256=premise['manifest_sha256'])))
        gate.verify_calibration_binding(contract, manifest)
        pack = _pack_identity(root, parent)
        workload = _workload(contract, manifest)
        launch = parent['launch_config']
        checked(contract['workload']['argv'] == ['-m', '{model}', *launch['args']],
                'Delivered launch parameters differ from pinned AQBC')
        identity = dict(package_id=package_id, request_id=request_id, delivery_check_id=artifact['obs_id'],
                        contract_sha256=contract_sha, build_attempt_id=build_id, image_id=image_id,
                        executable_sha256=image_check['executable_sha256'], image_check_id=image_check_id,
                        source_commit=image_check['source_commit'], pack=pack,
                        prefill_plan_sha256=parent['prefill_plan_sha256'], launch_config=launch,
                        launch_config_sha256=parent['launch_config_sha256'], profile_sha256=profile_sha,
                        profile_artifact_id=attached['artifact_id'], profile_manifest_sha256=premise['manifest_sha256'],
                        parent_image_id=parent['image_id'], parent_executable_sha256=parent['binary_sha256'],
                        profiling_library_sha256=manifest['profiling_library_sha256'])
        return identity, raw, {arm: arms[arm].get('env', {}) for arm in ARMS}, workload


def admit_order(store, task_id, arm, attempt_id=None):
    order = ['profile', *ARMS]
    index = order.index(arm)
    rows = store._db.execute("SELECT * FROM attempts WHERE task_id=? AND kind='model_run'", (task_id,))
    prior = [store._decode('attempts', row) for row in rows if row['attempt_id'] != attempt_id]
    by_arm = {row['request'].get('arm'): row for row in prior}
    if len(by_arm) != len(prior) or set(by_arm) != set(order[:index]):
        raise ScopeDenied('Each Run 4 load is admitted once, in order profile → AQBC → AQBCE')
    for previous in order[:index]:
        checked(by_arm[previous]['state'] == 'succeeded', f'Prior {previous} load did not complete successfully')
    return by_arm


def _extract_image(identity, out):
    # Every target arm extracts into a fresh private directory from the exact admitted image.
    root = out / 'image'
    root.mkdir(mode=0o700)
    image = identity['image_id']
    try:
        directory, _ = lab.from_image(identity['build_attempt_id'], dict(
            image=image, expect_image_id=image, expect_sha256=identity['executable_sha256']), root)
    except SystemExit as error:
        raise ValueError(str(error)) from error
    directory = Path(directory).resolve(strict=True)
    binary = directory / 'llama-server'
    checked(not binary.is_symlink() and binary.is_file() and binary.resolve().parent == directory,
            'Image executable is not an ordinary contained file')
    return binary, _image_hashes(directory)


def _image_hashes(directory):
    rows = {}
    for path in directory.iterdir():
        if path.name == 'llama-server' or '.so' in path.name:
            resolved = path.resolve(strict=True)
            checked(resolved.is_relative_to(directory) and resolved.is_file(), 'Image contains an escaping library')
            rows[path.name] = digest(resolved)
    checked('libllama.so.1' in rows and any(name.startswith('libggml-cuda.so') for name in rows),
            'Extracted image does not have its native GPU library set')
    return rows


def _library_delta(root, candidate, identity):
    """Compare the actual candidate library with the same path in the pinned parent image."""
    parent_image = identity['parent_image_id']
    checked(re.fullmatch(r'sha256:[0-9a-f]{64}', parent_image), 'Invalid parent image identifier')
    cached = root/'r11/extracted'/parent_image.removeprefix('sha256:')
    checked(digest(cached/'llama-server') == identity['parent_executable_sha256'],
            'Released parent executable does not match its pin')
    command = lambda args: subprocess.run(['docker', *args], check=True, capture_output=True, text=True, timeout=60)
    image = command(['image', 'inspect', '--format', '{{.Id}}', parent_image]).stdout.strip()
    checked(image == parent_image, 'Installed parent runtime image differs from its pinned identity')
    with tempfile.TemporaryDirectory(prefix='parent-library-', dir=candidate.parent.parent) as directory:
        library = Path(directory) / 'libllama.so.1'
        container = command(['create', parent_image]).stdout.strip()
        try:
            command(['cp', '-L', f'{container}:/opt/llamacpp/libllama.so.1', str(library)])
        finally:
            command(['rm', container])
        official = digest(library)
    checked(digest(cached/'libllama.so.1') == official, 'Cached parent runtime differs from its exact Docker image')
    raw = candidate.read_bytes()
    markers = [COUNTER_ENV, PROFILE_PATH_ENV, STARTUP_MARKER, COUNTER_MARKER]
    candidate_sha = _bytes_sha(raw)
    checked(candidate_sha not in {official, identity['profiling_library_sha256']}
            and all(marker.encode() in raw for marker in markers),
            'The candidate image lacks the native seeding/counter implementation or uses the profiling overlay')
    return dict(parent_image_id=parent_image, parent_library_sha256=official,
                candidate_library_sha256=candidate_sha, path_in_image='/opt/llamacpp/libllama.so.1',
                checked_marker_strings=markers)


def _stage_profile(directory, raw, sha):
    path = directory / 'run4-attachment' / 'seeding-profile.json'
    path.parent.mkdir(mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return path, _profile_identity(path, sha)


def _profile_identity(path, sha):
    checked(not path.is_symlink() and path.is_file() and path.stat().st_nlink == 1
            and stat.S_IMODE(path.stat().st_mode) == 0o400
            and digest(path) == sha, 'Staged seed profile changed')
    return dict(path=str(path), sha256=sha, mode='0400', **_identity(path))


def _environment(binary, delivered, profile):
    bus = {key: os.environ[key] for key in ('XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS') if key in os.environ}
    if delivered:
        checked(delivered == {'LLAMA_EXPERT_CACHE_NATIVE_PROFILE': '1',
                             PROFILE_PATH_ENV: '/opt/factory/r11/seeding-profile.json'},
                'Unexpected seeding environment in delivered arm')
    physical = dict(PATH=os.defpath, HOME=str(Path.home()), LANG='C',
                    LD_LIBRARY_PATH=str(binary.parent), **{COUNTER_ENV: '1'})
    physical.update(capped_run.user_bus_env())
    physical.update(bus)
    physical.update(delivered)
    if delivered:
        physical[PROFILE_PATH_ENV] = str(profile)
    return physical


def _native_lines(path, marker, offset=0):
    with path.open('rb') as stream:
        stream.seek(offset)
        while line := stream.readline():
            if not line.endswith(b'\n'):
                return
            start = stream.tell() - len(line)
            text = line.decode(errors='replace')
            if marker + ' ' in text:
                yield json.loads(text.split(marker + ' ', 1)[1]), dict(path='server.log', start=start, end=stream.tell())


def startup_receipt(path, arm):
    rows = list(_native_lines(path, STARTUP_MARKER))
    checked(len(rows) == 1, 'Expected exactly one native startup counter record')
    data, source = rows[0]
    enabled = arm == 'AQBCE'
    fields = lambda obj: all(type(obj.get(key)) is int and obj[key] >= 0 for key in SEED_FIELDS)
    checked(type(data.get('enabled')) is bool and data['enabled'] == enabled and fields(data)
            and type(data.get('seed_ms')) in (int, float) and math.isfinite(data['seed_ms'])
            and data['seed_ms'] >= 0 and isinstance(data.get('groups'), list), 'Invalid native startup counters')
    groups = data['groups']
    checked(all(isinstance(group, dict) and type(group.get('group')) is int and group['group'] >= 0
                and fields(group) and group['slots_populated'] <= group['slots_admitted'] for group in groups)
            and len({group['group'] for group in groups}) == len(groups)
            and all(sum(group[key] for group in groups) == data[key] for key in SEED_FIELDS),
            'Native startup groups do not reconcile to the recorded total')
    if enabled:
        checked(data['slots_admitted'] == data['slots_populated'] > 0 and data['uploaded_bytes'] > 0
                and data['charged_bytes'] > 0, 'The opt-in arm did not publish completed seed slots')
    else:
        checked(not any(data[key] for key in (*SEED_FIELDS, 'seed_ms')), 'Off arm recorded startup seeding')
    return dict(format='muse-r11-startup-fill/1', arm=arm, source=source, **data)


def device_budget(path, ready_end, ready):
    """Report the comparable device reservation inventory against the full native log."""
    with path.open('rb') as stream:
        stream.seek(ready_end)
        later = r8_final_benchmark.parse_log(stream.read().decode(errors='replace'))['device_mib']
    checked(not later, 'Post-ready memory reservations changed; comparable device peak cannot be reconstructed')
    categories = ready['device_mib']
    required = ('model', 'kv', 'compute', 'moe_cache')
    checked(all(key in categories for key in (*required, 'host_compute')), 'Native device allocation inventory is incomplete')
    peak = round(sum(categories[key] for key in required), 2)
    checked(peak <= DEVICE_BUDGET, 'Comparable device allocations exceed the approved budget')
    return dict(device_peak_mib=peak, device_peak_categories_mib=categories,
                device_budget_headroom_mib=round(DEVICE_BUDGET-peak, 2),
                device_peak_scope='Engine buffer reservations by comparable category, not GPU-wide occupation',
                device_peak_source=dict(path='server.log', start=0, ready_end=ready_end, end=path.stat().st_size))


def _validate_counters(values):
    checked(isinstance(values, dict) and all(type(values.get(key)) is int and values[key] >= 0 for key in COUNTERS),
            'Invalid native request cache counter fields')
    checked(values['prefill_hits'] + values['decode_hits'] == values['demand_hits'] + values['read_only_hits']
            and values['prefill_misses'] + values['decode_misses'] == values['demand_misses'] + values['read_only_misses'],
            'Native phase counters double count or omit lookups')
    checked(values['demand_seeded_hits'] <= values['demand_hits']
            and values['demand_seeded_evictions'] <= values['demand_evictions']
            and values['read_only_seeded_hits'] <= values['read_only_hits'], 'Native seeded-event counters exceed totals')
    return {key: values[key] for key in COUNTERS}


def _delta(before, after):
    previous, latest = _validate_counters(before), _validate_counters(after)
    difference = {key: latest[key] - previous[key] for key in COUNTERS}
    checked(all(value >= 0 for value in difference.values()), 'Cumulative native cache counters regressed')
    return difference


class CacheLog:
    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.latest = None
        self.source = None

    def read(self):
        """Advance only over complete native records written by the serial server."""
        for values, source in _native_lines(self.path, COUNTER_MARKER, self.offset):
            values = _validate_counters(values)
            if self.latest is not None:
                _delta(self.latest, values)
            self.latest, self.source = values, source
            self.offset = source['end']
        checked(self.latest is not None, 'No native baseline counters, including before first request')
        return self.latest, self.source


def _ratio(hit, miss):
    return hit / (hit + miss) if hit + miss else None


def request_schedule():
    yield 'first_after_start', 'first-request', 0, True
    for repeat in range(3):
        for length in (512, 2048):
            yield f'p{length}', f'warm-{length}', repeat, True
            yield f'p{length}', f'prime-{length}', repeat, False
            yield f'p{length}_followup', f'follow-up-{length}', repeat, True


def _safe_metrics(row):
    return all(type(row.get(key)) in (int, float) and math.isfinite(row[key]) and row[key] > 0
               for key in ('client_ttft_ms', 'request_total_ms', 'decode_tokens_per_second'))


def acquire(server, monitor, out, arm, workload, ticker):
    requested, prompts, calibration = workload
    for p in prompts.values():
        tokens = w2._tokenize(server, p['text'])
        checked(len(tokens) == p['actual'] and w2._ids_sha(tokens) == p['token_ids_sha256'],
                'Candidate tokenizer differs from the profiled AQBC identity')
    row_file = out / REQUESTS
    report = dict(format='muse-r11-requests/1', arm=arm, status='running', rows=[])
    try:
        for request, cell, repeat, measured in request_schedule():
            if cell == 'warm-512' and repeat == 0:
                try:
                    w2.run(server, monitor, out, template=prompts['prompt_512']['text'],
                           measured_prompts=[p['text'] for p in prompts.values()] + calibration)
                finally:
                    warm = out / w2.WARMUP_FILE
                    if warm.is_file():
                        warm.replace(out / WARMUP)
            p = prompts[requested[request]['input']]
            cache = requested[request]['params']['cache_prompt']
            before, before_source = ticker.read()
            log_start = server.log.stat().st_size
            identity = dict(id=f'{cell}-{repeat}', contract_request=request if measured else None, cell=cell,
                            repeat=repeat, measured_cell=measured, cache_prompt=cache,
                            nominal_prompt_tokens=p['nominal'], tokenized_prompt_tokens=p['actual'],
                            prompt_sha256=p['prompt_sha256'], token_ids_sha256=p['token_ids_sha256'],
                            n_predict=32, temperature=0, seed=1, ignore_eos=True)
            rendered = dict(identity, status='pending')
            report['rows'].append(rendered)
            lab.save(row_file, report)
            row, quiet_evidence, error = quiet_request(monitor, lambda: lab.request(
                server, p['text'], 32, benchmark=True, cache_prompt=cache, retain_output=True, retain_tokens=True))
            log_end = server.log.stat().st_size
            rendered.update(source=dict(path='server.log', start=log_start, end=log_end),
                            quiet=dict(quiet_evidence, status='recorded',
                                       observed_status=quiet_evidence['status'], included=bool(row)))
            if error:
                raise error
            with server.log.open('rb') as stream:
                stream.seek(log_start)
                tasks = first_cached_tasks(stream.read(log_end-log_start))
            checked(len(tasks) == 1 and tasks[0].get('slot_id') == 0 and tasks[0].get('end')
                    and tasks[0].get('prompt_tokens') == p['actual'], 'Native row does not match the requested tokenized prompt')
            cached = tasks[0].get('cached_tokens')
            checked(type(cached) is int and (0 < cached <= p['actual'] if cache else cached == 0),
                    'Native prompt reuse differs from the fixed request policy')
            output = row.get('generated_token_ids')
            checked(row['generated_tokens'] == 32 and isinstance(output, list) and len(output) == 32
                    and all(type(token) is int for token in output) and _safe_metrics(row),
                    'Target response has incomplete token identities or timing')
            after, after_source = ticker.read()
            checked(log_start <= after_source['start'] < after_source['end'] <= log_end,
                    'No native cache sample strictly inside the measured request')
            counters = _delta(before, after)
            if arm == 'AQBC':
                checked(not any(counters[key] for key in ('demand_seeded_hits', 'demand_seeded_evictions',
                                                          'read_only_seeded_hits')),
                        'The switch-off arm recorded seeded traffic')
            hits = counters['prefill_hits'] + counters['decode_hits']
            misses = counters['prefill_misses'] + counters['decode_misses']
            checked(hits + misses > 0, 'No expert lookup in a measured request')
            rendered.update(**row, server_task=tasks[0], output_token_ids=output,
                            output_token_ids_sha256=w2._ids_sha(output), cache_hit_rate=_ratio(hits, misses),
                            prefill_cache_hit_rate=_ratio(counters['prefill_hits'], counters['prefill_misses']),
                            decode_cache_hit_rate=_ratio(counters['decode_hits'], counters['decode_misses']),
                            cache_counters=counters, counters_before=before_source, counters_after=after_source,
                            status='complete')
            lab.save(row_file, report)
            server.run.log('sealed', arm, cell, repeat)
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='stopped', error=str(error))
        if report['rows'] and report['rows'][-1]['status'] == 'pending':
            report['rows'][-1]['status'] = 'stopped'
        raise
    finally:
        lab.save(row_file, report)


class MemoryWatchdog:
    """Enforce a pre-OOM RSS margin separately from the verified cgroup hard cap."""

    def __init__(self, run, *, proc_root=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup'), interval=0.1):
        self.run, self.proc_root, self.cgroup_root = run, proc_root, cgroup_root
        self.interval = interval
        self.proc = None
        self.unit = None
        self.error = None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample_loop, daemon=True)
        self.receipt = dict(format='muse-r11-memory-watchdog/1', cap_bytes=CAP_BYTES, rss_reserve_bytes=RSS_RESERVE,
                            threshold_rss_bytes=CAP_BYTES-RSS_RESERVE, cgroup_verified=False, samples=0,
                            peak_process_rss_bytes=0, peak_memory_bytes=0, max_unreclaimable_bytes=0,
                            min_available_bytes=None, events={})

    def __enter__(self):
        self._available()
        self.receipt['watching_since_utc'] = now()
        self.thread.start()
        return self

    def __exit__(self, *error):
        self.freeze()

    def freeze(self):
        self.stop.set()
        self.thread.join()

    def attach(self, proc, argv):
        self.unit = argv[argv.index('--unit') + 1] + '.scope'
        self.receipt['expected_scope'] = self.unit
        self.proc = proc

    def _available(self):
        available = capped_run._meminfo()['MemAvailable']
        low = self.receipt['min_available_bytes']
        self.receipt['min_available_bytes'] = available if low is None else min(low, available)
        if available < 8 << 30:
            raise capped_run.RunError('MEMORY_LOW', 'System MemAvailable fell below 8 GiB')

    def _server(self):
        pending = [self.proc.pid]
        visited = set()
        while pending:
            pid = pending.pop()
            if pid in visited:
                continue
            visited.add(pid)
            process = self.proc_root / str(pid)
            try:
                if (process / 'comm').read_text().strip() == 'llama-server':
                    return process
                pending.extend(map(int, (process/'task'/str(pid)/'children').read_text().split()))
            except FileNotFoundError:
                continue
        return None

    @staticmethod
    def _kv(path):
        return {key: int(value) for key, value in (row.split() for row in path.read_text().splitlines())}

    def sample(self):
        self._available()
        if self.proc is None or self.proc.poll() is not None:
            return
        process = self._server()
        if process is None:
            return
        try:
            cgroup = (process/'cgroup').read_text().strip().split('::')[-1].lstrip('/')
            scope = self.cgroup_root / cgroup
            if ('..' in Path(cgroup).parts or scope.name != self.unit or
                    (scope/'memory.max').read_text().strip() != str(CAP_BYTES) or
                    (scope/'memory.swap.max').read_text().strip() != '0'):
                raise capped_run.RunError('SCOPE', 'The native server is not in its verified 96 GiB / no-swap scope')
            status = (process/'status').read_text()
            rss = {name: int(value) * 1024 for name, value in re.findall(r'^(VmRSS|VmHWM):\s*(\d+) kB$', status, re.M)}
            checked(set(rss) == {'VmRSS', 'VmHWM'}, 'Cannot read native llama-server RSS')
            current = int((scope/'memory.current').read_text())
            peak = int((scope/'memory.peak').read_text())
            events = self._kv(scope/'memory.events')
            charged = self._kv(scope/'memory.stat')
            swap = int((scope/'memory.swap.current').read_text())
        except FileNotFoundError:
            if self.proc.poll() is not None:
                return
            raise
        acc = self.receipt
        acc.update(cgroup_verified=True, cgroup='/' + cgroup, samples=acc['samples'] + 1,
                   server_pid=int(process.name), current_memory_bytes=current, current_process_rss_bytes=rss['VmRSS'],
                   peak_process_rss_bytes=max(rss['VmRSS'], rss['VmHWM'], acc['peak_process_rss_bytes']),
                   peak_memory_bytes=max(peak, acc['peak_memory_bytes']), events=events, swap_bytes=swap,
                   max_unreclaimable_bytes=max(acc['max_unreclaimable_bytes'], charged.get('anon', 0) + charged.get('kernel', 0)))
        if swap or any(events.get(key, 0) for key in ('oom', 'oom_kill', 'oom_group_kill', 'high')):
            raise capped_run.RunError('MEMORY_PRESSURE', 'Cgroup reported swap, oom or high memory pressure')
        if acc['peak_process_rss_bytes'] >= acc['threshold_rss_bytes']:
            raise capped_run.RunError('MEMORY_MARGIN', 'Native server RSS entered the last 256 MiB of its 96 GiB cap')

    def _sample_loop(self):
        while not self.stop.is_set():
            try:
                self.sample()
            except (capped_run.RunError, OSError, ValueError) as error:
                self.error = error
                self.receipt['stop_error'] = dict(code=getattr(error, 'code', 'WATCHDOG_PROBE'), message=str(error), at=now())
                proc = self.proc
                if proc is not None and proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                break
            self.stop.wait(self.interval)

    def healthy(self, *, require_scope=True):
        if self.error:
            raise self.error
        if require_scope and not self.receipt['cgroup_verified']:
            raise capped_run.RunError('WATCHDOG_PROBE', 'The native server scope and hard cap were not verified')


def _previous_load(out, arm, prior, identity, images):
    if arm != 'AQBCE':
        return
    path = out/'aqbc'/LOAD
    control = read(path)
    checked(control['status'] == 'complete' and control['server_closed'] is True
            and control['load_id'] == prior['AQBC']['attempt_id']
            and all(control.get(key) == identity[key] for key in identity)
            and control['image_files_sha256'] == images,
            'The earlier switch-off load does not match the exact delivered image, build and inputs')


def execute(run, root, base):
    arm = run.req['arm']
    prior = admit_order(run.store, run.task_id, arm, run.run_id)
    identity, raw_profile, configs, workload = delivery(root)
    checked(run.req['delivery'] == identity, 'Native delivery changed after the capped attempt was admitted')
    out = base / arm.lower()
    out.mkdir(mode=0o700, exist_ok=False)
    for name in (LOAD, WARMUP, STARTUP, REQUESTS, 'server.log', 'memory-watchdog.json'):
        run.files[name] = out / name
    placeholders = {WARMUP: w2.FORMAT, STARTUP: 'muse-r11-startup-fill/1', REQUESTS: 'muse-r11-requests/1'}
    for name, format in placeholders.items():
        lab.save(out/name, dict(format=format, arm=arm, status='not-collected'))
    record = dict(format='muse-r11-target-load/1', arm=arm, status='admitting', started_utc=now(),
                  load_id=run.run_id, memory_cap=run.cap, swap_cap_bytes=0, device_budget_mib=DEVICE_BUDGET,
                  logical_env=configs[arm], server_closed=False, **identity)
    save = lambda: lab.save(out/LOAD, record)
    save()
    path = None
    server = None
    guard = MemoryWatchdog(run)
    try:
        binary, images = _extract_image(identity, out)
        record['library_delta'] = _library_delta(root, binary.parent/'libllama.so.1', identity)
        _previous_load(base, arm, prior, identity, images)
        path, profile = _stage_profile(binary.parent, raw_profile, identity['profile_sha256'])
        env = _environment(binary, configs[arm], path)
        record.update(image_files_sha256=images, profile_mapping_before=profile, physical_env=env)
        with quiet.Monitor(quiet.policy(quiet.SHARED), slots=1, stop_on_gate=True) as monitor:
            record['gate_before_load'] = run.gate()
            record['status'] = 'launch_reserved'
            save()
            with guard:
                try:
                    guard.healthy(require_scope=False)
                    server = capped_run.Server(run, str(binary), identity['pack']['first_shard'],
                                               identity['launch_config']['args'], env, 'server.log',
                                               log_path=out/'server.log', capture_stdout=True,
                                               inherit_env=False, watchdog=guard)
                    guard.healthy()
                    monitor.server = server
                    native = r8_final_benchmark.validate_ready(
                        server, dict(role=arm, ctx=8192, batch=2048, ubatch=2048, moe_cache_mib=62464))
                    record.update(status='loaded', load_seconds=server.ready_s, argv=server.argv,
                                  placement=server.placement, observed=native, image_scope_pid=server.proc.pid)
                    ready_log_end = server.log.stat().st_size
                    lab.save(out/STARTUP, startup_receipt(server.log, arm))
                    ticker = CacheLog(server.log)
                    ticker.read()  # Require native baseline before the first external completion.
                    save()
                    acquire(server, monitor, out, arm, workload, ticker)
                    guard.healthy()
                finally:
                    guard.freeze()
                    if server:
                        server.close()
                        record['server_closed'] = server.proc.poll() is not None
                        monitor.server = None
            guard.healthy()
        checked(record['server_closed'] and _image_hashes(binary.parent) == images,
                'The exact binary or libraries changed, or server did not close')
        record.update(device_budget(out/'server.log', ready_log_end, native))
        record['profile_mapping_after'] = _profile_identity(path, identity['profile_sha256'])
        checked(record['profile_mapping_after'] == profile, 'Read-only profile mapping changed while the server ran')
        record['status'] = 'complete'
    except BaseException as exc:
        record.update(status='stopped', error=str(guard.error or exc), code=getattr(guard.error or exc, 'code', type(exc).__name__))
        if guard.error and guard.error is not exc:
            raise guard.error from exc
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            raise capped_run.RunError('TARGET_INTERRUPTED', 'The independent target attempt was interrupted') from exc
        raise
    finally:
        if path is not None and 'profile_mapping_after' not in record:
            try:
                record['profile_mapping_after'] = _profile_identity(path, identity['profile_sha256'])
            except (OSError, ValueError) as exc:
                record['profile_mapping_error'] = str(exc)
        record.update(ended_utc=now(), watchdog=guard.receipt,
                      peak_memory_bytes=guard.receipt['peak_memory_bytes'] or run.peak,
                      min_available_bytes=guard.receipt['min_available_bytes'],
                      peak_process_rss_bytes=guard.receipt['peak_process_rss_bytes'] or None)
        lab.save(out/'memory-watchdog.json', guard.receipt)
        save()
    return dict(arm=arm, status='complete', package_id=identity['package_id'], request_id=identity['request_id'],
                image_id=identity['image_id'], profile_sha256=identity['profile_sha256'],
                evidence={name:digest(out/name) for name in (LOAD, WARMUP, STARTUP, REQUESTS, 'server.log', 'memory-watchdog.json')})
