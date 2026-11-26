"""Resolve the Muse rev-8 lab configuration from the completed Factory run."""
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID

from jiuwenswarm.factory import capped_replay, node_check, taskgraph
from jiuwenswarm.factory.evidence_digest import encoded
from jiuwenswarm.factory.export import snapshot
from jiuwenswarm.factory.store import Store

TASK = 'muse-2bit-demo-r8'
PROMPT_TOKENS = {'p512': 511, 'p2048': 2047}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def one(records, description):
    require(len(records) == 1, f'Expected one {description}, found {len(records)}')
    return records[0]


def artifact(home, artifacts, artifact_id):
    item = artifacts.get(artifact_id)
    require(item and item['complete'] and 0 < item['size'] <= 2 * 2**20,
            f'Missing or oversized Factory JSON artifact {artifact_id}')
    return Store._verify_blob(home / item['location'], item['sha256'], item['size'], item['size'])


def passed_check(nodes, observations, node_id, output):
    node = nodes[node_id]
    require(node['state'] == 'done', f'Factory node {node_id} must be done before the lab')
    matching = [row for row in observations if row['kind'] == 'node_check'
                and row['values'].get('node_id') == node_id and row['values'].get('output') == output]
    require(matching, f'Missing Factory check {node_id}.{output}')
    row = matching[-1]
    check = row['values']
    require(check.get('state') == 'finished' and check.get('passed') is True and row['obs_id'] in node['evidence_ids'],
            f'Latest Factory check {node_id}.{output} must pass and be cited by its node')
    return row


def verified_plan(home, artifacts, observations, row):
    check = row['values']
    verifier = check.get('verifier') or {}
    call = verifier.get('call')
    require(verifier.get('passed') is True and verifier.get('cc') == 'engine.size_prefill_batch',
            'Batch plan must pass the engine.size_prefill_batch verifier')
    require(isinstance(call, str) and str(UUID(call)) == call, 'Batch-plan verifier call ID is invalid')
    receipt = json.loads((home / 'ccstore' / 'attempts' / call / 'receipt.json').read_bytes())
    require(receipt.get('call') == call and receipt.get('release') == verifier['release']
            and receipt.get('capability') == 'verify' and receipt.get('key') == 'node-check-' + check['key']
            and receipt.get('state') == 'succeeded' and receipt.get('outputs', {}).get('done') is True,
            'Batch-plan receipt differs from the passing node check')
    inputs = receipt['provenance']['inputs']
    key = check['key']
    require(re.fullmatch(r'[0-9a-f]{64}', key), 'Batch-plan check key is invalid')
    request = json.loads((home / 'node-checks' / key[:32] / 'request.json').read_bytes())
    identity = dict(task=TASK, node='size_prefill_batch', entry=check['entry'], records=check['diff_sha256'],
                    verifier={field: verifier[field] for field in ('cc', 'capability', 'release')},
                    inputs=inputs, reviewer=request['reviewer'])
    require(node_check._sha(identity) == key and request['refs'] == check['refs'],
            'Batch-plan verifier inputs differ from the node check request')
    claimed = inputs['plan']
    if isinstance(claimed, str) and '\n' in claimed:
        plan = json.loads(claimed)
        # The receipt preserves the exact inline input. Canonical JSON makes its digest independent of spacing.
        plan_source = {'prefill_verifier_call': call}
    else:
        require(isinstance(claimed, str) and Path(claimed).is_absolute(),
                'Batch-plan verifier must receive inline JSON or an absolute cited plan path')
        refs = set(check['refs']['evidence_ids'])
        for observation in observations:
            if observation['obs_id'] in refs:
                refs.update(observation['source_artifacts'])
        stored_path = Path(claimed).resolve()
        plan_id = one([ref for ref in sorted(refs) if ref in artifacts
                       and (home / artifacts[ref]['location']).resolve() == stored_path],
                      'cited Factory artifact at the path used by the verifier')
        plan = json.loads(artifact(home, artifacts, plan_id))
        plan_source = dict(prefill_verifier_call=call, batch_plan_artifact_id=plan_id,
                           batch_plan_artifact_sha256=artifacts[plan_id]['sha256'])
    require(isinstance(plan, dict) and plan.get('format') == 'factory.prefill-batch-plan/1'
            and plan.get('fits') is True and plan.get('prompt_tokens') == sorted(PROMPT_TOKENS.values()),
            'Batch plan must fit both lab prompts')
    batch, ubatch, cache = (plan.get(key) for key in ('batch', 'ubatch', 'moe_cache_mib'))
    require(all(type(value) is int and value > 0 for value in (batch, ubatch, cache))
            and batch >= ubatch >= max(PROMPT_TOKENS.values()), 'Invalid batch plan values for the lab')
    require(plan.get('args') == ['-b', str(batch), '-ub', str(ubatch), '--moe-cache-mib', str(cache)],
            'Batch plan args differ from the verified plan values')
    budget = plan.get('device_budget_mib')
    require(type(budget) in (int, float) and budget > 0 and int(budget) == budget and budget == inputs['device_budget_mib'],
            'Batch plan budget differs from the verifier budget')
    default = plan.get('reference') or {}
    require(all(type(default.get(field)) is int and default[field] > 0 for field in ('n_batch', 'n_ubatch')),
            'Batch plan is missing the observed default batch settings')
    return plan, {**plan_source, 'batch_plan_sha256': hashlib.sha256(encoded(plan)).hexdigest()}


