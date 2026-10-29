"""RSI-only T1 arm with immutable historical plain/CC baselines.

prepare: snapshot the partner's exact source, reuse stored routes and build inputs.
validate: model-free contract checks inside the chosen immutable benchmark image.
preflight: qualify fresh Linux output permissions as the actual worker UID/GID.
run: explicitly spend a separate benchmark call budget, sequentially, once.
score: append new RSI results; never execute or overwrite historical arms.

All behavioral operations must wait until protected RSI timing campaigns stop.
"""
from __future__ import annotations
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

from export_selected import PARTNER, REPO, HERE, encoded, git_bytes, need, regular, sha

ITEMS = ('table_pad', 'calc_comma', 'calc_truncate', 'calc_float', 'table_float',
         'table_numeric', 'calc_reference', 'table_reference')
BASELINE_PATH = 'benchmarks/ccbench/runs-20261028/baseline/T1-sol-low/score-arms.json'
ROUTE_PATH = 'benchmarks/ccbench/runs-20261028/baseline/A-larger-set/cc_fallback.json'
MODEL, EFFORT = 'gpt-6.1-sol', 'low'
FAMILY_PREFIXES = {'calculate': 'calc_', 'table_normalize': 'table_'}


def selected_items(families, requested=None):
    need(bool(families) and len(families) == len(set(families))
         and set(families) <= set(FAMILY_PREFIXES), 'EXPLICIT_UNIQUE_T1_FAMILIES_REQUIRED')
    available = [item for item in ITEMS if any(item.startswith(FAMILY_PREFIXES[family]) for family in families)]
    if requested is None:
        return available
    need(bool(requested) and len(requested) == len(set(requested)) and set(requested) <= set(available),
         'T1_SUBSET_OUTSIDE_REQUESTED_FAMILIES')
    return [item for item in available if item in requested]


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if isinstance(value, bytes) else encoded(value))
        stream.flush(); os.fsync(stream.fileno())


def image_id(value):
    need(bool(re.fullmatch(r'sha256:[0-9a-f]{64}', value)), 'IMMUTABLE_BENCHMARK_IMAGE_ID_REQUIRED')
    return value


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        need(not path.is_symlink(), 'BENCHMARK_SYMLINK_DENIED')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    return result


