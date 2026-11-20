"""Review retained page samples and native bank logs for the 60 GiB P4 mirror."""
import json
import re

from expert_seed_residency import classify, read_layout, startup_admissions, utc
from import_evidence import digest, safe_bytes

EXPERT_EXTENTS = 'OPS/p3/cache-direct-seed-30g-expert-extents.json'
EXPERT_EXTENTS_SHA256 = '35d034e7a154df2337665274ae6a2b924f84e1610eb2c3691ed13597b9952eb4'
CLASSES = ('startup_seeded', 'other_expert')
SMALL = re.compile(r'llama_moe_cache: ubatch <= 8: hits = (\d+), misses = (\d+) \((\d+) on the CPU\), '
                   r'hit rate = ([\d.]+)%, uploaded = ([\d.]+) MiB')
LARGE = re.compile(r'llama_moe_cache: large batches: (\d+) experts copied from the cache, ([\d.]+) MiB')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def collect(base, scopes, requests, read, read_raw, span):
    path = base / EXPERT_EXTENTS
    raw_extents = safe_bytes(path)
    require(digest(raw_extents) == EXPERT_EXTENTS_SHA256, 'Frozen six-shard expert extent manifest changed')
    layouts, sizes = read_layout(json.loads(raw_extents))
    subject = [scope for scope in scopes if scope['arm'] == 'C3']
    native_logs, grants, warnings = [], [], []
    for scope in scopes:
        ref = scope['provenance']['engine_log']
        log = read_raw(ref).decode(errors='replace')
        small, large = SMALL.findall(log), LARGE.findall(log)
        require(len(small) == len(large) == 1, 'Native bank shutdown counters are absent or ambiguous')
        hits, misses, cpu, rate, uploaded = small[0]
        copied, d2d = large[0]
        counters = dict(small_ubatch=dict(hits=int(hits), misses=int(misses), cpu_misses=int(cpu),
                                         hit_rate_pct=float(rate), uploaded_mib=float(uploaded)),
                        large_batch=dict(experts_copied_from_cache=int(copied), device_to_device_mib=float(d2d)))
        native_logs.append(dict(arm=scope['arm'], launch_pass=scope['launch_pass'], log=ref, **counters))
        if scope['arm'] == 'C3':
            if 'expert_weight_cache_native_profile: nomination ' not in log:
                warnings.append(f"C3 pass {scope['launch_pass']} has no per-expert startup admission rows.")
                continue
            admitted, uploaded = startup_admissions(log, sizes)
            grants.append(dict(launch_pass=scope['launch_pass'], ids=sorted(admitted), upload_bytes=uploaded, log=ref))
    mechanism = dict(native_bank=native_logs, warnings=warnings, startup_admissions=grants,
                     extents=dict(path=str(path), sha256=EXPERT_EXTENTS_SHA256))
    if warnings:
        return mechanism
    require(len(grants) == len(subject) == 2 and grants[0]['ids'] == grants[1]['ids'] and
            grants[0]['upload_bytes'] == grants[1]['upload_bytes'], 'C3 launches do not share the same actual seed set')
    seeded = {tuple(key) for key in grants[0]['ids']}
    common_fingerprint = None
    sample_scopes = []
    for scope in scopes:
        owner = scope['artifact_id']
        kernel, load = read(scope['scope']), read(scope['load'])
        owner_requests = [row for row in requests if row['scope_id'] == owner]
        samples = []

        def retain(ref, snapshot, boundary, **fields):
            nonlocal common_fingerprint
            classes, fingerprint = classify(snapshot, layouts, seeded)
            if common_fingerprint is None:
                common_fingerprint = fingerprint
            require(fingerprint == common_fingerprint and all(classes[key]['weighted_resident_fraction'] is not None for key in CLASSES),
                    'Page draw / stratum identities differ or an expert class has no samples')
            if boundary != 'post-conditioning':
                require(snapshot['scope_accounting']['path'] == kernel['cgroup'], 'Source-page sample crosses cgroup ownership')
            samples.append(dict(boundary=boundary, completed=snapshot['completed'], ref=ref, classes=classes, **fields))

        conditioning = scope['conditioning']
        retain(conditioning, read(conditioning)['after'], 'post-conditioning')
        require(all(samples[-1]['classes'][key]['resident_sampled_pages'] == 0 for key in CLASSES),
                'Source conditioning left resident samples in the comparison classes')
        postready = scope['provenance'].get('load_ready_residency')
        if postready:
            ready = read(postready)
            require(utc(load['ready_at']) <= utc(ready['started']) <= utc(ready['completed']) <=
                    utc(owner_requests[0]['result']['started']), 'Post-ready snapshot does not precede the first prompt')
            retain(postready, ready, 'post-ready')
        else:
            warnings.append(f"{scope['arm']} pass {scope['launch_pass']} has no post-ready capture.")
        before = 0
        after = 0
        for position, request in enumerate(owner_requests, 1):
            ref = request['evidence'].get('residency')
            if not ref:
                continue
            result = request['result']
            warmup = result['discard']
            before += int(not warmup)
            after += int(warmup)
            retain(ref, read(ref), 'after-warmup-pair' if warmup else 'before-request',
                   position=position, repeat=result['repeat'], tokens=result['prompt_tokens'])
        require(before == 10 and after == 3, 'Expected ten measured boundaries and three warmup pair captures')
        sample_scopes.append(dict(arm=scope['arm'], launch_pass=scope['launch_pass'], samples=samples))
    steady = []
    for arm in ('A+', 'C3'):
        for tokens in (512, 2048):
            measured = [item for scope in sample_scopes if scope['arm'] == arm for item in scope['samples']
                        if item['boundary'] == 'before-request' and item['tokens'] == tokens]
            require({item['repeat'] for item in measured} == set(range(1, 11)) and len(measured) == 10,
                    'Measured residency ordinal pairs are incomplete')
            steady.append(dict(arm=arm, tokens=tokens, n=len(measured), classes={
                key: dict(residency_fraction=span([item['classes'][key]['weighted_resident_fraction'] for item in measured]),
                          sampled_pages=measured[0]['classes'][key]['sampled_pages'])
                for key in CLASSES}))
    mechanism.update(scopes=sample_scopes, steady=steady, page_size=common_fingerprint[0],
                     pages_per_sample=common_fingerprint[1], sampling_seed=common_fingerprint[2])
    return mechanism


