"""Run the single, operator-approved AQB W1 warm-up sequence under the 96 GiB cap."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
from tempfile import TemporaryDirectory
from uuid import uuid4

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.lab_lifecycle import QuietLease, atomic_json
from jiuwenswarm.factory.muse_r9_measure import first_cached_tasks
from scripts.factory import lab_v4_fast as lab, lab_v4_quiet as quiet
from scripts.factory import r8_final_benchmark as bench
from scripts.factory.r8_derive_p_ttft import derive

OUT = bench.BASE / 'lab/warmup-w1/run'
LOAD3_SHA256 = '72aed83d1fee53747988f5a4df862467e6ab806518d5e84a9f939ae117d8146e'
TOKENIZER = Path('/tmp/wt-stock-tools/build-cpu/bin/llama-tokenize')
TOKENIZER_SHA256 = 'b79d54a0b37f456fa41a4a6acbe8da8793b24721bd097ab85764102290fd9873'
BUDGET = 110000
MIN_FIT_MIB = 11618
N_PREDICT = 32
NOTE = 'measured on a shared machine; background activity recorded, not filtered'
USER_MARKER = '<|start|>user<|message|>'
END_MARKER = '<|eot|><|start|>assistant'
FILLERS = ('', ' a', ' the', ' a a', ' the the', '.', ' a.')
DOCUMENT_WORDS = {
    'D2': 'estuary sandpiper reed fossil marsh water salinity tide mussel channel silt heron shore eelgrass salt net',
    'D3': 'summit cloud frost moraine compass pine granite fault boulder glacier ledge wind lichen ridge slope snow',
    'D4': 'orchard seed plank soil plum irrigation trellis rain blossom quince graft mulch leaf pruning pear sun',
    'D5': 'vessel kiln clay glaze porcelain scraper chalk plaster ochre pigment flint ash vessel shard sandstone slip',
    'D6': 'meadow swallow grass cricket moth heather rabbit clover shade fog brook willow hare burrow fern moss',
    'E1': 'basalt ash crater magma lahar plume vent caldera pumice tuff fissure lapilli cone lava seismic obsidian',
    'E2': 'current plankton buoy shelf depth oxygen salinity clams kelp anemone seal rope mussel wave anchor reef',
}


@dataclass(frozen=True)
class Document:
    name: str
    intended: int
    text: str
    token_ids: tuple[int, ...]

    def metadata(self):
        return dict(document=self.name, intended_prompt_tokens=self.intended,
                    rendered_prompt_tokens=len(self.token_ids),
                    prompt_sha256=hashlib.sha256(self.text.encode()).hexdigest(),
                    token_ids_sha256=hashlib.sha256(json.dumps(self.token_ids, separators=(',', ':')).encode()).hexdigest())


def schedule():
    return [
        ('D1', 'startup'),
        *((f'D{idx}', 'new') for idx in range(2, 7)),
        *([('D6', 'repeat')] * 4),
        ('D6', 'after_page_evict'),
        ('E1', 'new'), ('E2', 'new'), ('E2', 'repeat'), ('E2', 'repeat'),
    ]


def offline_tokenizer(binary, model):
    def tokenize(text):
        # This CPU-only llama-tokenize executable uses vocab_only. The flags
        # are those of the existing lab fitter (fit_prompts.py).
        done = subprocess.run([str(binary), '-m', str(model), '--stdin', '--ids', '--log-disable', '--no-bos'],
                              input=text, text=True, capture_output=True, timeout=30, check=True)
        tokens = json.loads(done.stdout)
        if not isinstance(tokens, list) or not tokens or any(type(value) is not int for value in tokens):
            raise ValueError('Offline tokenizer did not return a token ID list')
        return tuple(tokens)
    return tokenize


def document_shell(rendered):
    user_start = rendered.index(USER_MARKER) + len(USER_MARKER)
    body_start = rendered.index('\n\n', user_start) + 2
    if not rendered.endswith(END_MARKER) or not body_start < len(rendered) - len(END_MARKER):
        raise ValueError('AQB prompt rendering does not contain one complete notebook')
    return rendered[:body_start], END_MARKER


def fit_notebook(head, tail, cycle, tokenize, target):
    """Fit a distinct notebook with the lab fitter's word-prefix search and short fillers."""
    words = cycle.split()
    words *= (target * 2 // len(words)) + 1
    low, high = 1, len(words)
    while low < high:
        mid = (low + high + 1) // 2
        trial = head + ' '.join(words[:mid]) + tail
        if len(tokenize(trial)) <= target:
            low = mid
        else:
            high = mid - 1
    body = ' '.join(words[:low])
    for extra in FILLERS:
        text = head + body + extra + tail
        tokens = tokenize(text)
        if len(tokens) == target:
            return text, tokens
    raise ValueError(f'Existing lab fit method could not reach exactly {target} rendered tokens')


def build_documents(proposal, tokenize):
    pins = proposal['speed_prompt_pins']
    source = {}
    for size in (512, 2048):
        pin = pins[f'p{size}']
        path = Path(pin['file'])
        if bench.digest(path) != pin['sha256']:
            raise ValueError(f'p{size} rendered source changed')
        text = path.read_text()
        tokens = tokenize(text)
        if len(tokens) != pin['verified_server_tokens']:
            raise ValueError(f'p{size} offline count differs from the historical AQB tokenizer')
        source[size] = (text, tokens)
    head, tail = document_shell(source[2048][0])
    if (head, tail) != document_shell(source[512][0]):
        raise ValueError('AQB p512 and p2048 use different field-notebook templates')
    documents = {'D1': Document('D1', 512, *source[512])}
    for name, words in DOCUMENT_WORDS.items():
        intended = 512 if name.startswith('D') else 2048
        target = pins[f'p{intended}']['verified_server_tokens']
        text, tokens = fit_notebook(head, tail, words, tokenize, target)
        documents[name] = Document(name, intended, text, tokens)
    if len({doc.token_ids for doc in documents.values()}) != len(documents):
        raise ValueError('W1 documents are not distinct token sequences')
    return documents


def _launch_args(proposal, prior, model):
    leg = prior['load']
    chosen = (leg['ctx'], leg['np'], leg['batch'], leg['ubatch'], leg['moe_cache_mib'])
    if chosen != (8192, 1, 2048, 2048, 62464):
        raise ValueError('Unexpected AQB load 3 context, parallelism, batch or MoE cache')
    base = [*proposal['base_args'], '-c', str(leg['ctx']), '-np', str(leg['np']), '-b', str(leg['batch']),
            '-ub', str(leg['ubatch']), '--moe-cache-mib', str(leg['moe_cache_mib'])]
    prior_argv = prior['argv']
    model_index = prior_argv.index('-m')
    fit_index = prior_argv.index('-fitt')
    if (prior_argv[model_index + 1] != str(model)
            or prior_argv[model_index + 2:fit_index] != base
            or prior_argv[fit_index + 1] != str(MIN_FIT_MIB)):
        raise ValueError('Reconstructed AQB launch differs from the recorded load 3 argv')
    return [*base, '-fitt', str(MIN_FIT_MIB)]


def preflight():
    proposal, identity, _ = bench.check_inputs()
    receipt = bench.OUT / '3.load.json'
    if bench.digest(receipt) != LOAD3_SHA256:
        raise ValueError('AQB load 3 receipt differs from the pinned benchmark')
    prior = bench.read(receipt)
    pack = proposal['pack_pins']['MIXED_2BIT']
    model = Path(pack['first_shard'])
    retained_binary = next(Path(arg) for arg in prior['argv'] if arg.endswith('/llama-server'))
    if (prior['status'] != 'complete' or prior['factory_provenance'] != identity or prior['pack'] != pack
            or bench.digest(retained_binary) != identity['llama_server_sha256']):
        raise ValueError('AQB image, binary or pack differs from completed load 3')
    image = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', identity['image_id']],
                           check=True, capture_output=True, text=True, timeout=30).stdout.strip()
    if image != identity['image_id'] or bench.digest(TOKENIZER) != TOKENIZER_SHA256:
        raise ValueError('Installed image or offline tokenizer differs from the lab pin')
    # Contact the user bus without creating a scope or exposing its environment.
    subprocess.run(['systemctl', '--user', 'show', '--property=Version', '--value'],
                   env={**os.environ, **capped_run.user_bus_env()}, check=True,
                   capture_output=True, text=True, timeout=15)
    args = _launch_args(proposal, prior, model)
    documents = build_documents(proposal, offline_tokenizer(TOKENIZER, model))
    return prior, identity, pack, args, documents