def partner_snapshot(root):
    # Frozen run artifact only: no checkout, merge or change to the working tree.
    result = subprocess.run(['git', '-C', str(REPO), 'archive', '--format=tar', PARTNER,
                             'benchmarks', 'jiuwenswarm', 'pyproject.toml'], capture_output=True, check=True)
    need(len(result.stdout) <= 512 * 1024 * 1024, 'PARTNER_SOURCE_ARCHIVE_TOO_LARGE')
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode='r:') as archive:
        for entry in archive:
            relative = PurePosixPath(entry.name)
            need(not relative.is_absolute() and '..' not in relative.parts
                 and '\\' not in entry.name and ':' not in entry.name, 'PARTNER_ARCHIVE_PATH_INVALID')
            target = root / relative
            if entry.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                need(entry.isfile(), 'PARTNER_ARCHIVE_LINK_OR_SPECIAL_FILE_DENIED')
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(entry) as source:
                    target.write_bytes(source.read())


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def prepare(args):
    out, served = args.out.resolve(), args.served.resolve()
    need(not out.exists() and not any(c.isspace() for c in str(out)), 'FRESH_SPACE_FREE_RUN_DIRECTORY_REQUIRED')
    export_raw = regular(served / 'export.json'); export = json.loads(export_raw)
    need(export['schema'] == 'ai4r-t1-rsi-export:1' and export['partner_commit'] == PARTNER,
         'PINNED_FINAL_SELECTION_EXPORT_REQUIRED')
    families = args.family
    items = selected_items(families, args.item)
    exported_tools = {row['capsule_name']: row for row in export['tools']}
    need(len(exported_tools) == len(export['tools'])
         and {'utility.' + family for family in families} <= set(exported_tools),
         'REQUESTED_FINAL_TOOL_SELECTIONS_REQUIRED')
    tools = {'utility.' + family: exported_tools['utility.' + family] for family in families}
    for row in tools.values():
        need(sha(regular(served / row['tool_file'])) == row['tool_sha256']
             and sha(regular(served / 'rsi_bundle' / row['specification'])) == row['specification_sha256'],
             'EXPORTED_TOOL_PIN_DIFFERS')
    out.mkdir(parents=True)
    source = out / 'partner-source'; partner_snapshot(source)
    frozen_served = out / 'served'; shutil.copytree(served, frozen_served)
    na = source / 'benchmarks/ccbench/nativeadmit'
    route_raw = git_bytes(ROUTE_PATH)
    historical_routes = json.loads(route_raw)
    route_by_item = {row['item']: row['route'] for row in historical_routes}
    need(len(route_by_item) == len(historical_routes) and set(items) <= set(route_by_item),
         'HISTORICAL_ROUTE_INVENTORY_DIFFERS')
    write_new(out / 'historical-routes.json', route_raw)
    rows = []
    for item in items:
        original = na / 'items' / item / 'public'
        job = json.loads((original.parent / 'job.json').read_bytes())
        historical_route = route_by_item[item]
        need(historical_route in ('admitted tool', 'rejected, fallback to admitted reference'),
             'HISTORICAL_ROUTE_NOT_REUSABLE')
        verdict = {'id': item, 'admitted': historical_route == 'admitted tool',
                   'source': ROUTE_PATH, 'source_sha256': sha(route_raw), 'reused': True}
        destination = out / 'inputs' / item; shutil.copytree(original, destination)
        write_new(out / 'route' / (item + '.json'), verdict)
        replaced = not verdict['admitted']
        selection = None
        if replaced:
            row = tools['utility.' + job['tool']]
            shutil.copyfile(frozen_served / row['tool_file'], destination / job['tool_file'])
            shutil.copytree(frozen_served / 'rsi_bundle', destination / 'rsi_bundle')
            selection = row['selection']
        rows.append({'item': item, 'original_tool_passed_benchmark_contract': verdict['admitted'],
                     'served_selected_worker': replaced, 'selection': selection,
                     'task_sha256': sha(regular(destination / 'task.txt')),
                     'original_tool_sha256': sha(regular(original / job['tool_file'])),
                     'served_tool_sha256': sha(regular(destination / job['tool_file']))})
    baseline_raw = git_bytes(BASELINE_PATH); baseline = json.loads(baseline_raw)
    need(all(len([r for r in baseline['rows'] if r['arm'] == arm]) == len(ITEMS)
             and {(r['item'], r['rep']) for r in baseline['rows'] if r['arm'] == arm}
                 == {(item, 1) for item in ITEMS} for arm in ('plain', 'cc')),
         'HISTORICAL_EIGHT_ITEM_BASELINE_REQUIRED')
    write_new(out / 'historical-score-arms.json', baseline_raw)
    shutil.copyfile(HERE / 'validate_served.py', out / 'validate_served.py')
    shutil.copyfile(HERE / 'preflight_application.py', out / 'preflight_application.py')
    shutil.copyfile(HERE / 'driver_compat.py', out / 'driver_compat.py')
    host_work = None
    if args.host_work_root is not None:
        work_root = args.host_work_root.absolute()
        need(not any(p.is_symlink() for p in (work_root, *work_root.parents)), 'LINKED_HOST_MODEL_WORK_ROOT_DENIED')
        work_root.mkdir(parents=True, exist_ok=True)
        info = work_root.stat()
        need(stat.S_ISDIR(info.st_mode), 'HOST_MODEL_WORK_ROOT_DIRECTORY_REQUIRED')
        host_work = {'path': str(work_root), 'device': info.st_dev, 'inode': info.st_ino,
                     'uid': info.st_uid, 'gid': info.st_gid,
                     'scope': 'Fresh per-plan/session empty model workspaces only; private receipts remain under run output.'}
    meta = {'schema': 'ai4r-t1-rsi-plan:1', 'partner_commit': PARTNER, 'model': MODEL, 'effort': EFFORT,
            'bridge_system': '0', 'host_model_work_root': host_work,
            'host_driver_compatibility': {'file': 'driver_compat.py',
                'sha256': sha(regular(out / 'driver_compat.py')),
                'scope': 'Exact shared broker response.pending mode0640 before original atomicrename; private write_once remains0600'},
            'image_id': image_id(args.image), 'baseline_image_id': args.baseline_image,
            'baseline_image_match': None if args.baseline_image is None else args.image == args.baseline_image,
            'baseline_sha256': sha(baseline_raw), 'baseline_path_at_commit': BASELINE_PATH,
            'historical_route_sha256': sha(route_raw), 'historical_route_path_at_commit': ROUTE_PATH,
            'export_sha256': sha(export_raw), 'families': families, 'requested_items': items,
            'deferred_families': [family for family in FAMILY_PREFIXES if family not in families],
            'omitted_historical_items': [item for item in ITEMS if item not in items],
            'items': rows, 'repetitions': args.reps,
            'historical_arms_reused': ['plain', 'cc'], 'new_arms': ['rsi'],
            'comparability': [row['comparability'] for row in tools.values()],
            'limits': ['Historical results were measured earlier; no randomized contemporaneous comparison.',
                       'New arm uses packet workers and a frozen runtime bridge; runtime/parent differences prevent an RSI-only causal claim.',
                       'Only replaced-tool items exercise selected workers; correct-reference items remain controls.'],
            'production_admission': 'UNKNOWN', 'created_at': datetime.now(timezone.utc).isoformat()}
    write_new(out / 'artifact-pins.json', inventory(out))
    meta['artifact_pins_sha256'] = sha(regular(out / 'artifact-pins.json'))
    write_new(out / 'plan.json', meta)
    return meta


