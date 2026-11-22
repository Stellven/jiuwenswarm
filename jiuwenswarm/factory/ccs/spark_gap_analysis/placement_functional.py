"""Validate stock-equivalent C2 placement and functional request evidence."""
from base64 import b64decode
import hashlib
import re

from early_bracket import PROMPTS, check_server, reject_if, timestamp

MODES = ('equivalent-stock', 'off', 'on')
PROJECTIONS = ('gate', 'down', 'up')
EXPERT = re.compile(r'blk\.(\d+)\.ffn_(gate|down|up)_exps\.weight')
ASSIGNMENT = re.compile(
    r'weight_placement_planner: assignment name="([^"]+)" planned=(\S+) actual=(\S+) bytes=(\d+)$',
    re.MULTILINE,
)
FAMILY = 'weight_placement_planner:'


def captured_text(entry):
    content = b64decode(entry['raw_b64'], validate=True)
    reject_if(hashlib.sha256(content).hexdigest() != entry['sha256'],
              'Captured text does not reproduce its evidence digest')
    return content.decode(errors='replace')


def placement_readback(log, selected):
    named = [dict(name=name, planned=planned, actual=actual, bytes=int(size))
             for name, planned, actual, size in ASSIGNMENT.findall(log) if EXPERT.fullmatch(name)]
    required = {f'blk.{layer}.ffn_{projection}_exps.weight'
                for layer in range(40) for projection in PROJECTIONS}
    reject_if(len(named) != len(required) or {row['name'] for row in named} != required,
              'Candidate did not expose one actual assignment for all 120 expert projections')
    expected = {row['name']: row['bytes'] for row in selected if row['expected_buffer'] == 'CUDA0'}
    reject_if(set(expected) != {f'blk.27.ffn_{p}_exps.weight' for p in PROJECTIONS},
              'Placement controls did not pin the three layer-27 projections')
    applied = [row for row in named if row['name'] in expected]
    reject_if(any(row['planned'] != 'CUDA0' or row['actual'] != 'CUDA0' or row['bytes'] != expected[row['name']]
                  for row in applied), 'A selected tensor differs from its planned CUDA0 assignment')
    remaining = [row for row in named if row['name'] not in expected]
    reject_if(any(row['planned'] != 'stock' or row['actual'] not in ('CPU_Mapped', 'CPU') for row in remaining),
              'An unselected expert projection did not retain stock CPU placement')
    reject_if(len(re.findall(r'weight_placement_planner: active ', log)) != 1 or 'weight_placement_planner: inactive' in log or
              re.findall(r'weight_placement_planner: assignment class=expert assigned=(\d+) stock=(\d+)', log) != [('3', '117')] or
              re.findall(r'weight_placement_planner: stats assigned=(\d+) stock=\d+', log) != ['3'],
              'Placement activation, totals or orderly final counters disagree with tensor readback')
    return dict(selected=applied, other_expert_tensors=remaining, cuda_payload_bytes=sum(expected.values()))


def requests(scope, label, ready, ended, prompts, eligible, reference, positive):
    rows, previous = [], ready
    reject_if(len(scope['requests']) != len(PROMPTS), 'Expected both functional prompts')
    for item, size in zip(scope['requests'], PROMPTS):
        request, result = (item[key]['value'] for key in ('request', 'result'))
        now = timestamp(result['started'])
        reject_if(result['prompt_tokens'] != size or result['arm'] != label or result['repeat'] != 0 or
                  result['finish_reason'] != 'length' or result['timings']['predicted_n'] != 32 or
                  result['discard'] is not True or not previous <= now < ended or
                  request.get('chat_template_kwargs') != {'enable_thinking': False} or
                  not eligible(dict(request=request, result=result), prompts), 'Functional request identity, greedy settings or cache mismatch')
        phases = {'ttft_s': result['ttft_s'], 'wall_s': result['wall_s'], 'decode_tps': result['decode_tps'],
                  **{key: result['timings'][key] for key in ('prompt_ms', 'predicted_ms')}}
        hashes = [item[name]['sha256'] for name in ('output', 'reasoning')]
        reject_if(not all(map(positive, phases.values())) or hashes != [result['output_sha256'], result['reasoning_sha256']] or
                  hashes != scope['probe']['value']['greedy_hashes'][str(size)],
                  'Functional output hash or client/server phases differ from retained evidence')
        resources = item['resources']
        reject_if(resources['sha256'] != result['resource_windows_sha256'] or
                  resources['value']['schema'] != 'spark-request-resources/1' or
                  resources['value']['cgroup'] != scope['scope']['value']['cgroup'] or
                  set(resources['value']['snapshots']) != {'start', 'first_token', 'end'},
                  'Functional request resource windows do not match this scope and result')
        rows.append(dict(prompt_tokens=size, output_sha256=hashes[0], reasoning_sha256=hashes[1], **phases,
                         evidence={name: reference(value) for name, value in item.items()}))
        previous = now
    return rows


def analyze(evidence, eligible, reference, positive):
    scopes = evidence['scopes']
    reject_if(set(scopes) != set(MODES), 'Expected equivalent-stock, gate-unset and gate-enabled scopes')
    prompts = {row['target_tokens_including_template']: row['prompt_sha256']
               for row in evidence['prompts']['value']['prompts']}
    reject_if(set(prompts) != set(PROMPTS), 'Expected approved fixed-prompt manifest')
    comparisons, previous = {}, None
    for mode in MODES:
        scope = scopes[mode]
        label, began, ready, ended, row = check_server(scope, mode, 'C2', evidence['expected'][mode],
                                                      reference, window='functional')
        reject_if(previous is not None and began <= previous, 'Functional launch scopes overlapped')
        previous = ended
        log = captured_text(scope['log'])
        buffers = re.findall(r'load_tensors:\s+CUDA0 model buffer size =\s+(\d+(?:\.\d+)?) MiB', log)
        reject_if(not buffers, 'No CUDA0 model allocation in retained engine log')
        row['cuda0_model_mib'] = round(sum(map(float, buffers)), 2)
        if mode == 'on':
            row['readback'] = placement_readback(log, evidence['controls']['value']['selected'])
        else:
            row['gate_marker_silent'] = FAMILY not in log
            reject_if(not row['gate_marker_silent'], 'Gate-unset marker leaked into the control log')
        row['requests'] = requests(scope, label, ready, ended, prompts, eligible, reference, positive)
        comparisons[mode] = row
    on = comparisons['on']
    for control in MODES[:-1]:
        on[f'cuda0_delta_vs_{control}_mib'] = round(on['cuda0_model_mib'] - comparisons[control]['cuda0_model_mib'], 2)
    parity = {
        str(size): len({(row['requests'][i]['output_sha256'], row['requests'][i]['reasoning_sha256'])
                       for row in comparisons.values()}) == 1
        for i, size in enumerate(PROMPTS)
    }
    return dict(mode='c2-placement-functional', comparison=comparisons, parity=parity,
                controls=reference(evidence['controls']), prompts=reference(evidence['prompts']))
