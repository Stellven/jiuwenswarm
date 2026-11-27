"""Prepare or publish Run 4's independent target lab verdict without starting a model."""
from __future__ import annotations

import argparse
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

MAX_ARTIFACT = 16 << 20
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


def native_arms(lab_home, request_id, package_id, delivery):
    with _snapshot_store(lab_home) as store:
        ledger = store.dump(LAB_TASK)
        attempts = sorted((row for row in ledger['attempts'] if row['kind'] == 'model_run'),
                          key=lambda row: row['created'])
        order = [row.get('request', {}).get('arm') for row in attempts]
        check(order == ['profile', *ARMS][:len(order)] and 0 < len(order) <= 3,
              'The independent capped ledger must have one serial load per admitted arm.')
        check(all(row['state'] in {'succeeded', 'failed', 'cancelled'} for row in attempts),
              'A capped target load is still active; wait for its sealed receipts.')
        timed = [row for row in attempts if row.get('started') is not None]
        check(all(row.get('ended') is not None and row['started'] <= row['ended'] for row in timed)
              and all(row.get('started') is not None or row['state'] == 'cancelled' for row in attempts),
              'The capped ledger has no completed timing for a load.')
        check(all(before['ended'] <= after['started'] for before, after in zip(timed, timed[1:])),
              'The independent capped loads overlapped.')
        result = {}
        for attempt in attempts[1:]:
            arm = attempt['request']['arm']
            observations = [row for row in ledger['observations'] if row['kind'] == 'capped_run'
                            and row['values'].get('attempt_id') == attempt['attempt_id']]
            check(len(observations) <= 1, 'A capped attempt has ambiguous native receipts.')
            if not observations:
                result[arm] = dict(attempt=attempt, observation={}, files={})
                continue
            observation = observations[0]
            native = observation['values']
            refs = observation['source_artifacts']
            request = native.get('request') or {}
            # The admission contains the sealed delivery identity; these are not free-form request arguments.
            identities = dict(request_id=request_id, package_id=package_id, delivery_check_id=delivery['obs_id'])
            check(native.get('recipe') == attempt['request'].get('recipe') == RECIPE
                  and observation.get('host_run', {}).get('module') == 'jiuwenswarm.factory.capped_run'
                  and observation['host_run'].get('attempt_id') == attempt['attempt_id']
                  and request.get('arm') == arm and request == attempt['request']
                  and all(request.get('delivery', {}).get(key) == value for key, value in identities.items())
                  and ((native.get('outcome') == 'ok') == (attempt['state'] == 'succeeded')),
                  'A native capped receipt belongs to an unrelated or incomplete target admission.')
            files = {}
            for name in ARTIFACTS:
                ident = f"run-{attempt['attempt_id'][:12]}-{name}"
                if ident not in refs:
                    continue
                metadata = store.read_artifact(LAB_TASK, ident)
                check(metadata['size'] <= MAX_ARTIFACT, 'Native lab file exceeds the report export bound: ' + name)
                raw = store.artifact_bytes(LAB_TASK, ident)
                check(len(raw) == metadata['size'] and sha(raw) == metadata['sha256'],
                      'The native capped job artifact changed: ' + name)
                files[name] = dict(data=raw, artifact_id=ident, sha256=metadata['sha256'], size=len(raw))
            if attempt['state'] == 'succeeded':
                receipt = native.get('result') or {}
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
