"""Generate factory/contracts/muse-2bit-ttft-v4.json: the Muse demo with a new 2-bit pack, every node run by the factory.

Revision 6 of the Muse demo contract, from muse-q2-ttft-v3.json (make_muse_q2_preliminary.py). Two planner
changes, both the contract owner's (2026-11-25):

1. A different 2-bit pack. The Q2_K pack of Nov 24 exists already; this run makes a pack not made before:
   routed gate and up experts IQ2_XXS (2.06 bits per weight), down experts Q2_K (2.63), everything else at its
   NVFP4-pack type. The down projection is the one most sensitive to low bits, so it keeps the K-quant; the pack
   is about 12 % smaller than the Q2_K one (about 267 GB against 305 GB), which is less to stream per token.
2. Every node runs here: nothing built by hand is reused. Conversion, builds, requantization, smoke runs,
   accuracy and the routing profile run through factory.capped_runner under the memory cap.

Node ids keep their roles; names that said Q2 now say 2-bit.
"""
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = REPO / 'jiuwenswarm/factory/contracts'
TARGET = 'iq2_xxs,down=q2_k'
BYTES = [240_000_000_000, 290_000_000_000]
MIX = 'IQ2_XXS for the gate and up projections, Q2_K for down'

text = (OUT / 'muse-q2-ttft-v3.json').read_text(encoding='utf-8')
# Literal replacements, longest first; each must occur (asserted below).
REPLACE = [
    ('requant_q2', 'requant_2bit'),
    ('q2_pack_census', 'pack_2bit_census'),
    ('q2_accuracy', 'accuracy_2bit'),
    ('q2_pack', 'pack_2bit'),
    ('muse-q2-ttft-v3', 'muse-2bit-ttft-v4'),
    ('NVFP4 to Q2 requantization', 'NVFP4 to mixed 2-bit (IQ2_XXS and Q2_K) requantization'),
    ('requantized to Q2_K', f'requantized to a mixed 2-bit format ({MIX})'),
    ('a Q2_K requantization of it', f'a mixed 2-bit requantization of it ({MIX})'),
    ('E0 on the Q2_K requantized pack', 'E0 on the mixed 2-bit pack'),
    ('on the Q2_K pack', 'on the 2-bit pack'),
    ('Routed experts Q2_K instead of NVFP4', f'Routed experts {MIX}, instead of NVFP4'),
    ('Every routed expert weight of the Q2 pack is Q2_K;',
     'Every routed gate and up expert weight of the 2-bit pack is IQ2_XXS and every down expert weight Q2_K;'),
    ('routed experts to Q2_K, everything else kept at its source type',
     'routed gate and up experts to IQ2_XXS and down experts to Q2_K (the down projection is the most sensitive to '
     'low bits), everything else kept at its source type'),
    ('Every routed expert weight is Q2_K;', 'Every routed gate and up expert weight is IQ2_XXS and every down expert weight Q2_K;'),
    ('Total size between 250 and 320 GB', 'Total size between 240 and 290 GB'),
    ('the expected Q2 size', 'the expected 2-bit pack size'),
    ('acc(NVFP4) - acc(Q2)', 'acc(NVFP4) - acc(2-bit)'),
    ('One cold Q2 request on E1', 'One cold 2-bit request on E1'),
    ('about 1.4 TB when the NVFP4 and Q2 packs are both written', 'about 0.9 TB when the NVFP4 and 2-bit packs are both written'),
    ('the Q2 pack', 'the 2-bit pack'),
]
for old, new in REPLACE:
    if old not in text:
        raise SystemExit(f'not found: {old!r}')
    text = text.replace(old, new)
contract = json.loads(text)
contract['version'] = 6
leftover = [m for m in ('Q2 pack', 'acc(Q2)', 'Q2 request') if m in text]
assert not leftover, leftover

nodes = {n['node_id']: n for n in contract['extensions']['factory.node-contracts']['nodes']}
req = nodes['requant_2bit']
for v in req['verifiers']:
    v['inputs']['target'] = TARGET
    if v['output'] == 'pack_2bit':
        v['inputs']['expect_bytes_range'] = BYTES
recipe = next(o for o in req['outputs'] if o['name'] == 'recipe')
recipe['criteria'].append('Times one layer with the recipe\'s probe before the full run and records the projected '
                          'full time; the full run starts only if it fits the node time limit.')
# The measured times of this run are longer than the Q2_K run's: IQ2_XXS quantization searches a lattice per block.
req.setdefault('node_limits', {})['time_s'] = max(req.get('node_limits', {}).get('time_s', 0), 16 * 3600)

for node in nodes.values():
    eligible = node.setdefault('work', {}).setdefault('eligible_ccs', [])
    if node['kind'] in {'integrate', 'build', 'measure', 'tune'} and 'factory.capped_runner' not in eligible:
        eligible.append('factory.capped_runner')
    ceiling = node.get('authority_ceiling') or {}
    if 'effects' in ceiling and node['kind'] in {'integrate', 'build', 'measure', 'tune'}:
        ceiling['effects'] = sorted(set(ceiling['effects']) | {'process.exec', 'workspace.write'})

