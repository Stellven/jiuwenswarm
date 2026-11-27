"""Prepare or publish Run 4's independent target lab verdict without starting a model."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import tempfile

from jiuwenswarm.factory.contract import load_for_task
from jiuwenswarm.factory.lab_agent import LabAgent, accepted_by
from jiuwenswarm.factory.lab_mailbox import open_mailbox
from jiuwenswarm.factory.lab_manager import LabManager
from jiuwenswarm.factory.muse_r11_cache import RECIPE, ROOT, TASK as LAB_TASK
from jiuwenswarm.factory.muse_r11_gate import (
    EVIDENCE_FILES, calibration_requests, check_for, graph, require_eligible, verify_calibration_binding, verify_image,
)
from jiuwenswarm.factory.muse_r11_scoring import ARMS, ARTIFACTS, TASK, check, evaluate, optional_json, sha
from jiuwenswarm.factory.views.activity import _snapshot_store

# The capped runner seals complete files through this size and omits larger files.
MAX_ARTIFACT = 64 << 20
REPO = Path(__file__).resolve().parents[2]


def factory_delivery(graph_home, mailbox, request_id):
    with _snapshot_store(graph_home) as store:
        task = store.get_task(TASK)
        contract = load_for_task(task, TASK)
        checkpoint = task['constraints']['seeding_checkpoint']
        nodes = graph(store, TASK)
        premise = require_eligible(store, TASK, checkpoint, nodes)
        delivery = check_for(store, TASK, nodes, checkpoint['delivery_node'], 'lab_package')
        found = delivery['found']
        check(nodes[checkpoint['delivery_node']]['state'] == 'done' and request_id == found['request_id'],
              'The mailbox request is not the completed native Run 4 delivery.')
        package = LabManager(store, mailbox=mailbox, route='mailbox')._package_for(TASK, request_id)
        check(found['package_id'] == package['package_id']
              and found['contract_sha256'] == package['contract']['sha256'] == task['constraints']['contract_sha256']
              and package['contract']['document'] == contract,
              'The sent package does not match the current admitted contract.')
        engine = package['subjects'][package['lab_task']['arms']['AQBC']['subject']]
        build_id, image_id = engine['build_attempt_id'], engine['identity']['id']
        image_check = verify_image(store, task, dict(build_attempt_id=build_id, image_id=image_id))
        check_receipt = json.loads(store.artifact_bytes(TASK, image_check))
        profile = package['subjects']['seeding_profile']['payload']
        check(profile['sha256'] == premise['profile_sha256']
              and sha(mailbox.file_path(request_id, profile).read_bytes()) == profile['sha256'],
              'The shipped profile differs from the accepted premise.')
        expected_manifest = premise['manifest_sha256']
        candidates = [row for row in store.dump(TASK)['observations'] if row['kind'] == 'operator_input'
                      and row['values'].get('key') == 'seeding_trace_manifest'
                      and row['values'].get('sha256') == expected_manifest]
        check(len(candidates) == 1, 'The accepted profile has no unique operator-sealed capture manifest.')
        manifest = candidates[0]
        artifact_id = manifest['values']['artifact_id']
        check(artifact_id in manifest['source_artifacts'], 'The operator manifest receipt has no sealed artifact.')
        raw = store.artifact_bytes(TASK, artifact_id)
        check(sha(raw) == expected_manifest, 'The profiles acquisition manifest digest differs.')
        profile_manifest = json.loads(raw)
        verify_calibration_binding(contract, profile_manifest)
        folder = REPO / 'ops/spark/prompts/muse'
        pins = json.loads((folder / 'MANIFEST.json').read_bytes())['files']
        prompts = {}
        for size in (512, 2048):
            filename = f'{size}.rendered.txt'
            text_sha = sha((folder / filename).read_bytes())
            input_id = f'prompt_{size}'
            raw_prompt = (folder / f'{size}.txt').read_bytes()
            check(text_sha == pins[filename]
                  and sha(raw_prompt) == contract['inputs'][input_id]['sha256'],
                  'The fixed request files differ from the sealed workload.')
            profiled = {(row['prompt_n'], row['token_ids_sha256']) for row in profile_manifest['requests']
                        if row['cohort'] == 'heldout' and row['cell'] == f'warm-{size}'
                        and row['prompt_sha256'] == text_sha}
            check(len(profiled) == 1, 'No unique profiled tokenizer pin for the fixed request.')
            prompts[size] = (text_sha, *profiled.pop())
        calibration = {sha(row['rendered_prompt'].encode()) for row in calibration_requests(contract)}
        delivery_identity = dict(obs_id=delivery['obs_id'], image_check_id=image_check,
                                 executable_sha256=check_receipt['executable_sha256'],
                                 source_commit=check_receipt['source_commit'],
                                 profile_artifact_id=profile['artifact_id'], profile_manifest_sha256=expected_manifest)
        return package, delivery_identity, prompts, calibration


def reservation_time(attempt):
    history = attempt.get('history') or []
    first = history[0] if history else {}
    check(first.get('state') == 'queued' and type(first.get('created')) in (int, float),
          'A capped attempt has no initial native reservation.')
    return first['created']


def sealed_file(store, attempt, observation, name):
    ident = f"run-{attempt['attempt_id'][:12]}-{name}"
    if ident not in observation['source_artifacts']:
        return None
    metadata = store.read_artifact(LAB_TASK, ident)
    check(metadata['size'] <= MAX_ARTIFACT, 'Native lab file exceeds the capped evidence bound: ' + name)
    raw = store.artifact_bytes(LAB_TASK, ident)
    check(len(raw) == metadata['size'] and sha(raw) == metadata['sha256'],
          'The native capped job artifact changed: ' + name)
    return dict(data=raw, artifact_id=ident, sha256=metadata['sha256'], size=len(raw))


def load_window(receipt, arm):
    document = json.loads(receipt['data'])
    if arm == 'profile':
        check(document.get('format') == 'muse-r11-load/1'
              and document.get('status') == 'complete' and document.get('server_closed') is True,
              'The profile receipt does not record a completed native load.')
    else:
        check(document.get('format') == 'muse-r11-target-load/1' and document.get('arm') == arm,
              'A target load receipt belongs to another arm.')
    try:
        start = datetime.fromisoformat(document['started_utc'])
        end = datetime.fromisoformat(document['ended_utc'])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError(f'The capped {arm} load has no recorded execution window.') from error
    check(start.utcoffset() is not None and end.utcoffset() is not None and start <= end,
          f'The capped {arm} load has an invalid execution window.')
    return start, end


def native_arms(lab_home, request_id, package_id, delivery):
    with _snapshot_store(lab_home) as store:
        ledger = store.dump(LAB_TASK)
        attempts = sorted((row for row in ledger['attempts'] if row['kind'] == 'model_run'),
                          key=reservation_time)
        order = [row.get('request', {}).get('arm') for row in attempts]
        reserved = {reservation_time(row) for row in attempts}
        check(order == ['profile', *ARMS][:len(order)] and 0 < len(order) <= 3
              and len(reserved) == len(attempts),
              'The independent capped ledger must have one serial load per admitted arm.')
        check(all(row['state'] in {'succeeded', 'failed', 'cancelled'} for row in attempts),
              'A capped target load is still active; wait for its sealed receipts.')
        result = {}
        last_end = None
        for attempt in attempts:
            arm = attempt['request']['arm']
            observations = [row for row in ledger['observations'] if row['kind'] == 'capped_run'
                            and row['values'].get('attempt_id') == attempt['attempt_id']]
            check(len(observations) <= 1, 'A capped attempt has ambiguous native receipts.')
            if not observations:
                check(arm != 'profile' and attempt['state'] != 'succeeded',
                      'A successful capped load has no native receipt.')
                result[arm] = dict(attempt=attempt, observation={}, files={})
                continue
            observation = observations[0]
            native = observation['values']
            request = native.get('request') or {}
            check(native.get('recipe') == attempt['request'].get('recipe') == RECIPE
                  and native.get('attempt_id') == attempt['attempt_id']
                  and observation.get('host_run', {}).get('module') == 'jiuwenswarm.factory.capped_run'
                  and observation['host_run'].get('attempt_id') == attempt['attempt_id']
                  and request.get('arm') == arm and request == attempt['request']
                  and ((native.get('outcome') == 'ok') == (attempt['state'] == 'succeeded')),
                  'A native capped receipt belongs to an unrelated or incomplete admission.')
            receipt = native.get('result') or {}
            if arm == 'profile':
                check(attempt['state'] == 'succeeded' and receipt.get('arm') == 'profile'
                      and receipt.get('status') == 'complete'
                      and receipt.get('manifest_sha256') == delivery['profile_manifest_sha256'],
                      'The capped profile does not match the accepted acquisition manifest.')
                manifest = sealed_file(store, attempt, observation, 'manifest.json')
                check(manifest and manifest['sha256'] == receipt['manifest_sha256'],
                      'The capped profile has no sealed acquisition manifest.')
                load = sealed_file(store, attempt, observation, 'load.json')
                check(load, 'The capped profile has no sealed load receipt.')
                _, last_end = load_window(load, arm)
                continue
            # The admission contains the sealed delivery identity.
            identities = dict(request_id=request_id, package_id=package_id, delivery_check_id=delivery['obs_id'])
            check(all(request.get('delivery', {}).get(key) == value for key, value in identities.items()),
                  'A native capped load belongs to another delivery.')
            files = {name: ref for name in ARTIFACTS if (ref := sealed_file(store, attempt, observation, name))}
            load = files.get('load-receipts.json')
            if load:
                start, end = load_window(load, arm)
                check(last_end <= start, 'The recorded independent capped loads overlapped.')
                last_end = end
            if attempt['state'] == 'succeeded':
                check(receipt.get('arm') == arm and receipt.get('status') == 'complete'
                      and receipt.get('request_id') == request_id and receipt.get('package_id') == package_id
                      and receipt.get('image_id') == request['delivery']['image_id']
                      and receipt.get('profile_sha256') == request['delivery']['profile_sha256']
                      and set(files) == set(ARTIFACTS)
                      and {name: row['sha256'] for name, row in files.items()} == receipt.get('evidence'),
                      'The successful capped receipt does not seal the exact files for its delivered arm.')
            result[arm] = dict(attempt=attempt, observation=observation, files=files)
    return result


def stage_report(output, request, package, report, arms, measured, startup, comparison):
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Choose a new staging directory for the lab verdict.')
    with tempfile.TemporaryDirectory(prefix='.r11-report-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'staged'
        stage.mkdir()
        names = []

        def put(name, value):
            path = stage / name
            raw = value if isinstance(value, bytes) else (
                json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
            path.write_bytes(raw)
            names.append(name)

        for name in EVIDENCE_FILES:
            rows = {}
            for arm in ARMS:
                source = arms.get(arm, {})
                files = source.get('files', {})
                ref = files.get(name)
                row = dict(attempt_id=source.get('attempt', {}).get('attempt_id'),
                           observation_id=source.get('observation', {}).get('obs_id'))
                if ref:
                    suffix = 'load.json' if name == 'load-receipts.json' else name
                    raw_name = ARMS[arm] + '-' + suffix
                    put(raw_name, ref['data'])
                    row.update(attachment=raw_name, **{key: ref[key] for key in ('artifact_id', 'sha256', 'size')})
                rows[arm] = row
            put(name, dict(format='muse-r11-report-source-index/1', request_id=request,
                           package_id=package['package_id'], arms=rows))

        for arm, label in ARMS.items():
            source = arms.get(arm, {})
            files = source.get('files', {})
            if arm in startup:
                receipt = files['startup-fill-receipts.json']
                put(label + '-startup-fill.json', dict(startup[arm], report_source=dict(
                    attachment=label + '-startup-fill-receipts.json', sha256=receipt['sha256'])))
            if measured[arm]:
                receipt = files['request-receipts.json']
                raw_rows = optional_json(files, 'request-receipts.json')['rows']
                idx = {row['id']: index for index, row in enumerate(raw_rows)}
                put(label + '-speed.json', dict(format='muse-r11-chart-request-projection/1',
                    source=dict(attachment=label + '-request-receipts.json', sha256=receipt['sha256']),
                    rows=[dict(row, cell=cell, source_pointer=f"/rows/{idx[row['id']]}")
                          for (cell, _), row in measured[arm].items()]))
            for name in ('server.log', 'memory-watchdog.json'):
                if name in files:
                    put(label + '-' + name, files[name]['data'])
        if comparison:
            put('matched-comparison.json', comparison)
        put('report.json', report)
        names.remove('report.json')
        stage.rename(output)
    return {name: output / name for name in names}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request_id')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--graph-home', type=Path, default=ROOT / 'r11/graph')
    parser.add_argument('--lab-home', type=Path, default=ROOT / 'r11/lab-home')
    parser.add_argument('--mailbox')
    parser.add_argument('--lab-name')
    parser.add_argument('--publish', action='store_true', help='Post the validated report as the already-accepted LabAgent.')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    graph_home, lab_home = args.graph_home.resolve(), args.lab_home.resolve()
    check(not any(output.is_relative_to(path) for path in (graph_home, lab_home)),
          'Choose a report staging directory outside the native homes.')
    mailbox = open_mailbox(args.mailbox, home=graph_home)
    thread = mailbox.thread(args.request_id)
    owner = accepted_by(thread)
    if args.publish:
        check(owner is not None and args.lab_name == owner and thread['state'] in {'accepted', 'running'},
              'Publication requires the named independent LabAgent that already accepted this request.')
    agent = LabAgent(mailbox, name=args.lab_name or owner or 'muse-r11-target', profile='spark-gb10')
    package, delivery, prompts, calibration = factory_delivery(graph_home, mailbox, args.request_id)
    arms = native_arms(lab_home, args.request_id, package['package_id'], delivery)
    report, measured, startup, comparison = evaluate(package, args.request_id, delivery, arms, prompts, calibration)
    files = stage_report(output, args.request_id, package, report, arms, measured, startup, comparison)
    problems = agent.check_report(args.request_id, report, files)
    check(not problems, 'Prepared report does not answer the delivered requirements: ' + '; '.join(problems or []))
    if args.publish:
        response = agent.report(args.request_id, report, files)
        print(response['id'])
    print(str(output / 'report.json'))
    print(report['summary'])


if __name__ == '__main__':
    main()