def verify_live_tokenizer(server, documents):
    for doc in documents.values():
        reply = server.post(dict(content=doc.text, add_special=True, parse_special=True),
                            path='/tokenize', timeout=60)
        tokens = reply['tokens']
        if any(type(t) is not int for t in tokens) or tuple(tokens) != doc.token_ids:
            raise ValueError(f'{doc.name}: live tokenizer differs from the pinned offline token IDs')


def live_row(server, monitor, probe, out, doc, condition, index, pack):
    row = dict(doc.metadata(), index=index, condition=condition, cache_prompt=False, n_predict=N_PREDICT,
               temperature=0, seed=1, ignore_eos=True, status='pending')
    path = out / f'{index:02}.json'
    atomic_json(path, row)
    start = None
    try:
        start, _ = monitor.wait('start', 'during', server.run.log)
        if condition == 'after_page_evict':
            row['page_cache_before_eviction'] = probe.pack_residency(
                Path(pack['manifest']), pack['manifest_sha256'])
            lab.evict(pack['first_shard'])
            row['page_eviction_utc'] = bench.now()
        row['page_cache_before'] = probe.pack_residency(Path(pack['manifest']), pack['manifest_sha256'])
        row['server_memory_before'] = probe.server_memory(server)
        scope = row['server_memory_before']['scope']
        if scope['max_bytes'] != 96 * 2**30 or scope['swap_max_bytes'] != 0:
            raise ValueError('Running cgroup differs from the pinned 96 GiB, zero-swap cap')
        before = probe.counter_probe(server)
        offset = server.log.stat().st_size
        row.update(status='measuring', server_log_start=offset)
        atomic_json(path, row)
        metrics = lab.request(server, doc.text, N_PREDICT, benchmark=True, cache_prompt=False, retain_output=True)
        row.update(metrics)
        after = probe.counter_probe(server)
        row['moe_cache_counters'] = probe.counter_delta(before, after)
        with server.log.open('rb') as source:
            source.seek(offset)
            raw = source.read()
        row['server_log_end'] = offset + len(raw)
        tasks = first_cached_tasks(raw)
        if (len(tasks) != 1 or tasks[0].get('slot_id') != 0 or tasks[0].get('cached_tokens') != 0
                or tasks[0].get('prompt_tokens') != len(doc.token_ids) or not tasks[0].get('end')):
            raise ValueError('Server log did not establish one completed request with zero cached tokens')
        row['server_request'] = tasks[0]
        if (row['generated_tokens'] != N_PREDICT or row['prompt_tokens'] != len(doc.token_ids)
                or row['client_ttft_ms'] is None or not row['output_text'].strip()):
            raise ValueError('Completion differs from the declared W1 token counts or is empty')
        for name in ('client_ttft_ms', 'decode_tokens_per_second', 'request_total_ms'):
            if type(row[name]) not in (float, int) or not math.isfinite(row[name]) or row[name] <= 0:
                raise ValueError(f'Invalid elapsed or decode metric {name}')
        row['quiet'] = {'status': 'recorded'}
        timing_row = dict(row, arm='AQB', request=doc.name, state=condition, repeat=0)
        row.update({key: val for key, val in derive(timing_row).items() if key not in {
            'arm', 'request', 'state', 'repeat', 'quiet_status'}})
        row['status'] = 'complete'
    except BaseException as error:
        row.update(status='stopped', error=dict(code=getattr(error, 'code', type(error).__name__), message=str(error)))
        raise
    finally:
        if start is not None:
            end = monitor.mark('end', 'between_rows')
            samples = monitor.samples[start:end + 1]
            row['quiet'] = dict(status='recorded', reasons=quiet.evidence_issues(samples, monitor.limits), samples=samples)
        atomic_json(path, row)
    return row