def verified(out):
    plan = json.loads(regular(out / 'plan.json'))
    pins_raw = regular(out / 'artifact-pins.json')
    need(sha(pins_raw) == plan['artifact_pins_sha256'], 'ARTIFACT_INVENTORY_PIN_DIFFERS')
    pins = json.loads(pins_raw)
    for name, expected in pins.items():
        need(sha(regular(out / name)) == expected, 'PREPARED_ARTIFACT_CHANGED: ' + name)
    need(plan['schema'] == 'ai4r-t1-rsi-plan:1' and plan['partner_commit'] == PARTNER
         and plan['model'] == MODEL and plan['effort'] == EFFORT and plan['bridge_system'] == '0',
         'PINNED_T1_PLAN_REQUIRED')
    need([row['item'] for row in plan['items']] == selected_items(plan['families'], plan['requested_items'])
         and type(plan['repetitions']) is int and 1 <= plan['repetitions'] <= 10, 'FIXED_T1_ITEM_PLAN_REQUIRED')
    need(plan['baseline_sha256'] == sha(regular(out / 'historical-score-arms.json')),
         'HISTORICAL_BASELINE_CHANGED')
    return plan


def validate(out):
    plan = verified(out)
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
               '--mount', 'type=bind,src=' + str(out / 'partner-source') + ',dst=/partner,readonly',
               '--mount', 'type=bind,src=' + str(out / 'served') + ',dst=/served,readonly',
               '--mount', 'type=bind,src=' + str(out / 'validate_served.py') + ',dst=/validate.py,readonly',
               '--entrypoint', '/usr/local/bin/python3', plan['image_id'], '-B', '/validate.py', '/partner', '/served', *plan['families']]
    completed = subprocess.run(command, capture_output=True, timeout=3600)
    write_new(out / 'contract-validation.stdout', completed.stdout)
    write_new(out / 'contract-validation.stderr', completed.stderr)
    need(completed.returncode == 0, 'BENCHMARK_CONTRACT_OR_WORKER_ABI_VALIDATION_FAILED')
    result = json.loads(completed.stdout)
    need(result['passed'] is True, 'BENCHMARK_CONTRACT_FAILED')
    result.update(image_id=plan['image_id'], plan_sha256=sha(regular(out / 'plan.json')),
                  artifact_pins_sha256=sha(regular(out / 'artifact-pins.json')))
    write_new(out / 'contract-validation.json', result)
    return result