def render(mechanism):
    lines = ['## Verified native-bank shutdown counters', '',
             '| Arm | Pass | Small ubatch ≤8 hits | Small ubatch misses | CPU misses | Demand upload MiB | Large batch cache copies | Large batch device-to-device MiB |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in mechanism['native_bank']:
        s, t = (row[key] for key in ('small_ubatch', 'large_batch'))
        lines.append(f"| {row['arm']} | {row['launch_pass']} | {s['hits']:,} | {s['misses']:,} | {s['cpu_misses']:,} | "
                     f"{s['uploaded_mib']:,.2f} | {t['experts_copied_from_cache']:,} | {t['device_to_device_mib']:,.2f} |")
    lines += ['', 'Counters cover the whole launch, including warmups. The small-ubatch category can include prefill and decode. '
              'Large-batch cache copies are device-local. Process read and fault counters use separate boundaries.', '',
              '## Host file pages associated with actual C3 startup seeds', '', *mechanism['warnings'], '']
    if 'scopes' not in mechanism:
        return lines
    grants = mechanism['startup_admissions']
    lines += [f"Both C3 passes admitted the same {len(grants[0]['ids']):,} experts and uploaded "
              f"{grants[0]['upload_bytes']/1e9:.3f} GB at startup. The A+ comparison applies the same layer and expert IDs to its source pages.",
              '', '| Arm | Pass | Post-ready seeded pages | Post-ready other expert pages | Excluded boundary draws |',
              '|---|---:|---:|---:|---:|']
    for scope in mechanism['scopes']:
        ready = next((item['classes'] for item in scope['samples'] if item['boundary'] == 'post-ready'), None)
        if ready:
            values = ' | '.join(f"{ready[key]['weighted_resident_fraction']:.2%} ({ready[key]['sampled_pages']:,} draws)"
                                for key in CLASSES)
            lines.append(f"| {scope['arm']} | {scope['launch_pass']} | {values} | {ready['excluded_boundary']['sampled_pages']:,} |")
    lines += ['', '| Arm | Prompt | Seeded before-request median [min, max] | Other before-request median [min, max] |',
              '|---|---:|---:|---:|']
    for row in mechanism['steady']:
        cells = []
        for key in CLASSES:
            obj = row['classes'][key]
            f = obj['residency_fraction']
            cells.append(f"{f['median']:.2%} [{f['min']:.2%}, {f['max']:.2%}] ({obj['sampled_pages']:,} draws)")
        lines.append(f"| {row['arm']} | {row['tokens']} | {' | '.join(cells)} |")
    lines += ['', 'The same deterministic page draws are weighted by their original stratum size and exclude slice-boundary pages. '
              'The JSON supplement retains all three post-warmup-pair observations per launch and separate cgroup/host evidence references. '
              'These estimates describe host file pages by startup admission class. Later evictions can change device-bank membership. '
              'Per-expert cache-hit causation remains unmeasured.', '']
    return lines