def execute(prepared, out=OUT):
    from scripts.factory import warmup_w1_probe as probes

    prior, identity, pack, args, documents = prepared
    with QuietLease(bench.BASE / 'lab-lease', timeout_s=0):
        out.mkdir(mode=0o750, parents=True, exist_ok=False)
        run = capped_run.RunScope(out, out, dict(resources=dict(memory_cap=capped_run.CAP,
                                  need_available_gib=100, device_budget_mib=BUDGET, floor_gib=8,
                                  gate_wait_s=0)), uuid4().hex)
        limits = quiet.policy(quiet.SHARED)
        report = dict(format='muse-warmup-w1/1', status='admitting', run_id=run.run_id, started_utc=bench.now(),
                      identity=identity, pack=pack, load_3_receipt_sha256=LOAD3_SHA256, server_args=args,
                      minimum_fit_margin_mib=MIN_FIT_MIB, memory_cap=run.cap, swap_cap_bytes=0,
                      device_budget_mib=BUDGET, quiet_policy=limits, method_note=NOTE,
                      schedule=[dict(index=index, document=name, condition=state)
                                for index, (name, state) in enumerate(schedule(), 1)],
                      documents={name: doc.metadata() for name, doc in documents.items()}, rows=[])
        path = out / 'report.json'
        atomic_json(path, report)
        server = None
        try:
            prompt_dir = out / 'prompts'
            prompt_dir.mkdir()
            for doc in documents.values():
                (prompt_dir / f'{doc.name}.rendered.txt').write_text(doc.text, encoding='utf-8')
            with TemporaryDirectory(dir=out, prefix='.image-') as directory:
                image_dir, report['image'] = lab.from_image('W1 AQB', dict(
                    image=identity['image_id'], expect_image_id=identity['image_id'],
                    expect_sha256=identity['llama_server_sha256']), Path(directory))
                with quiet.Monitor(limits, slots=1, stop_on_gate=True) as monitor:
                    try:
                        # No pre-launch eviction and no inference request before D1.
                        report['machine_gate'] = run.gate()
                        report['status'] = 'launch_reserved'
                        atomic_json(path, report)
                        server = capped_run.Server(run, str(Path(image_dir) / 'llama-server'),
                            pack['first_shard'], args, capped_run.user_bus_env(), 'server.log', capture_stdout=True)
                        monitor.server = server
                        monitor.mark('ready', 'between_rows')
                        report.update(status='loaded', pid=server.proc.pid, argv=server.argv,
                                      launch_to_ready_s=server.ready_s, placement=server.placement)
                        report['fit_margin_raise_mib'] = server.placement['fit_margin_mib'] - MIN_FIT_MIB
                        atomic_json(path, report)
                        report['observed'] = bench.validate_ready(server, prior['load'])
                        if sum(report['observed']['device_mib'].values()) > BUDGET:
                            raise ValueError('Observed device and host compute buffers exceed 110000 MiB')
                        report['startup_warmup'] = probes.startup_warmup(server.log)
                        if report['startup_warmup']['status'] != 'bounded':
                            raise ValueError('Startup log did not establish the model warmup interval')
                        verify_live_tokenizer(server, documents)
                        atomic_json(path, report)
                        for index, (name, state) in enumerate(schedule(), 1):
                            run.log(f'{index:02}/15 {name} {state}: sampling and measuring')
                            row = live_row(server, monitor, probes, out, documents[name], state, index, pack)
                            report['rows'].append(row)
                            atomic_json(path, report)
                            run.log(f'{index:02}/15 {name} {state}: TTFT {row["derived_ttft_ms"]} ms, '
                                    f'decode {row["decode_tokens_per_second"]:.3f} tokens/s')
                        report['status'] = 'complete'
                    finally:
                        if server:
                            try:
                                server.close()
                            finally:
                                monitor.server = None
                                report['server_closed'] = server.proc.poll() is not None
                        monitor.mark('arm_end')
                        atomic_json(out / 'admission.json',
                                    [sample for sample in monitor.samples if sample['phase'] not in ('during', 'end')])
        except BaseException as error:
            report.update(status='stopped', error=dict(code=getattr(error, 'code', type(error).__name__),
                          message=str(error)))
            raise
        finally:
            report['ended_utc'] = bench.now()
            atomic_json(path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Launch the single reserved W1 measurement')
    options = parser.parse_args()
    prepared = preflight()
    if options.execute:
        def interrupted(_signal, _frame):
            raise KeyboardInterrupt('W1 interrupted')
        signal.signal(signal.SIGTERM, interrupted)
        execute(prepared)
    else:
        _, identity, pack, args, documents = prepared
        print(json.dumps(dict(status='preflight_complete', image_id=identity['image_id'], pack=pack,
                              args=args, rows=len(schedule()), documents={name: doc.metadata()
                              for name, doc in documents.items()}, next_output=str(OUT)), indent=2))


if __name__ == '__main__':
    main()