def worker_preflight(out):
    """Qualify fresh Linux output custody without issuing any model request."""
    plan = verified(out)
    need(os.name == 'posix', 'BENCHMARK_RUN_REQUIRES_LINUX_OUTPUT_PERMISSIONS')
    need(not (out / 'run-started.json').exists(), 'CONSUMED_BENCHMARK_RUN_DENIED')
    root = out / 'rsi'
    need(not root.exists() and not root.is_symlink(), 'FRESH_RSI_OUTPUT_ROOT_REQUIRED')
    root.mkdir(mode=0o770)
    os.chown(root, -1, 10001)
    os.chmod(root, 0o2770)
    # The frozen driver and its broker inherit the same mask and setgid root.
    campaign = root / 'permission-preflight' / 'native'
    source = out / 'partner-source'
    initialize = [sys.executable, '-B', str(out / 'driver_compat.py'), '--probe-publication', str(campaign)]
    subprocess.run(initialize, env=dict(os.environ, AI4R_CODE_ROOT=str(source), PYTHONPATH=str(source),
                   PYTHONDONTWRITEBYTECODE='1'), check=True, capture_output=True, umask=0o007)
    probe = """import errno,json,os,pathlib,stat
p=pathlib.Path('/campaign')
assert os.getuid()==10001 and os.getgid()==10001
(p/'run').mkdir()
(p/'run'/'worker-output').write_text('worker')
assert json.loads((p/'broker'/'00000000000000000000000000000000.response.json').read_text())=={'probe':'shared-response'}
assert stat.S_IMODE((p/'broker'/'00000000000000000000000000000000.response.json').stat().st_mode)==0o640
(p/'broker'/'worker-request').write_text('request')
with (p/'broker'/'host-response').open('a') as f: f.write('-worker')
try:
    pathlib.Path('/inputs/.write-denied-probe').write_text('must fail')
except OSError as e:
    assert e.errno==errno.EROFS, repr(e)
else:
    raise RuntimeError('INPUT_MOUNT_NOT_READ_ONLY')
print(json.dumps({'passed':True,'uid':os.getuid(),'gid':os.getgid(),'input_mount_readonly':True,
 'shared_response_readable':True, 'private_receipt_mode':'0600',
 'campaign_mode':oct(stat.S_IMODE(p.stat().st_mode)), 'campaign_gid':p.stat().st_gid}))
"""
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
               '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--mount', 'type=bind,src=' + str(campaign) + ',dst=/campaign',
               '--mount', 'type=bind,src=' + str(out / 'inputs') + ',dst=/inputs,readonly',
               '--entrypoint', '/usr/local/bin/python3', plan['image_id'], '-I', '-B', '-c', probe]
    completed = subprocess.run(command, capture_output=True, timeout=120, umask=0o007)
    write_new(out / 'worker-preflight.stdout', completed.stdout)
    write_new(out / 'worker-preflight.stderr', completed.stderr)
    need(completed.returncode == 0, 'WORKER_CAMPAIGN_WRITE_PREFLIGHT_FAILED')
    result = json.loads(completed.stdout)
    need(result['passed'] is True and result['campaign_gid'] == 10001,
         'WORKER_CAMPAIGN_WRITE_PREFLIGHT_FAILED')
    # Host broker must also consume worker requests and publish responses.
    request = campaign / 'broker' / 'worker-request'
    need(request.read_text() == 'request' and (campaign / 'broker' / 'host-response').read_text() == 'host-worker',
         'HOST_WORKER_BROKER_PREFLIGHT_FAILED')
    with request.open('a') as stream:
        stream.write('-host'); stream.flush(); os.fsync(stream.fileno())
    runtime = out / 'partner-source/benchmarks/ccbench/nativetask/native-runtime-en'
    application_command = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
        '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001',
        '-e', 'HOME=/tmp', '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/runtime:/opt/ai4r',
        '--mount', 'type=bind,src=' + str(campaign) + ',dst=/campaign',
        '--mount', 'type=bind,src=' + str(runtime) + ',dst=/runtime,readonly',
        '--mount', 'type=bind,src=' + str(out / 'preflight_application.py') + ',dst=/preflight.py,readonly',
        '--entrypoint', '/opt/venv/bin/python', plan['image_id'], '-B', '/preflight.py', '/campaign/application']
    application = subprocess.run(application_command, capture_output=True, timeout=180, umask=0o007)
    write_new(out / 'application-preflight.stdout', application.stdout)
    write_new(out / 'application-preflight.stderr', application.stderr)
    need(application.returncode == 0, 'NATIVE_APPLICATION_INITIALIZATION_PREFLIGHT_FAILED')
    result['application'] = json.loads(application.stdout.splitlines()[-1])
    need(result['application']['passed'] is True and result['application']['model_calls'] == 0,
         'MODEL_FREE_NATIVE_APPLICATION_PREFLIGHT_REQUIRED')
    info = root.stat()
    result.update(plan_sha256=sha(regular(out / 'plan.json')), image_id=plan['image_id'],
                  root_device=info.st_dev, root_inode=info.st_ino, root_uid=info.st_uid,
                  root_gid=info.st_gid, root_mode=stat.S_IMODE(info.st_mode), subprocess_umask='0007')
    write_new(out / 'worker-preflight.json', result)
    return result


