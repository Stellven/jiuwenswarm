#!/usr/bin/env python3
"""Publish a completed C3 cache lab through native analyze/verify capabilities."""
import argparse
from base64 import b64encode
import gzip
import json
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.deep_profile import stream_counters
from jiuwenswarm.factory.store import NotFound, Store

from import_evidence import append_once, digest, safe_bytes
from report_early_bracket import CAPSULE, STOCK, content, scope_inputs
from report_p1 import ITERATION as P1_ITERATION, TASK as DIRECT_TASK, json_bytes

ITERATION = 'spark-c3-native-cache'
REFERENCE_ITERATION = 'spark-a-s-cold-steady'
PLAN_TASK = 'spark-cache-residency-plan-01'
PLAN_ID = PLAN_TASK + ':decision:2'
LANE = 'factory-runs/star-expert_weight_cache-residency-01'
PROFILE_DIGEST = 'dd4861349970a46e9e23ebe58c39b5afb91bd1d9e4c28e960026fc375b1034da'
DIFF = {'artifact_id': 'cache-native-profile.diff',
        'sha256': '95682b4c6d8d19eaddfa66824aefbbe8ebf3208645ce078ab985471db870a281'}
VERIFY = {'artifact_id': 'cache-native-source-static-verification.json',
          'sha256': 'c923f8169616f582b1621fca5e631f345ed66b3c6f5149359e9e274ad7e906df'}
EARLY = ((30720, 'on', 'residency-speed-30720-on-01'),
         (30720, 'equivalent-stock', 'residency-speed-30720-equivalent-stock-01'))
FINAL = (
    (30720, 'stock', 'residency-speed-30720-stock-01'),
    (61440, 'on', 'residency-speed-61440-on-01'),
    (0, 'strata', 'strata-steady-fair-01'),
    (30720, 'on', 'residency-steady-30720-on-01'),
    (30720, 'equivalent-stock', 'residency-steady-30720-equivalent-stock-01'),
    (61440, 'equivalent-stock', 'residency-speed-61440-equivalent-stock-01'),
)
REFERENCE = (FINAL[0], FINAL[2])
SCREENING = FINAL[:3]
MODES = {'pilot': 'c3-warmup-pilot', 'reference': 'a-s-cold-steady',
         'screening': 'c3-screening-60', 'full': 'c3-cold-steady'}
PILOT_ORDER = ((0, 512), (0, 2048), (1, 512), (1, 2048), (2, 2048), (2, 512), (3, 512), (3, 2048))


def expected_argv(base, first, product, inventory, profile, mib, role, path):
    if role == 'strata':
        config_path = base / 'OPS/configs' / (path.name + '.json')
        config = content(config_path)
        fair = content(base / 'OPS/configs/p4-s-pass-1.json')
        fair['log'] = str(path / 'engine.log')
        fair['env']['STRATA_DS4_SLOT_DIR'] = str(path / 'ds4-slots')
        if config != fair or '--profile-readonly' not in config['args'] or config['env']['DS4_UMA_HEADROOM_GIB'] != '16':
            raise ValueError('Strata configuration differs from the frozen read-only fair profile')
        prior = content(base / 'OPS/runs/s-first-load/start.json')
        prior_engine = content(base / 'OPS/runs/s-first-load/strata-fair-provenance.json')
        argv = list(prior['command'])
        argv[argv.index('--config') + 1] = str(config_path)
        proven_env = {key: config['env'][key] for key in ('DS4_UMA_HEADROOM_GIB', 'STRATA_DS4_REUSE', 'STRATA_DS4_SLOT_DIR')}
        return dict(label='S-fair-steady', config=str(config_path), view='strata', command=argv,
                    binary_sha256=prior_engine['engine_sha256'], config_env=proven_env)
    on = role == 'on'
    executable = product['executable']['path'] if on else first['command'][0]
    argv = [executable, *first['command'][1:], '-lv', '4']
    if role != 'stock':
        argv += ['--moe-cache-mib', str(mib), '--moe-cache-cpu-share', '0']
    label = {'stock': 'A-matched', 'equivalent-stock': 'Aplus', 'on': 'C3-profile-on'}[role]
    gates = {'LLAMA_EXPERT_CACHE_NATIVE_PROFILE': '1',
             'LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH': str(profile)} if on else {}
    return dict(label=f'{label}-speed-{mib}MiB', command=argv, source_commit=product['source_commit'] if on else STOCK,
                binary_sha256=product['executable']['sha256'] if on else first['binary_sha256'],
                products_manifest_sha256=inventory, profile_sha256=PROFILE_DIGEST, gates=gates,
                library_path=str(Path(executable).parent))


