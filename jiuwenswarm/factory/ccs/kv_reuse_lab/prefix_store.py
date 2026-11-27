"""Factory-stage checks for a prefix-store image derived from the measured AQB arm."""
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median


FLAGS = ['--swa-full', '--ctx-checkpoints', '32']
MEMORY_CAP = '96G'
DEVICE_BUDGET_MIB = 110000
PLACEMENT = {'placement_share_0': 0, 'placement_share_025': 0.25, 'placement_share_05': 0.5}
SOURCES = {
    'image_receipt', 'image_check', 'pack_manifest', 'batch_plan', 'aqb_load', 'aqb_speed',
    'aqb_ttft', 'phase0b', 'phase0b_log', *PLACEMENT,
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def config_text(config):
    return json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def read_pinned(record):
    path = Path(record['path'])
    require(path.is_absolute() and path.is_file() and path.stat().st_size <= 32 * 2**20,
            'Expected a small pinned evidence file: ' + str(path))
    data = path.read_bytes()
    require(digest(data) == record['sha256'], 'Evidence digest differs: ' + str(path))
    return data


def verify_pack(pack, manifest):
    location = Path(pack['manifest'])
    actual = read_pinned(dict(path=str(location), sha256=pack['manifest_sha256']))
    require(json.loads(actual) == manifest, 'The runtime pack and retained manifest differ')
    first = Path(pack['first_shard'])
    stem = re.fullmatch(r'(.*)-00001-of-(\d{5})\.gguf', first.name)
    require(stem and first.parent == location.parent and first.is_absolute(), 'Invalid runtime pack path')
    files = manifest['files']
    count = pack['shard_count']
    require(type(count) is int and count == int(stem[2]) == len(files) and 1 <= count <= 128,
            'Manifest and runtime pack shard counts differ')
    require(files[0]['sha256'] == pack['first_shard_sha256'], 'First shard pin differs from the manifest')
    for index, entry in enumerate(files, 1):
        name = f'{stem[1]}-{index:05d}-of-{count:05d}.gguf'
        path = first.with_name(name)
        require(entry['name'] == name and re.fullmatch(r'[a-f0-9]{64}', entry['sha256'])
                and path.is_file() and path.stat().st_size == entry['bytes'],
                'Shard identity or byte count differs: ' + name)
        with path.open('rb') as stream:
            require(stream.read(4) == b'GGUF', 'Shard header differs: ' + name)
    require(manifest['bytes'] == pack['bytes'] == sum(item['bytes'] for item in files),
            'Total pack bytes differ')


def verify_pins(spec):
    require(isinstance(spec, dict) and set(spec) == SOURCES, 'Required AQB and Phase 0 evidence pins differ')
    evidence = {name: json.loads(read_pinned(ref)) for name, ref in spec.items() if name != 'phase0b_log'}
    read_pinned(spec['phase0b_log'])
    receipt, check = evidence['image_receipt'], evidence['image_check']
    load, speed = evidence['aqb_load'], evidence['aqb_speed']
    identity = load['factory_provenance']
    require(load['status'] == 'complete' and speed['status'] == 'completed'
            and load['load']['id'] == speed['leg']['id'] == '3'
            and all(speed['identity'][key] == identity[key] for key in ('image_id', 'llama_server_sha256', 'pack_manifest_sha256'))
            and speed['identity']['pack_first_shard'] == load['pack']['first_shard']
            and speed['identity']['engine_source_commit'] == identity['source_commit'],
            'Expected completed AQB load 3 receipts')
    require(receipt['image_id'] == check['image_id'] == identity['image_id']
            and receipt['executable_sha256'] == check['executable_sha256'] == identity['llama_server_sha256']
            and receipt['image_check']['sha256'] == spec['image_check']['sha256']
            and check['source_commit'] == identity['source_commit'] and check['status'] == 'passed',
            'AQB image and offline executable identity differ')
    require(check['executable'] == '/opt/llamacpp/llama-server', 'Unexpected executable in AQB image')
    batch = evidence['batch_plan']
    semantic_digest = digest(json.dumps(batch, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())
    require(semantic_digest == identity['batch_plan_sha256'] and batch['fits'] is True
            and batch['device_budget_mib'] == DEVICE_BUDGET_MIB
            and batch['batch'] == load['load']['batch'] and batch['ubatch'] == load['load']['ubatch'],
            'AQB prefill plan differs from the accepted plan or loaded batches')
    pack = load['pack']
    require(spec['pack_manifest']['sha256'] == pack['manifest_sha256'] == identity['pack_manifest_sha256'],
            'AQB pack manifest identity differs')
    verify_pack(pack, evidence['pack_manifest'])
    require(evidence['aqb_ttft']['source_sha256'] == spec['aqb_speed']['sha256'],
            'AQB TTFT sidecar does not derive from the pinned speed rows')
    return dict(format='factory.r9-pinned-inputs/1', evidence=spec, identity=identity, pack=pack,
                shard_verification='pinned-manifest-hashes, sizes and GGUF headers')


def launch_args(load, first_shard):
    argv = load['argv']
    binary = next(i for i, arg in enumerate(argv) if arg.endswith('/llama-server'))
    args = argv[binary + 1:]
    require('MemoryMax=96G' in argv[:binary] and 'MemorySwapMax=0' in argv[:binary]
            and args[:2] == ['-m', first_shard], 'Expected capped AQB launch with the pinned pack')
    wrapper = args.index('-fitt')
    require(args[wrapper + 2:wrapper + 5] == ['--host', '127.0.0.1', '--port']
            and args[wrapper + 6:] == ['-lv', '4'],
            'Unexpected dynamic wrapper arguments in recorded launch')
    return args[2:wrapper]


def device_budget(observed, reference):
    components = observed['device_mib']
    fields = {'model', 'kv', 'moe_cache', 'compute', 'host_compute'}
    require(set(components) == fields and set(reference) == fields
            and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in components.values()),
            'Invalid measured allocation breakdown')
    require(all(components[k] == reference[k] for k in ('model', 'moe_cache')),
            'Model or expert cache allocation differs from AQB')
    # GB10 allocations share one pool. Count host compute once and leave the
    # live cgroup cap as a separate enforcement control for the runtime.
    total = round(sum(components.values()), 2)
    require(total <= DEVICE_BUDGET_MIB, 'Prefix-store settings exceed the device budget')
    return dict(cap=MEMORY_CAP, swap_cap=0, device_budget_mib=DEVICE_BUDGET_MIB,
                phase0b_components_mib=components, phase0b_accounted_mib=total,
                headroom_mib=round(DEVICE_BUDGET_MIB - total, 2),
                aqb_components_mib=reference, kv_delta_mib=round(components['kv'] - reference['kv'], 2))


def plan(pinned_inputs):
    spec = pinned_inputs['evidence']
    require(verify_pins(spec) == pinned_inputs, 'Pinned AQB inputs changed')
    load = json.loads(read_pinned(spec['aqb_load']))
    speed = json.loads(read_pinned(spec['aqb_speed']))
    ttft = json.loads(read_pinned(spec['aqb_ttft']))
    trial = json.loads(read_pinned(spec['phase0b']))
    log = read_pinned(spec['phase0b_log']).decode()
    pack = pinned_inputs['pack']
    identity = pinned_inputs['identity']
    base_args = launch_args(load, pack['first_shard'])
    candidate_args = launch_args(trial, pack['first_shard'])
    require(trial['status'] == 'complete' and trial['identity'] == identity and trial['pack'] == pack
            and trial['memory_cap'] == trial['gate']['cap'] == MEMORY_CAP and trial['gate']['ok'] is True
            and trial['device_budget_mib'] == DEVICE_BUDGET_MIB and candidate_args == base_args + FLAGS,
            'Phase 0b launch differs from the approved treatment or pins')
    baseline = [item for item in speed['rows'] if item['request'] in ('p512', 'p2048')]
    require(baseline and all(item['cache_prompt'] is False for item in baseline),
            'AQB control did not establish cache_prompt=false for both cells')
    quiet_ttft = [item['derived_ttft_ms'] for item in ttft['rows'] if item['request'] == 'p2048'
                  and item['state'] == 'warm' and item['quiet_status'] == 'accepted']
    require(quiet_ttft and all(type(ms) in (int, float) and math.isfinite(ms) and ms > 0 for ms in quiet_ttft),
            'AQB lacks quiet accepted warm p2048 timing')
    aqb_ttft = median(quiet_ttft)
    prime, follow = trial['rows']
    cached = follow['cached_tokens']
    evidence_lines = follow['server_log_evidence']
    first = next((line for line in evidence_lines if 'cached n_tokens =' in line), '')
    pattern = r'cached n_tokens = ' + str(cached) + r','
    require(all(item['cache_prompt'] is True and item['generated_tokens'] == 32 for item in trial['rows'])
            and type(cached) is int and 0 < cached < follow['tokenized_prompt_tokens']
            and re.search(pattern, first) and first in log.splitlines()
            and 'selected slot by LCP similarity' in log and 'using full-size SWA cache' in log
            and 'context checkpoints enabled, max = 32' in log,
            'Phase 0b log does not substantiate the follow-up cache reuse or selected settings')
    require(0 < follow['derived_ttft_ms'] <= 0.75 * aqb_ttft,
            'Phase 0b did not clear a 25 percent improvement over published AQB TTFT')
    require(all(trial['observed'][key] == load['observed'][key] for key in ('n_ctx', 'n_batch', 'n_ubatch')),
            'Phase 0b effective context or batch settings differ from AQB')
    budget = device_budget(trial['observed'], load['observed']['device_mib'])
    placement = []
    for key, share in PLACEMENT.items():
        row = json.loads(read_pinned(spec[key]))
        require(row['status'] == 'complete' and row['identity'] == identity and row['pack'] == pack
                and row['cache_prompt'] is False and row['generated_tokens'] == 32 and row['share'] == share,
                'Phase 0 placement evidence differs from the pinned AQB run')
        placement.append(dict(share=share, quiet_status=row['quiet']['status'], evidence=spec[key],
                              ttft_ms=row['derived_ttft_ms'], decode_tokens_per_second=row['decode_tokens_per_second'],
                              total_ms=row['request_total_ms']))
    baseline_placement = placement[0]
    require(baseline_placement['quiet_status'] == 'accepted'
            and not any(row['quiet_status'] == 'accepted'
                        and (row['decode_tokens_per_second'] > baseline_placement['decode_tokens_per_second']
                             or row['total_ms'] < baseline_placement['total_ms']) for row in placement[1:]),
            'Phase 0 does not support recording placement as a refused candidate')
    base_config = dict(format='factory.r9-launch/1', args=base_args, request=dict(cache_prompt=False))
    config = dict(format='factory.r9-launch/1', args=candidate_args, request=dict(cache_prompt=True))
    config_sha = digest(config_text(config).encode())
    build_request = dict(
        target='spark-gb10', tag='factory/llamacpp:muse-aqbc-r9', deadline_s=300,
        config_image=dict(base_image_id=identity['image_id'], executable_sha256=identity['llama_server_sha256'],
                          launch_config=config),
    )
    return dict(
        format='factory.r9-prefix-plan/1', atlas='state.prefix_store', pinned_inputs=pinned_inputs, pack=pack,
        phase0=dict(status='refused', reason='No eligible alternative beat the share-zero control', rows=placement),
        phase0b=dict(status='engaged', evidence=spec['phase0b'], server_log=spec['phase0b_log'],
                     first_ttft_ms=prime['derived_ttft_ms'], follow_up_ttft_ms=follow['derived_ttft_ms'],
                     cached_tokens=cached, prompt_tokens=follow['tokenized_prompt_tokens'], cache_log_line=first,
                     aqb_p2048_warm_ttft_ms=aqb_ttft, quiet_status=follow['quiet']['status'],
                     eligibility_reasons=follow['quiet']['reasons']),
        memory=budget, aqb_launch_config=base_config, launch_config=config, launch_config_sha256=config_sha,
        diff=dict(append_args=FLAGS, request=dict(cache_prompt=dict(before=False, after=True))),
        build_request=build_request,
    )


def verify_factory_stage(prefix_plan, build_record):
    require(plan(prefix_plan['pinned_inputs']) == prefix_plan, 'Prefix plan or AQB inputs changed')
    expected = prefix_plan['build_request']['config_image']
    check = build_record['image_check']
    image = build_record['image']
    config = expected['launch_config']
    env = 'FACTORY_LAUNCH_CONFIG=' + config_text(config)
    require(build_record['status'] == 'success' and build_record['mode'] == 'config_image'
            and build_record['base_image_id'] == expected['base_image_id']
            and image['Id'] != expected['base_image_id'] and re.fullmatch(r'sha256:[a-f0-9]{64}', image['Id'])
            and check['image_id'] == image['Id'] and check['status'] == 'passed',
            'Builder did not return a distinct, checked derivative image')
    base = build_record['base_image']
    require(base['Id'] == expected['base_image_id'] and image['RootFS'] == base['RootFS']
            and image['Config'] == dict(base['Config'], Cmd=config['args'], Env=[*base['Config']['Env'], env])
            and check['executable_sha256'] == expected['executable_sha256']
            and check['launch_config_sha256'] == prefix_plan['launch_config_sha256'],
            'Image filesystem, executable or config diff differs from the approved plan')
    return dict(format='factory.r9-factory-stage/1', status='passed', passed=True, done=True,
                image_id=image['Id'], base_image_id=base['Id'], executable_sha256=check['executable_sha256'],
                pack=prefix_plan['pack'], launch_config=config,
                launch_config_sha256=prefix_plan['launch_config_sha256'],
                checks=dict(same_layers=True, unchanged_binary=True, pinned_pack=True,
                            approved_config_diff=prefix_plan['diff'], memory=prefix_plan['memory']))
