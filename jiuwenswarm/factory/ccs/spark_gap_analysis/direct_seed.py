"""Admission and paired estimates for the same-budget direct seed diagnostic."""
import hashlib
import json
import re

from early_bracket import PROMPTS, check_requests, check_server, reject_if, residency_identity, timestamp
from residency_speed import boundaries, captured_log, paired_results, server_counters, steady_order, trends

BUDGET = 30720
ARMS = ('A+', '02b-mmap', '02b-direct')
MODES = ('equivalent-stock', 'off', 'on')
PROFILE = 'expert_weight_cache_native_profile:'
DIRECT = 'expert_weight_cache_direct_seed:'
PROFILE_GATE = 'LLAMA_EXPERT_CACHE_NATIVE_PROFILE'
PROFILE_PATH = 'LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH'
DIRECT_GATE = 'LLAMA_EXPERT_CACHE_DIRECT_SEED'
NOMINATION = re.compile(
    r'group=(\d+) layer=(\d+) rank=(\d+) expert=(\d+) admitted=([01]) '
    r'reason=(\w+) slot=(-?\d+) complete_charge=(\d+)'
)


def single(log, marker):
    found = re.findall(re.escape(marker) + r' ([^\r\n]+)', log)
    reject_if(len(found) != 1, 'Expected exactly one ' + marker)
    fields = dict(re.findall(r'\b(\w+)=([\w-]+)', found[0]))
    return {key: int(value) if value.isdigit() else value for key, value in fields.items()}


def admissions(log, profile):
    found = re.findall(re.escape(PROFILE + ' nomination ') + r'([^\r\n]+)', log)
    nominated = {(layer['layer'], rank): expert for layer in profile['layers']
                 for rank, expert in enumerate(layer['expert_ids'])}
    rows, experts, slots = [], set(), set()
    for line in found:
        match = NOMINATION.fullmatch(line)
        reject_if(not match, 'Invalid full nomination and slot receipt')
        group, layer, rank, expert, admitted, reason, slot, charge = match.groups()
        group, layer, rank, expert, admitted, slot, charge = map(int, (group, layer, rank, expert, admitted, slot, charge))
        key = (layer, expert)
        reject_if(nominated.get((layer, rank)) != expert or not (0 <= expert < 384 and charge > 0) or key in experts,
                  'Nomination differs from the frozen profile or is repeated')
        experts.add(key)
        if admitted:
            reject_if(slot < 0 or (group, slot) in slots, 'Real profile slot missing or reused')
            slots.add((group, slot))
            rows.append(dict(group=group, layer=layer, rank=rank, expert=expert, slot=slot, charge=charge))
    reject_if(len(found) != 40 * 192 or not rows, 'Frozen 192-nomination profile incomplete')
    return rows


def seed_ledger(log, mode, scope, product, profile, reference):
    reject_if(PROFILE + ' inactive ' in log, 'Profile treatment declined before runtime admission')
    rows = admissions(log, profile)
    active = single(log, PROFILE + ' active')
    stats = single(log, PROFILE + ' stats')
    direct = mode == 'on'
    label = 'direct' if direct else 'mmap'
    budget = BUDGET * 1024**2
    activation = scope['activation']['value']
    reject_if(active['seed_source'] != label or active['policy'] != 'stock_evictable' or active['reverse_rank'] != 1 or
              active['seeds'] != len(rows) or not 0 < active['initial_h2d_bytes'] <= active['charged_bound'] <= budget or
              not active['init_us'] or stats['active'] != 1 or stats['demand_source'] != 'mmap' or
              any(stats[key] != active[key] for key in ('seeds', 'init_us', 'charged_bound')) or
              stats['planned_seed_payload_bytes'] != active['initial_h2d_bytes'] or
              activation['sha256'] != product['profile_sha256'] or activation['marker'] not in log or
              activation['seed_source'] != label,
              'Active seed quantities, profile digest, startup source or final bank ledger disagree')
    if direct:
        ledger = single(log, DIRECT + ' stats')
        payload = active['initial_h2d_bytes']
        reject_if(ledger['state'] != 'complete' or ledger['scope'] != 'startup_seed_payload' or
                  ledger['failures'] != 0 or ledger['fallback_count'] != 0 or
                  any(ledger[k] != payload for k in ('planned_payload_bytes', 'direct_payload_bytes', 'uploaded_payload_bytes')) or
                  not ledger['requested_io_bytes'] == ledger['returned_io_bytes'] == payload + ledger['alignment_overhead_bytes'] or
                  ledger['alignment_overhead_bytes'] < 0 or ledger['staging_bytes'] != 1024**2 or
                  not (0 < ledger['files'] <= 6 and 0 < ledger['calls'] and 0 < ledger['elapsed_us'] and
                       0 < ledger['read_alignment_max'] <= 65536 and 0 < ledger['memory_alignment_max'] <= 65536) or
                  activation['direct_seed_stats'] not in log,
                  'Direct launch lacks completed exact I/O and upload counters')
    else:
        reject_if(DIRECT in log or activation.get('direct_seed_stats'), 'Direct I/O engaged in the mmap control')
        ledger = None
    return dict(source=label, active=active, shutdown=stats, direct_io=ledger, admitted_slots=rows,
                activation=reference(scope['activation']))