def fmt_sample(phase):
    return f"{phase['process_read_bytes']/1024**2:,.3f} MiB / {phase['process_major_faults']:,}"


def format_cold(scopes, pilot=False):
    lines = [
        '## Request positions after conditioning', '',
        '| Arm | Position | Prompt tokens | TTFT | Decode tok/s | Process reads / major faults to first token | Process reads / major faults afterward |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for scope in scopes:
        for i, row in enumerate(scope.get('samples', []), 1):
            if not pilot and row['phase'] != 'warmup':
                continue
            phase = row['phases']
            lines.append(f"| {scope['arm']} | {i} | {row['prompt_tokens']} | {row['ttft_s']:.3f} s | "
                         f"{row['decode_tps']:.2f} | {fmt_sample(phase['start_to_first_token'])} | "
                         f"{fmt_sample(phase['first_token_to_end'])} |")
    return lines


def startup_rows(result):
    if result['mode'] == 'a-s-cold-steady':
        return ['## Launch and cap accounting', '',
                '| Arm | Launch to ready | Peak cgroup memory | Reclaim max events |',
                '|---|---:|---:|---:|',
                *[f"| {r['arm']} | {r['load_s']:.3f} s | {r['peak_memory_bytes']/1024**3:.2f} GiB | {r['reclaim_max']} |"
                  for r in result['scopes']]]
    lines = ['## Launch and cache admission', '',
             '| Arm | Launch to ready | Peak cgroup memory | Reclaim max events | Profile seeds | Initial upload |',
             '|---|---:|---:|---:|---:|---:|']
    declines = []
    for scope in result['scopes']:
        stats = scope.get('profile', {})
        upload = f"{stats['initial_h2d_bytes']/1e9:.3f} GB" if stats else '—'
        lines.append(f"| {scope['arm']} | {scope['load_s']:.3f} s | {scope['peak_memory_bytes']/1024**3:.2f} GiB | "
                     f"{scope['reclaim_max']} | {stats.get('seeds', '—')} | {upload} |")
        if scope['status'] == 'declined':
            declines.append(f"- {scope['arm']} declined before requests. {'; '.join(scope['reasons'])}.")
    lines.extend(['', *declines, 'The profile seeds the existing stock bank during startup. Initial seed upload is separate from demand refill traffic.', '',
                  '| Arm | Actual bank | Seed time | Demand upload | Native lookup hits / misses | Large-prefill D2D experts | Evictions |',
                  '|---|---:|---:|---:|---:|---:|---:|'])
    for scope in result['scopes']:
        bank = scope.get('native_bank')
        if bank:
            stats = scope.get('profile', {})
            seed_time = f"{stats['init_us']/1e6:.3f} s" if stats else '—'
            lines.append(f"| {scope['arm']} | {bank['allocated_mib']:.2f} MiB | {seed_time} | {bank['uploaded_mib']:.2f} MiB | "
                         f"{bank['hits']:,} / {bank['misses']:,} | {bank['large_batch_d2d_experts']:,} | {stats.get('evictions', '—')} |")
    return lines


def screening_finding(result):
    stock, c3, _ = result['scopes']
    by_size = [('512', stock['steady_trend']['512'], c3['steady_trend']['512']),
               ('2048', stock['steady_trend']['2048'], c3['steady_trend']['2048'])]
    decode = [b['decode_tps']['median'] / a['decode_tps']['median'] for _, a, b in by_size]
    ttft = [b['ttft_s']['median'] / a['ttft_s']['median'] for _, a, b in by_size]
    summary = (f"At 60 GiB, C3 decoded {decode[0]:.1f}× and {decode[1]:.1f}× as fast as A-matched "
               f"at 512 and 2048 tokens, while median time to first token rose to {ttft[0]:.1f}× and {ttft[1]:.1f}×.")
    lines = [summary, '']
    for size, _, row in by_size:
        counts = row['phase_counters']['start_to_first_token']
        lines.append(f"- At {size} prompt tokens, C3 read a median {counts['process_read_bytes']['median']/1e9:.3f} GB "
                     f"and recorded {counts['process_major_faults']['median']:,} engine major faults before the first token.")
    profile = c3['profile']
    lines += [
        '', f"C3 took {c3['load_s']:.3f} s to become ready versus {stock['load_s']:.3f} s for A-matched, "
        f"with {profile['init_us']/1e6:.3f} s in profile seeding and {profile['initial_h2d_bytes']/1e9:.3f} GB in initial upload.",
        '', f"C3 logged {profile['large_prefill_d2d_bytes']/1e12:.3f} TB of aggregate large-prefill device-to-device copies across all 16 requests. "
        'This counter measures device-local copies. The request-phase tables separately show process reads and faults.',
        '', 'Host page pressure is one possible contributor to the first-token regression. '
        'The paired A-matched comparison includes the standing native bank and the seeding policy. '
        'The pending same-budget 60-GiB A+ arm is the control for separating the profile from the stock bank.',
    ]
    return summary, lines


def report_text(result, release, residency_ref=None):
    pilot = result['mode'] == 'c3-warmup-pilot'
    reference = result['mode'] == 'a-s-cold-steady'
    opening = None
    if pilot:
        on, aplus = result['scopes']
        startup_change = on['load_s'] - aplus['load_s']
        startup = f"{abs(startup_change):.1f} seconds {'more' if startup_change >= 0 else 'less'} to become ready"
        summary = f'Both 30-GiB launches kept warming across eight request positions, and the cache profile took {startup} than stock.'
        heading = '# C3 native cache startup and warm-up pilot'
    elif reference:
        a, s = result['scopes']
        a_rate, s_rate = (r['steady_trend']['512']['decode_tps']['median'] for r in (a, s))
        summary = f'After three warmups per size, fair Strata decoded the 512-token workload at a median {s_rate:.2f} tokens per second and A-matched at {a_rate:.2f}.'
        heading = '# A-matched and fair Strata cold and post-warmup reference'
    elif result['mode'] == 'c3-screening-60':
        summary, opening = screening_finding(result)
        heading = '# C3 60-GiB interim screening'
    else:
        matched = next((row for row in result['comparisons'] if 'same-budget stock bank' in row['relation']), None)
        if matched:
            pair = matched['steady'][0]
            delta = pair['ttft_saved_s']['median']
            delta_text = f"{abs(delta):.2f} seconds {'faster' if delta >= 0 else 'slower'}"
            scope = next(r for r in result['scopes'] if r['arm'] == matched['candidate'])
            context = 'In exploratory screening across' if result.get('exploratory_cpu_overlap') else 'Across'
            summary = (f"{context} five post-warmup pairs at {scope['budget_mib']//1024} GiB, "
                       f"the seeded cache reached the first token a median {delta_text} for the 512-token prompt.")
        else:
            summary = 'The cache profile did not produce an active same-budget timing comparison.'
        heading = '# C3 native cache cold and post-warmup lab'
    lines = [heading, '', *(opening or [summary]), '', *format_cpu_exposure(result),
             *startup_rows(result), '', *format_cold(result['scopes'], pilot=pilot), '']
    lines += ['No sampled expert, Engram or dense pages were resident in either pack view immediately before each launch. Launch initialization can change residency before the first request.',
              'Process counters come from one unchanged engine PID per launch. Resource snapshots span client request start to first token and first token to stream completion. The raw analysis retains cgroup file refaults and separate host NVMe counters. Host disk activity includes any other activity on the device.', '']
    if pilot:
        a, b = result['scopes']
        lines += [f"The cache profile changed launch-to-ready by {a['load_s']-b['load_s']:+.3f} s. "
                  'Both launches used the same 30-GiB native-bank budget, with one discarded prompt per size and three further positions. '
                  'Those positions describe the warm-up curve. A separate three-warmup, five-pair lab measures later behavior.', '',
                  '| Matched position | Tokens | TTFT saved | Decode gain | Process reads avoided to first token | Major faults avoided to first token | Greedy parity |',
                  '|---:|---:|---:|---:|---:|---:|---|']
        for pair in result['matched_positions']:
            parity = 'matched' if pair['greedy_parity'] else 'diverged'
            lines.append(f"| {pair['position']} | {pair['prompt_tokens']} | {pair['ttft_saved_s']:+.3f} s | {pair['decode_gain_tps']:+.2f} tok/s | "
                         f"{pair['read_bytes_saved_to_first_token']/1e9:+.3f} GB | {pair['major_faults_avoided_to_first_token']:+,} | {parity} |")
        lines.append('')
    else:
        lines += format_steady(result)
        if residency_ref:
            lines += format_residency(result, residency_ref)
        lines += format_greedy(result)
        lines += format_strata_streaming(result)
        if reference:
            lines += ['The paired measurements compare the two complete engine and pack configurations. The experiment used the same request order and host caps, and sampled both source packs after each file-specific reset. The startup and load paths differ between engines.', '']
    lines += ['Source, cap, prompt, raw request phases, residency, model identities and build receipts are linked in the iteration record.',
              f'Native analysis and exact recomputation used release `{release}`.', '']
    return summary, '\n'.join(lines).encode()


def interval(row):
    return f"{row['median']:.3f} [{row['min']:.3f}, {row['max']:.3f}]"


def phase_counter_span(values):
    reads = {key: values['process_read_bytes'][key]/1024**2 for key in ('median', 'min', 'max')}
    return f"{interval(reads)} | {interval(values['process_major_faults'])}"


def format_steady(result):
    lines = ['## Cold positions matched by ordinal', '',
             '| Candidate and control | Position | Tokens | TTFT saved | Decode gain | Reads / major faults avoided to first token | Greedy parity |',
             '|---|---:|---:|---:|---:|---:|---|']
    for pair in result['comparisons']:
        for row in pair['cold_pairs']:
            counters = row['counters_avoided']['start_to_first_token']
            parity = 'matched' if row['greedy_parity'] else 'diverged'
            lines.append(f"| {pair['relation']} | {row['position']} | {row['prompt_tokens']} | {row['ttft_saved_s']:+.3f} s | "
                         f"{row['decode_gain_tps']:+.2f} tok/s | {counters['process_read_bytes']/1e9:+.3f} GB / "
                         f"{counters['process_major_faults']:+,} | {parity} |")
    lines += [
        '', '## Five post-warmup pairs', '',
        '| Arm | Tokens | TTFT median [min, max] s | Decode median [min, max] tok/s | Last minus first TTFT / decode |',
        '|---|---:|---:|---:|---:|',
    ]
    for scope in result['scopes']:
        for size, metrics in scope.get('steady_trend', {}).items():
            ttft, decode = metrics['ttft_s'], metrics['decode_tps']
            lines.append(f"| {scope['arm']} | {size} | {interval(ttft)} | {interval(decode)} | "
                         f"{ttft['last_minus_first']:+.3f} s / {decode['last_minus_first']:+.3f} tok/s |")
    lines += ['', '| Arm | Tokens | Process reads to first token (MiB) | Major faults to first token | Process reads afterward (MiB) | Major faults afterward |',
              '|---|---:|---:|---:|---:|---:|']
    for scope in result['scopes']:
        for size, metrics in scope.get('steady_trend', {}).items():
            phases = metrics['phase_counters']
            before = phase_counter_span(phases['start_to_first_token'])
            after = phase_counter_span(phases['first_token_to_end'])
            lines.append(f"| {scope['arm']} | {size} | {before} | {after} |")
    lines += ['', '| Candidate and control | Tokens | TTFT saved s | Decode gain tok/s | Greedy parity | Request positions with observed CPU-lane overlap |',
              '|---|---:|---:|---:|---|---|']
    for pair in result['comparisons']:
        for row in pair['steady']:
            parity = 'matched' if row['greedy_parity'] else 'diverged'
            overlap = ', '.join(map(str, row.get('observed_cpu_overlap_positions', []))) or '—'
            lines.append(f"| {pair['relation']} | {row['prompt_tokens']} | {interval(row['ttft_saved_s'])} | "
                         f"{interval(row['decode_gain_tps'])} | {parity} | {overlap} |")
    lines += ['', 'Ranges summarize the five observed paired positions within one launch per arm. Persistent movement across positions indicates residual warming or drift. '
              'Comparisons across cache budgets or Strata packs describe the named settings and engine differences. Greedy parity is reported separately. '
              'Retain mirrored launch replication for a causal performance decision.', '']
    return lines


def format_cpu_exposure(result):
    if not result.get('exploratory_cpu_overlap'):
        return []
    policy = result['cpu_policy']
    lines = ['## Concurrent CPU lane exposure', '',
             'The affected scope measurements are exploratory. Boundary receipts identify the owner-authorized '
             'JiuwenSwarm service on CPUs 12–19 while the capped model used CPUs 0–7. Shared storage and memory can still affect timing.',
             '', '| Scope | Source conditioning | Launch | Request positions and observed boundaries |',
             '|---|---|---|---|']
    for scope in result['scopes']:
        if exposure := scope.get('screening_exposure'):
            positions = ', '.join(f"{r['position']} ({'+'.join(r['boundaries'])})" for r in exposure['positions'])
            conditioning = 'observed' if exposure['conditioning'] else '—'
            launch = 'observed' if exposure['launch'] else '—'
            lines.append(f"| {scope['arm']} | {conditioning} | {launch} | {positions or '—'} |")
    lines += ['', 'Each observation names the PID, service cgroup and CPU affinity. Positions with an empty boundary '
              'observation can still overlap activity between snapshots. Repeat under the quiet mirrored protocol to confirm timing.',
              f"Authorization `{policy['artifact_id']}` SHA256 `{policy['sha256']}`.", '']
    return lines


def format_strata_streaming(result):
    strata = next((scope for scope in result['scopes'] if scope['mode'] == 'strata'), None)
    if strata is None:
        return []
    streams = strata['prefill_streaming']
    lines = ['## Strata engine prefill counters', '',
             f"Native engine log `{streams['engine_log']['artifact_id']}` and parsed prefill counters "
             f"`{streams['parsed']['artifact_id']}` are retained separately from request process and NVMe snapshots."]
    if row := streams.get('last_2048'):
        lines += ['', f"The final logged 2048-token CUDA0 prefill streamed {row['file_experts']:,} experts from files "
                  f"and {row['layer_cache_experts'] or 0:,} from the layer cache. The engine reported "
                  f"{row['reported_unbuffered_file_gb']:.1f} GB unbuffered and {row['reported_page_cache_file_gb']:.1f} GB "
                  f"through page cache, with {row['compute_read_wait_ms']:.0f} ms of compute wait for reads."]
        if row['io_worker_busy_ms'] is not None:
            lines.append(f"I/O workers accumulated {row['io_worker_busy_ms']:.0f} ms of activity across threads.")
    lines += ['', 'Worker times can overlap one another and other prefill work. '
              'The engine counters have their own boundaries and remain separate from client TTFT, process reads and GPU copies.', '']
    return lines


def format_greedy(result):
    lines = ['## Greedy output checks', '',
             '| Arm | Prompt tokens | Within-arm content and reasoning stability | Content SHA256 prefix |',
             '|---|---:|---|---|']
    for scope in result['scopes']:
        for size, stability in scope.get('within_arm_greedy_stability', {}).items():
            hashes = ', '.join(sorted({pair[0][:12] for pair in scope['greedy_hashes'][size]}))
            lines.append(f"| {scope['arm']} | {size} | {'stable' if stability else 'diverged'} | `{hashes}` |")
    lines += ['', 'Cross-arm equality is shown in the paired tables. Timing comparisons use the actual generated sequences. Accuracy remains unmeasured.', '']
    if historical := result.get('pilot_a_plus_output_check'):
        same = ', '.join(f'{size} tokens' for size, match in historical['matches'].items() if match)
        if same:
            lines += [f"The C3 60-GiB content and reasoning hashes also match the earlier A+ 30-GiB warm-up pilot at {same}. "
                      'That historical hash check uses a different cache budget.', '']
    return lines


def format_residency(result, ref):
    lines = ['## Source residency immediately before post-warmup requests', '',
             '| Arm | Source view | Tokens | Sampled expert inode residence, median [min, max] % | Cgroup file memory, median [min, max] GiB |',
             '|---|---|---:|---:|---:|']
    units = ('median', 'min', 'max')
    for scope in result['scopes']:
        for size, metrics in scope.get('steady_trend', {}).items():
            resident = metrics['source_residency']
            experts = {key: 100*resident['expert_inode_fraction'][key] for key in units}
            files = {key: resident['scope_file_bytes'][key]/1024**3 for key in units}
            lines.append(f"| {scope['arm']} | {scope['source_view']} | {size} | {interval(experts)} | {interval(files)} |")
    lines += ['', 'Expert residence estimates come from sampled pages of the named source inodes in the host page cache. '
              'Cgroup file memory comes from that scope’s memory.stat file field. Strata samples its own pack. '
              'Residency differences are observed at these boundaries, and a link to specific expert hits remains a hypothesis.',
              f"Planner input `{ref['artifact_id']}` SHA256 `{ref['sha256']}` retains all sample values and exact artifact references.", '']
    return lines


def source_plan(store, task, builder, prefix, put):
    decision = store.read(PLAN_TASK, PLAN_ID)
    plan_ref = put(f'{prefix}/source-planner-decision.json', json_bytes(decision))
    incoming = [key for key in decision['evidence_ids'] if key.startswith('incoming-') and key.endswith('.md')]
    for key in incoming:
        if store.read_artifact(task, key)['sha256'] != store.read_artifact(PLAN_TASK, key)['sha256']:
            raise ValueError('Copied historical planner input disagrees with its original')
    plan = dict(decision_id=dict(decision_id=PLAN_ID, task_id=PLAN_TASK), decision_artifact_id=plan_ref['artifact_id'],
                incoming_report_ids=incoming, builder_ccs=[builder],
                rationale='\n\n'.join(value for value in (decision['hypothesis'], decision['reason_for_change']) if value))
    authored = decision.get('action', {}).get('summary')
    if not authored:
        additions = store.query(PLAN_TASK, kinds=['factory_iteration_summary'], text=PLAN_ID)['items']
        for item in additions:
            addition = store.read(PLAN_TASK, item['id'])
            value = addition['values']
            if value.get('schema') == 'factory-iteration-summary/1' and value.get('decision_id') == PLAN_ID:
                authored = value.get('summary')
                put(f'{prefix}/source-planner-summary.json', json_bytes(addition))
                break
    if authored:
        plan['summary'] = authored
    return plan, incoming


def publish(base, stage):
    repo = Path(__file__).resolve().parents[2]
    ops = base / 'OPS/p3'
    pilot = stage == 'pilot'
    direct = stage == 'reference'
    revision = {'pilot': 1, 'reference': 1, 'screening': 2, 'full': 3}[stage]
    source_path = ops / 'cache-native-profile-verified-native-request.json'
    elf_path = ops / 'revised-native-cache-elf-manifest.json'
    inventory_path = ops / 'revised-cache-speed-products.json'
    release_path = ops / 'cache-native-profile-release.json'
    profile_path = ops / 'frozen-strata-top192-ranked-pool.json'
    first_path = base / 'OPS/runs/a-first-load-retry/start.json'
    regions_path = base / 'OPS/p4/source-regions.json'
    first = content(first_path)
    inventory = content(inventory_path)
    product = inventory['products'][0]
    if inventory['schema'] != 'spark-native-star-build-products/1' or product['capsule'] != 'expert_weight_cache':
        raise ValueError('Inventory does not identify the revised native cache')
    if direct:
        iteration = REFERENCE_ITERATION
        task, home = DIRECT_TASK, base / 'factory-runs/spark-direct-benchmarks'
    else:
        iteration = ITERATION
        builder, source, elf = map(content, (release_path, source_path, elf_path))
        task, home = source['task_id'], base / LANE
        if not source['source_clean'] or source['home'] != str(home) or (
            source['observed_head'] != product['source_commit'] or product['source_commit'] != elf['source']['commit'] or
            elf['build_receipt']['artifact_id'] != product['receipt_artifact_id'] or elf['executable'] != product['executable']):
            raise ValueError('Initial native build, retained ELF and source receipt disagree')
        if digest(safe_bytes(profile_path)) != PROFILE_DIGEST:
            raise ValueError('Cache nomination input differs from the pinned profile')
    model_identity_path = Path(first['command'][2]).parent.parent / 'factory-intake/asset-identity.json'
    obs = iteration + (f':report-v{revision}' if revision > 1 else ':report')
    prefix = f'{iteration}/{stage}'
    with Store(home) as store:
        try:
            current = store.read(task, obs)['values']['report']
            saved = store.read_artifact(task, current['artifact_id'])
            if saved['sha256'] != current['sha256']:
                raise ValueError('Stored iteration report digest disagrees')
            return dict(current, task_id=task, home=str(home), observation_id=obs)
        except NotFound:
            pass
        evidence_ids = []

        def put(identifier, raw, media='application/json'):
            record = store.put_artifact(task, identifier, raw, media, None)
            evidence_ids.append(record['artifact_id'])
            return {k: record[k] for k in ('artifact_id', 'sha256')}

        def attach(path):
            raw = safe_bytes(path)
            ref = put(f'{prefix}/{path.name}', raw)
            return dict(ref, value=json.loads(raw))

        inputs = (inventory_path, first_path) if direct else (source_path, elf_path, inventory_path, release_path, first_path)
        for path in inputs:
            attach(path)
        model_identity = attach(model_identity_path)
        regions = attach(regions_path)
        profile = None if direct else attach(profile_path)
        prompts = attach(repo / 'ops/spark/prompts/MANIFEST.json')
        cpu_policy_path = ops / 'concurrent-screening.json'
        cpu_policy = attach(cpu_policy_path) if stage == 'full' and cpu_policy_path.is_file() else None
        launcher_digest = digest(safe_bytes(inventory_path))
        expected, scopes = [], []
        schedule = {'pilot': EARLY, 'reference': REFERENCE, 'screening': SCREENING, 'full': FINAL}[stage]
        for mib, role, folder in schedule:
            path = base / 'OPS/runs' / folder
            if not (path / 'result.json').is_file():
                raise ValueError(f'Scope has no completed result receipt: {folder}')
            arm = expected_argv(base, first, product, launcher_digest, profile_path, mib, role, path)
            if cpu_policy and folder in cpu_policy['value']['scope_names']:
                arm['authorized_scope'] = folder
            expected.append(arm)
            streaming = None
            if role == 'strata':
                instance = attach(Path(arm['config']))['value']
                attach(base / 'OPS/configs/p4-s-pass-1.json')
                historical = base / 'OPS/runs/s-first-load'
                attach(historical / 'strata-fair-provenance.json')
                drift = attach(historical / 'profile-drift.json')['value']
                args = instance['args']
                profile_file = Path(args[args.index('--expert-profile') + 1])
                frozen = safe_bytes(profile_file)
                if digest(frozen) != drift['before_sha256']:
                    raise ValueError('Strata fair profile differs from the frozen pre-run bytes')
                put(f'{prefix}/strata-frozen-profile.bin', frozen, 'application/octet-stream')
                engine_log = safe_bytes(path / 'engine.log')
                engine_ref = put(f'{prefix}/scopes/{folder}/engine.log', engine_log, 'text/plain')
                rows = stream_counters(engine_log.decode(errors='replace'))
                parsed = put(f'{prefix}/scopes/{folder}/prefill-streaming.json', json_bytes(rows))
                streaming = dict(engine_log=engine_ref, parsed=parsed, value=rows)
            protocol = None
            if (path / 'protocol.json').is_file():
                protocol_raw = safe_bytes(path / 'protocol.json')
                protocol_value = json.loads(protocol_raw)
                protocol_rows = protocol_value['ordered_requests']
                if any(Path(row['path']).name != row['path'] for row in protocol_rows):
                    raise ValueError('Protocol request path leaves its own scope')
                protocol = dict(put(f'{prefix}/scopes/{folder}/protocol.json', protocol_raw), value=protocol_value)
                if protocol_value['conditioning_receipt'] != str(ops / 'early-preflights' / (folder + '-source.json')):
                    raise ValueError('Protocol names a different source-conditioning receipt')
            finished = (path / 'probe.json').is_file()
            request_order = PILOT_ORDER if pilot and finished else ()
            scope = scope_inputs(path, base, put, prefix, 'S' if role == 'strata' else 'C3', request_order=request_order,
                                 protocol=protocol['value']['ordered_requests'] if protocol else None)
            if protocol:
                scope['protocol'] = protocol
            if streaming:
                scope['prefill_streaming'] = streaming
            if finished and not pilot and not protocol:
                raise ValueError('A full lab scope completed without its protocol receipt')
            if role != 'strata' and scope['load']['value']['native_build_receipt'] != (
                    product['receipt_artifact_id'] if role == 'on' else None):
                raise ValueError('Launch provenance points to a different build receipt')
            scope['log']['gzip_b64'] = b64encode(gzip.compress(safe_bytes(path / 'stderr.log'), compresslevel=1, mtime=0)).decode('ascii')
            if (path / 'profile-activation.json').is_file():
                raw = safe_bytes(path / 'profile-activation.json')
                scope['activation'] = dict(put(f'{prefix}/scopes/{folder}/profile-activation.json', raw), value=json.loads(raw))
            scopes.append(scope)
        existing = [] if direct else [DIFF, VERIFY, elf['build_receipt'], elf['build_record']]
        for ref in existing:
            if store.read_artifact(task, ref['artifact_id'])['sha256'] != ref['sha256']:
                raise ValueError(f"Changed DO or native build artifact {ref['artifact_id']}")
        mode = MODES[stage]
        evidence = dict(mode=mode, expected=expected,
                        prompts=prompts, model_identity=model_identity, profile=profile, regions=regions, scopes=scopes)
        if cpu_policy:
            evidence['cpu_policy'] = cpu_policy
        if stage == 'screening':
            prior_id = f'{ITERATION}/pilot/analysis.json'
            try:
                prior_raw = store.artifact_bytes(task, prior_id)
            except NotFound:
                pass
            else:
                prior = json.loads(prior_raw)
                historical = next(row for row in prior['scopes'] if row['mode'] == 'equivalent-stock')
                evidence['pilot_a_plus'] = dict(artifact_id=prior_id, sha256=digest(prior_raw), hashes=historical['greedy_hashes'])
                evidence_ids.append(prior_id)
        analysis_input = json_bytes(evidence)
        host = Host(home / 'analysis-ccv2')
        release = host.seal(repo / 'jiuwenswarm/factory/ccs/spark_gap_analysis')
        call_key = f'{prefix}:{release}:{digest(analysis_input)}'
        result = host.call(release, 'analyze', {'evidence': evidence}, key=call_key+':analyze', grants=['process.exec'])
        analysis = result.get('outputs', {}).get('analysis')
        if analysis is None:
            failed = json_bytes(result)
            put(f'{prefix}/failed-{digest(failed)[:12]}.json', failed)
            raise ValueError(f"Native cache analysis admission failed: {result.get('diagnostics')}")
        checked = host.call(release, 'verify', {'evidence': evidence, 'analysis': analysis}, key=call_key+':verify',
                            grants=['process.exec'])
        if checked.get('outputs', {}).get('verification', {}).get('done') is not True:
            raise ValueError('Verifying the cache result did not reproduce exact analysis')
        put(f'{prefix}/analysis-input.json', analysis_input)
        lab = put(f'{prefix}/lab.json', json_bytes(dict(schema='spark-position-lab/1', mode=mode, scopes=analysis['scopes'])))
        lab_ids = list(evidence_ids)
        outputs = [put(f'{prefix}/{name}.json', json_bytes(value))['artifact_id'] for name, value in (
            ('analysis', analysis), ('analyze-receipt', result), ('verify-receipt', checked))]
        outputs.append(put(f'{prefix}/release-manifest.json',
                           (host.store / 'releases' / release / 'manifest.json').read_bytes())['artifact_id'])
        residency_ref = None
        if not pilot:
            by_scope = {scope['arm']: {'source_view': scope['source_view'], 'by_prompt': {
                size: metrics['source_residency'] for size, metrics in scope['steady_trend'].items()}}
                for scope in analysis['scopes'] if scope['status'] == 'completed'}
            residency_ref = put(f'{prefix}/steady-source-residency.json', json_bytes(
                dict(schema='spark-steady-source-residency/1', scopes=by_scope, n_per_prompt=5)))
            outputs.append(residency_ref['artifact_id'])
        summary, report_body = report_text(analysis, release, residency_ref)
        report = put(f'{prefix}/report.md', report_body, 'text/markdown')
        status = {'pilot': 'warm-up pilot', 'screening': '60-GiB interim screening',
                  'reference': 'cold and steady reference', 'full': 'cold and steady lab'}[stage]
        if analysis.get('exploratory_cpu_overlap'):
            status = 'exploratory cold and post-warmup screening'
        report = dict(report, revision=revision, summary=summary, status=status)
        kind = 'factory_iteration_report'
        for older in range(revision - 1, 0, -1):
            previous_obs = ITERATION + (f':report-v{older}' if older > 1 else ':report')
            try:
                previous = store.read(task, previous_obs)['values']['report']
            except NotFound:
                continue
            if store.read_artifact(task, previous['artifact_id'])['sha256'] != previous['sha256']:
                raise ValueError('Earlier cache report digest changed')
            report.update(supersedes_observation_id=previous_obs, supersedes_artifact_id=previous['artifact_id'])
            kind = 'factory_iteration_report_revision'
            evidence_ids.append(previous['artifact_id'])
            break
        predecessors, incoming = [], []
        if direct:
            baseline = store.read(task, P1_ITERATION + ':report')['values']['report']
            if store.read_artifact(task, baseline['artifact_id'])['sha256'] != baseline['sha256']:
                raise ValueError('P1 predecessor report digest changed')
            predecessors.append({key: baseline[key] for key in ('artifact_id', 'sha256')})
            evidence_ids.append(baseline['artifact_id'])
            plan = dict(decision_id=None, incoming_report_ids=[], builder_ccs=[],
                        summary='Run the same cold and post-warmup prompt order on stock llama.cpp and fair Strata.',
                        rationale='Address the earlier P1 timing limits with separately conditioned sources, a common request order, and one capped launch per reference.')
            do = dict(source_commit=None, diff_artifact_id=None, verification_receipt_ids=[], build_receipt_ids=[])
        else:
            plan, incoming = source_plan(store, task, builder, prefix, put)
            do = dict(source_commit=source['observed_head'], diff_artifact_id=DIFF['artifact_id'],
                      verification_receipt_ids=[VERIFY['artifact_id']],
                      build_receipt_ids=[elf[key]['artifact_id'] for key in ('build_receipt', 'build_record')])
        envelope = dict(schema='spark-factory-iteration/1', iteration_id=iteration, predecessor_report_ids=predecessors,
                        plan=plan, do=do,
                        lab=dict(status=report['status'], result_artifact_ids=lab_ids, lab_artifact_id=lab['artifact_id']),
                        analysis=dict(ccs=[dict(id=CAPSULE, version=host.describe(release)['version'], release=release)],
                                      output_artifact_ids=outputs), report=report, next_plan=dict(decision_id=None))
        append_once(store, task, dict(obs_id=obs, kind=kind, values=envelope,
            source_artifacts=[*evidence_ids, *incoming, *[r['artifact_id'] for r in existing]]))
        out = base / 'OPS/iterations' / iteration / stage
        out.mkdir(parents=True, exist_ok=True)
        (out / 'report.md').write_bytes(report_body)
        (out / 'analysis.json').write_bytes(json_bytes(analysis))
        (out / 'iteration.json').write_bytes(json_bytes(envelope))
        return dict(report, task_id=task, home=str(home), observation_id=obs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=MODES)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    args = parser.parse_args()
    print(json.dumps(publish(args.base.resolve(), args.stage), indent=2))