def verify_worker_preflight(out, plan):
    result = json.loads(regular(out / 'worker-preflight.json'))
    root = out / 'rsi'
    need(not root.is_symlink() and root.is_dir(), 'RSI_OUTPUT_ROOT_CUSTODY_CHANGED')
    info = root.stat()
    need(result['passed'] is True and result['input_mount_readonly'] is True
         and result.get('shared_response_readable') is True and result.get('private_receipt_mode') == '0600'
         and result.get('application', {}).get('passed') is True
         and result['application']['model_calls'] == 0
         and result['plan_sha256'] == sha(regular(out / 'plan.json'))
         and result['image_id'] == plan['image_id'] and result['subprocess_umask'] == '0007'
         and (info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
             == (result['root_device'], result['root_inode'], result['root_uid'], 10001, 0o2770)
         and all(not (root / name).exists() and not (root / name).is_symlink()
                 for name in ('sessions', 'ledgers')),
         'FRESH_QUALIFIED_WORKER_OUTPUT_REQUIRED')
    return result


def run(args):
    out = args.out.resolve(); plan = verified(out)
    validation = json.loads(regular(out / 'contract-validation.json'))
    need(validation['passed'] is True and validation['image_id'] == plan['image_id']
         and validation['plan_sha256'] == sha(regular(out / 'plan.json'))
         and validation['artifact_pins_sha256'] == sha(regular(out / 'artifact-pins.json')), 'CURRENT_BENCHMARK_VALIDATION_REQUIRED')
    items = plan['requested_items']
    count = len(items) * plan['repetitions']
    need(1 <= args.calls_per_attempt <= 80 and args.total_call_budget >= count * args.calls_per_attempt,
         'EXPLICIT_SEPARATE_BENCHMARK_CALL_BUDGET_REQUIRED')
    need(not (out / 'run-started.json').exists(), 'CONSUMED_BENCHMARK_RUN_DENIED')
    if not (out / 'worker-preflight.json').exists():
        worker_preflight(out)
    preflight = verify_worker_preflight(out, plan)
    write_new(out / 'run-started.json', {'schema': 'ai4r-t1-rsi-run-start:1',
              'plan_sha256': sha(regular(out / 'plan.json')), 'maximum_model_calls': count * args.calls_per_attempt,
              'approved_call_budget': args.total_call_budget, 'calls_per_attempt': args.calls_per_attempt,
              'one_model_job_at_a_time': True, 'replay': False,
              'worker_preflight_sha256': sha(regular(out / 'worker-preflight.json')),
              'subprocess_umask': preflight['subprocess_umask']})
    source = out / 'partner-source'; script = out / 'driver_compat.py'
    env = dict(os.environ, AI4R_CODE_ROOT=str(source), AI4R_PRODUCT_COMMIT=PARTNER,
               AI4R_PRODUCT_DIRTY='0', AI4R_BRIDGE_SYSTEM='0', PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1')
    results = []
    for repeat in range(1, plan['repetitions'] + 1):
        for item in items:
            ident = item + '-r' + str(repeat)
            ledger = out / 'rsi' / 'ledgers' / ident
            initialize = [sys.executable, '-B', str(script), 'init-ledger', '--out', str(ledger),
                          '--effort', EFFORT, '--max-calls', str(args.calls_per_attempt), '--wall-s', '10800']
            subprocess.run(initialize, cwd=source, env=env, check=True, capture_output=True, umask=0o007)
            inputs = out / 'inputs' / item
            command = [sys.executable, '-B', str(script), 'run', '--task-file', str(inputs / 'task.txt'),
                       '--inputs-dir', str(inputs), '--ledger', str(ledger / 'ledger.sqlite3'),
                       '--attempt-id', ident, '--model', MODEL, '--effort', EFFORT,
                       '--image', plan['image_id'], '--max-calls', str(args.calls_per_attempt),
                       '--execute', '--out', str(out / 'rsi')]
            if args.binary:
                command += ['--binary', args.binary]
            with (out / (ident + '.log')).open('xb') as log:
                completed = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, umask=0o007)
            results.append({'attempt': ident, 'exit_code': completed.returncode})
            if completed.returncode:
                # Unknown envelopes are retained; do not spend the next attempt's calls.
                write_new(out / 'run-stopped.json', {'attempts': results, 'reason': 'attempt_failed_no_replay'})
                return {'attempts': results, 'status': 'stopped'}
    write_new(out / 'run-finished.json', {'attempts': results})
    return score(out)


def score(out):
    plan = verified(out)
    source = out / 'partner-source'; na = source / 'benchmarks/ccbench/nativeadmit'
    sys.path[:0] = [str(na), str(na.parent)]
    scorer = module(na / 'score_arms.py', 'rsi_partner_scorer')
    baseline = json.loads(regular(out / 'historical-score-arms.json'))
    items = plan['requested_items']
    historical = [row for row in baseline['rows'] if row['arm'] in ('plain', 'cc') and row['item'] in items]
    rows = scorer.score_arm('rsi', out / 'rsi') if (out / 'rsi/sessions').is_dir() else []
    expected = {(item, repeat) for item in items for repeat in range(1, plan['repetitions'] + 1)}
    seen = {(row['item'], row['rep']) for row in rows}
    need(len(rows) == len(seen) and seen <= expected, 'UNEXPECTED_OR_DUPLICATE_RSI_SESSION')
    for item, repeat in sorted(expected - seen):
        rows.append({'arm': 'rsi', 'session': item + '-r' + str(repeat), 'item': item, 'rep': repeat,
                     'cls': 'unavailable', 'reason': 'No completed session was available; denominator retained.',
                     **{key: None for key in ('input_tokens', 'output_tokens', 'total_tokens', 'calls', 'wall_s')}})
    costs = scorer.cost.cost_table(historical + rows)
    classes = {arm: {c: sum(r['arm'] == arm and r['cls'] == c for r in historical + rows)
                     for c in scorer.score.CLASSES} for arm in ('plain', 'cc', 'rsi')}
    policy = json.loads(regular(out / 'run-started.json')) if (out / 'run-started.json').is_file() else None
    result = {'schema': 'ai4r-t1-rsi-comparison:1', 'historical_arms_reused': ['plain', 'cc'],
              'selected_families': plan['families'], 'selected_items': items,
              'deferred_families': plan['deferred_families'], 'new_run_call_policy': policy,
              'baseline_call_ceiling_match': None if policy is None else policy['calls_per_attempt'] == 80,
              'historical_baseline_sha256': plan['baseline_sha256'], 'class_counts': classes, 'cost': costs,
              'rows': historical + rows, 'provenance': plan,
              'separate_RSI_benchmark_required_for_speed_claim': True}
    target = out / 'comparison'; target.mkdir(exist_ok=True)
    # Scoring is repeatable; only derived comparison files may be replaced.
    (target / 'score-arms.json').write_bytes(encoded(result))
    text = scorer.cost.markdown(costs, 'T1 ' + ', '.join(plan['families']) + ' subset: historical plain/CC and new RSI arm')
    text += '\nHistorical rows for the selected items are reused unchanged. Unavailable selected runs remain in the denominator; deferred families are excluded.\n'
    text += '\nEnd-to-end differences include the selected release/runtime adapter; use the protected RSI benchmark for the parent/child speed claim.\n'
    (target / 'score-arms.md').write_text(text, encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--served', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--image', type=image_id, required=True)
    p.add_argument('--baseline-image', type=image_id)
    p.add_argument('--host-work-root', type=Path,
                   help='Optional explicit host-accessible root for fresh model working directories; no private receipts are moved.')
    p.add_argument('--family', action='append', choices=tuple(FAMILY_PREFIXES), required=True,
                   help='Explicit requested family; repeat only to include both.')
    p.add_argument('--item', action='append', choices=ITEMS,
                   help='Optional subset within the requested families; default is their original T1 items.')
    p.add_argument('--reps', type=int, choices=range(1, 11), default=1)
    for operation in ('validate', 'preflight', 'run', 'score'):
        p = sub.add_parser(operation); p.add_argument('--out', type=Path, required=True)
        if operation == 'run':
            p.add_argument('--calls-per-attempt', type=int, required=True)
            p.add_argument('--total-call-budget', type=int, required=True)
            p.add_argument('--binary')
    args = parser.parse_args()
    if args.operation == 'prepare': result = prepare(args)
    elif args.operation == 'validate': result = validate(args.out.resolve())
    elif args.operation == 'preflight': result = worker_preflight(args.out.resolve())
    elif args.operation == 'run': result = run(args)
    else: result = score(args.out.resolve())
    print(json.dumps(result, indent=2))
    if args.operation == 'run' and result.get('status') in ('stopped', 'failed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