def check_design(expected, profile):
    stock, buffered, direct = expected
    buffered_gates = buffered['gates']
    reject_if(stock['gates'] or stock['build_receipt'] is not None or
              set(buffered_gates) != {PROFILE_GATE, PROFILE_PATH} or buffered_gates[PROFILE_GATE] != '1' or
              not buffered_gates[PROFILE_PATH] or direct['gates'] != buffered_gates | {DIRECT_GATE: '1'} or
              not buffered['build_receipt'] or direct['build_receipt'] != buffered['build_receipt'] or
              any(row['profile_sha256'] != profile['sha256'] for row in (buffered, direct)),
              'Expected stock and exact same-binary buffered/direct gate contracts')
    argv = stock['command'][1:]
    for flag, value in (('-lm', 'mmap'), ('--moe-cache-mib', str(BUDGET)), ('--moe-cache-cpu-share', '0')):
        reject_if(argv.count(flag) != 1 or argv[argv.index(flag)+1:argv.index(flag)+2] != [value],
                  'Wrong fixed 30 GiB native bank deployment')
    reject_if(argv.count('--cpu-moe') != 1 or any(row['command'][1:] != argv for row in expected[1:]),
              'Three direct-seed LAB arms require the same CPU MoE launch flags')


def analyze(evidence, eligible, reference, positive):
    schedule = steady_order()
    prompts = {p['target_tokens_including_template']: p['prompt_sha256'] for p in evidence['prompts']['value']['prompts']}
    reject_if(set(prompts) != set(PROMPTS) or len(evidence['scopes']) != len(ARMS) or len(evidence['expected']) != len(ARMS),
              'Expected three complete arms and both fixed prompts')
    check_design(evidence['expected'], evidence['profile'])
    after = evidence['scopes'][0]['conditioning']['value']['after']
    fingerprints = {name: residency_identity(after, name) for name in ('llama', 'strata')}
    index = evidence['model_identity']['value']['files']
    reject_if([(f['path'], f['identity']['size'], f['identity']['mtime_ns']) for f in after['views']['llama']['files']] !=
              [(f['path'], f['size'], f['mtime_ns']) for f in index], 'GGUF source fingerprint differs from the model receipt')
    records, previous, runtime = [], None, None
    for arm, mode, scope, expected in zip(ARMS, MODES, evidence['scopes'], evidence['expected'], strict=True):
        label, began, ready, ended, result = check_server(scope, mode, 'C3', expected, reference, window='speed')
        conditioning = scope['conditioning']['value']
        start = scope['start']['value']
        reject_if(previous is not None and (timestamp(conditioning['before']['started']) <= previous or began <= previous),
                  'Source resets or launches overlap')
        reject_if(scope['quiet']['value']['mem_available_gib'] < 110 or
                  conditioning['regions_sha256'] != evidence['regions']['sha256'] or
                  any(residency_identity(conditioning[state], view) != fp
                      for view, fp in fingerprints.items() for state in ('before', 'after')) or
                  any(m['estimated_resident_fraction'] != 0 for view in conditioning['after']['views'].values()
                      for m in view['total'].values()),
                  'Matched quiet cold source sampling departed from the admitted geometry')
        previous = ended
        settings = (result['effective_settings'], result['runtime_environment'])
        if runtime is None:
            runtime = settings
        reject_if(settings != runtime, 'Effective server settings differ apart from the two profile gates')
        reject_if(scope['load']['value']['native_build_receipt'] != expected['build_receipt'],
                  'Ready receipt names a different build')
        log = captured_log(scope['log'])
        # Reuse verified physical bank parsing for all arms. Its profile-free
        # view removes only the independently verified profile marker lines.
        native_log = log if not expected['gates'] else '\n'.join(
            line for line in log.splitlines() if PROFILE not in line and DIRECT not in line)
        counters = server_counters(native_log, 'equivalent-stock', BUDGET, scope, expected, reference)
        if not expected['gates']:
            reject_if(DIRECT in log, 'Direct marker appeared in A+')
        seed = seed_ledger(log, mode, scope, expected, evidence['profile']['value'], reference) if mode != 'equivalent-stock' else None
        protocol = scope['protocol']['value']
        reject_if(protocol['schema'] != 'spark-cold-steady/1' or protocol['arm'] != label or protocol['view'] != 'llama' or
                  protocol['source_reset'] != 'file-specific DONTNEED' or protocol['regions_sha256'] != evidence['regions']['sha256'] or
                  protocol['warmups_per_size'] != 3 or protocol['measured_per_size'] != 5 or protocol['ordered_requests'] != schedule,
                  'Scope departed from the frozen 16-position protocol')
        requests = [dict(row, discard=row['phase'] == 'warmup', residency=True) for row in schedule]
        samples, hashes = check_requests(scope, label, ready, ended, prompts, fingerprints['llama'],
                                         eligible, reference, positive, protocol=requests)
        reject_if(hashes != scope['probe']['value']['greedy_hashes'], 'Completed probe output hashes differ')
        for pos, sample, row in zip(schedule, samples, scope['requests'], strict=True):
            phases = boundaries(row, scope['scope']['value']['pid'])
            file_bytes = row['residency']['value']['scope_accounting']['stat_bytes']['file']
            reject_if(type(file_bytes) is not int or file_bytes < 0, 'Invalid scope file bytes')
            sample.update(position=pos['position'], pair=pos['pair'], phase=pos['phase'], scope_file_bytes=file_bytes,
                          greedy_hashes=[row[k]['sha256'] for k in ('output', 'reasoning')], **phases)
        reject_if(any(s['process'] != samples[0]['process'] for s in samples), 'Engine identity changed during one launch')
        result.update(role=arm, binary_sha256=start['binary_sha256'], source_commit=expected['source_commit'],
                      protocol=reference(scope['protocol']), samples=samples, steady_trend=trends(samples),
                      greedy_hashes=hashes, seed=seed, **counters)
        records.append(result)
    aplus, buffered, direct = records
    reject_if(len({(r['native_bank']['allocated_mib'], r['native_bank']['host_experts_mib']) for r in records}) != 1 or
              buffered['binary_sha256'] != direct['binary_sha256'] or buffered['source_commit'] != direct['source_commit'] or
              buffered['seed']['admitted_slots'] != direct['seed']['admitted_slots'] or
              buffered['seed']['active']['initial_h2d_bytes'] != direct['seed']['active']['initial_h2d_bytes'] or
              not all(row['greedy_hashes'] == aplus['greedy_hashes'] for row in records),
              'Actual native bank, exact admitted slots/bytes, ELF, or greedy parity differs')
    residency = evidence['expert_classes']
    joined = residency['value']
    expected_ids = [list(key) for key in sorted((row['layer'], row['expert']) for row in direct['seed']['admitted_slots'])]
    reject_if(joined['admitted_layer_expert_ids'] != expected_ids or
              joined['startup_upload_bytes'] != direct['seed']['active']['initial_h2d_bytes'] or
              set(joined['scopes']) != set(ARMS),
              'Known-source-page labels differ from actual seed IDs or source bytes')
    for role, scope in zip(ARMS, evidence['scopes'], strict=True):
        values = joined['scopes'][role]
        expected_snapshots = [scope['conditioning'], *(row['residency'] for row in scope['requests'])]
        expected_labels = ['post-conditioning', 'post-ready', *(row['path'] for row in schedule[1:])]
        reject_if([reference(row) for row in values] != [reference(row) for row in expected_snapshots] or
                  [row['label'] for row in values] != expected_labels,
                  'Seeded source-page classes differ from sampled receipt hashes')
    comparisons = [dict(candidate=a['role'], control=b['role'], **paired_results(a, b))
                   for a, b in ((direct, buffered), (direct, aplus), (buffered, aplus))]
    for row in (buffered, direct):
        slots = row['seed'].pop('admitted_slots')
        serialized = json.dumps(slots, sort_keys=True, separators=(',', ':')).encode()
        row['seed']['admitted_slots_sha256'] = hashlib.sha256(serialized).hexdigest()
    return dict(mode=evidence['mode'], budget_mib=BUDGET, scopes=records, comparisons=comparisons,
                exact_greedy_parity=True, hot_other_residency=reference(residency),
                limitations=['One fresh launch per arm. Position-paired ranges do not establish between-launch repeatability.',
                             'Post-ready residency samples describe CPU file-cache pages by initial seed membership.',
                             'Direct startup I/O changes startup payload source only. Stock demand and inference fallbacks can use mmap.'])