# A shorter lab (owner, 2026-11-25): one cold and one warm request per arm and prompt size, 32 generated tokens.
for request in contract['workload']['requests']:
    request['params']['n_predict'] = 32
contract['measurement']['metrics']['request_total_ms']['how'] = (
    'Client clock from sending the request to the last streamed token (32 generated tokens).')
protocol = contract['measurement']['protocol']
protocol['repeats'] = 1
protocol['notes'] = ('One server load per arm (A, B, C, D in that order). Per prompt size: one cold request (pack pages '
                     'evicted with posix_fadvise DONTNEED before it, reported separately) then one warm request, 32 '
                     'generated tokens each. Trimmed to keep the lab short: with a single warm request there is no '
                     'warm spread, so small differences are reported as measured, not as gains.')

# Fill the device budget with expert cache (owner, 2026-11-26: "allow a lot of the memory to be used"). Measured on
# the Q2_K lab of Nov 25 (-lv 4 logs): model 37397 MiB and KV 716 on every arm; compute 8387 MiB on arm A (NVFP4)
# against 1539 (B, C) and 2128 (D, ub 2048); MoE cache 61425. Arm A at 61440 MiB of cache already fills the
# 110000 MiB budget, the 2-bit arms left about 5 to 7 GiB unused. The budget is the limit, not the cgroup cap:
# device buffers of about 101 GiB loaded under the 96G cap, and 110000 MiB keeps the host above the 8 GiB guard.
SPB = nodes['size_prefill_batch']
SPB['objective'] = ('Size the server prefill batch so each lab prompt is prefilled in as few micro-batches as the '
                    'device budget allows, give the rest of the budget to the MoE expert cache, and check both on '
                    'capped loads of E1 with the 2-bit pack.')
plan_out = next(o for o in SPB['outputs'] if o['name'] == 'batch_plan')
plan_out['criteria'].append(
    'The plan sizes the MoE cache (--moe-cache-mib in its args) and the capped load with the planned arguments uses '
    'the device budget to within headroom plus 2 GiB; if the linear compute estimate left more, the plan is redone '
    'from that load\'s log and loaded again.')
for v in SPB['verifiers']:
    if v['output'] == 'batch_plan':
        v['inputs']['fill_moe_cache_headroom_mib'] = 2048
SPB.setdefault('bounds', {})['verifiers.batch_plan.inputs.fill_moe_cache_headroom_mib'] = 'lower'
arms = {a['id']: a for a in contract['arms']}
arms['A']['deviations'] = [
    d if '61440' not in d else
    ('One device memory budget (110000 MiB) on every arm: arm A runs --moe-cache-mib 61440 (its NVFP4 compute buffer '
     'of about 8 GiB leaves no more), arms B, C and D the larger --moe-cache-mib of the size_prefill_batch plan')
    for d in arms['A']['deviations']]
for arm in ('B', 'C', 'D'):
    arms[arm]['deviations'].append('--moe-cache-mib from the size_prefill_batch plan (device budget filled)')
nodes['deliver_to_lab']['objective'] += (' Arm A keeps --moe-cache-mib 61440; arms B, C and D take the plan\'s '
                                         '--moe-cache-mib, and only arm D its -b and -ub.')
contract['provenance']['notes'].append(
    'Revision 6 fills the device budget with expert cache (owner, 2026-11-26): the 2-bit arms take --moe-cache-mib '
    'from the size_prefill_batch plan (about 66 GiB instead of 60) under the same 110000 MiB device budget as arm A, '
    'whose NVFP4 compute buffer leaves it at 61440. Equal memory budget, not equal cache size, is the fair '
    'comparison; B against A then includes the cache room the smaller compute buffer frees.')
contract['provenance']['notes'].append(
    'Revision 6 also trims the lab protocol (owner, 2026-11-25): one warm request instead of two and 32 generated '
    'tokens instead of 128 per request, so the four arms fit in a few hours instead of a night.')
contract['provenance']['notes'].append(
    'Revision 6 (v4 file, owner decision 2026-11-25): a 2-bit pack not made before, routed experts ' + MIX +
    ', other tensors at their NVFP4-pack type (about 267 GB against 305 GB for the Q2_K pack of Nov 24), target '
    + TARGET + ' for weights.build_weight_pack_compiler; and every node runs in this run (capped runs through '
    'factory.capped_runner), reusing nothing built by hand.')

plan = {'format': 'factory.plan/1', 'planner': 'hand-written demo plan (muse-2bit-ttft, preliminary node contracts)',
        'nodes': [{'node_id': n['node_id'], 'node_contract': n['node_id'], 'depends_on': n.get('predecessors', []),
                   'title': n['objective']} for n in contract['extensions']['factory.node-contracts']['nodes']]}
(OUT / 'muse-2bit-ttft-v4.json').write_text(json.dumps(contract, indent=1) + '\n', encoding='utf-8')
(OUT.parent / 'tasks/muse-2bit-ttft-v4.plan.json').write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8')
print('wrote muse-2bit-ttft-v4', len(nodes), 'nodes')