def resolve(home, task_id):
    require(task_id == TASK, f'Factory lab task must be {TASK}')
    home = Path(home).expanduser().resolve()
    records = snapshot(home, task_id)
    nodes = {node['node_id']: node for node in taskgraph.from_records(records)['nodes']}
    observations = records['observations']
    artifacts = {item['artifact_id']: item for item in records['artifacts']}
    attempts = {item['attempt_id']: item for item in records['attempts']}
    delivery = passed_check(nodes, observations, 'deliver_to_lab', 'lab_request')['values']['found']
    image = passed_check(nodes, observations, 'build_image', 'image')['values']['found']
    prefill = passed_check(nodes, observations, 'size_prefill_batch', 'batch_plan')
    require(nodes['requant_2bit']['state'] == 'done', 'Factory node requant_2bit must be done before the lab')

    build_id, image_id = image['build_attempt_id'], image['image_id']
    build = attempts[build_id]
    require(build['state'] == 'succeeded' and build['kind'] == 'build'
            and build['request'].get('node_id') == 'build_image' and build['request'].get('verify_image') is True,
            'Image must come from the successful verified build_image attempt')
    receipt = json.loads(artifact(home, artifacts, build_id + ':receipt'))
    image_check = receipt.get('image_check') or {}
    require(receipt.get('image_id') == image_id and re.fullmatch(r'sha256:[0-9a-f]{64}', image_id)
            and image_check.get('artifact_id') == build_id + ':image-check',
            'Image check and immutable ID must come from the build receipt')
    checked = json.loads(artifact(home, artifacts, image_check['artifact_id']))
    digest = receipt.get('executable_sha256')
    require(re.fullmatch(r'[0-9a-f]{64}', digest or '') and checked.get('format') == 'factory.image-check/1'
            and checked.get('status') == 'passed' and checked.get('image_id') == image_id
            and checked.get('executable_sha256') == digest and checked.get('source_commit') == build['request']['source']['commit']
            and image_check.get('sha256') == artifacts[image_check['artifact_id']]['sha256'],
            'Image check does not verify the build identity and executable digest')

    replay_row = one([row for row in observations if row['kind'] == 'capped_run'
                      and row['values'].get('node_id') == 'requant_2bit' and row['values'].get('recipe') == 'quantize'
                      and row['values'].get('outcome') == 'ok' and row['values'].get('replayed_from')],
                     'successful quantize replay in this run')
    replay_id = replay_row['values']['attempt_id']
    replay = attempts[replay_id]
    require(replay['kind'] == 'pack_replay' and replay['state'] == 'succeeded'
            and replay['request'].get('node_id') == 'requant_2bit', 'Quantize replay attempt did not succeed')
    pack = replay_row['values']['result']
    manifest_id = f'run-{replay_id[:12]}-pack-manifest.json'
    require(manifest_id in replay_row['source_artifacts'], 'Quantize replay did not attach its verified pack manifest')
    model, manifest = Path(pack['first_shard']), Path(pack['manifest'])
    require(manifest == capped_replay.manifest_path(model), 'Quantize replay named the wrong pack manifest')
    _, manifest_digest = capped_replay._manifest_rows(model, manifest)
    require(manifest_digest == pack['manifest_sha256'] == hashlib.sha256(artifact(home, artifacts, manifest_id)).hexdigest(),
            'Pack manifest changed since Factory verification')

    package = json.loads(artifact(home, artifacts, 'lab-package:' + delivery['package_id']))
    subjects = list(package['subjects'].values())
    require(package['origin'] == {'task_id': task_id, 'node_id': 'deliver_to_lab'}
            and any(s.get('kind') == 'container_image' and s.get('build_attempt_id') == build_id
                    and s.get('identity', {}).get('id') == image_id for s in subjects),
            'The accepted lab package does not ship this run’s verified image')
    require(any(s.get('payload', {}).get('artifact_id') == manifest_id
                and s['payload'].get('sha256') == manifest_digest for s in subjects),
            'The accepted lab package does not attach the verified 2-bit manifest artifact')

    plan, plan_source = verified_plan(home, artifacts, observations, prefill)
    identity = dict(factory_task_id=task_id, lab_package_id=delivery['package_id'], lab_request_id=delivery['request_id'],
                    build_attempt_id=build_id, image_id=image_id, llama_server_sha256=digest,
                    source_commit=checked['source_commit'], pack_replay_attempt_id=replay_id,
                    pack_manifest_artifact_id=manifest_id, pack_manifest_sha256=manifest_digest,
                    prefill_check_id=prefill['obs_id'], **plan_source)
    common = dict(image=image_id, expect_image_id=image_id, expect_sha256=digest, model=str(model), cache_mib=plan['moe_cache_mib'])
    arms = {'B': common, 'P': dict(common, args=plan['args'][:4])}
    return identity, plan, arms
