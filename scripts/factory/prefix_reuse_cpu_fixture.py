"""Gated factory-stage SWA fixture using the delivered engine executable on CPU."""

import argparse
from itertools import takewhile
import json
from pathlib import Path
import re
import signal
import time
from uuid import uuid4

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.lab_lifecycle import QuietLease, atomic_json
from jiuwenswarm.factory.muse_r9_measure import first_cached_tasks
from scripts.factory import lab_v4_fast as lab, r8_final_benchmark as bench
from scripts.factory.warmup_w1 import fit_notebook

OUT = bench.BASE / 'r9/factory-fixture-c'
SOURCE_REVISION = 'c90975dbd40c0c7b275fefaae758c3415c906238'
MODEL_ID = 'unsloth/gemma-3-270m-it-GGUF'
FILENAME = 'gemma-3-270m-it-Q4_K_M.gguf'
MODEL_SHA = 'b1baabd6b729e4041822220d3e648e00d99cac5df86b10dffb77bcccf0688e39'
LOAD3_SHA = '72aed83d1fee53747988f5a4df862467e6ab806518d5e84a9f939ae117d8146e'
MODEL_BYTES = 253115424
WINDOW = 512
BASE = ('--device', 'none', '-ngl', '0', '-fit', 'off',
        '-c', '2048', '-np', '1', '-b', '128', '-ub', '128', '-t', '4', '-tb', '4')
CONFIGS = {'stock': (), 'configured': ('--swa-full', '--ctx-checkpoints', '32')}
QUESTION = (
    'Which object appears in the notebook? Answer in one sentence.',
    'What does the notebook record about its surroundings? Answer in one sentence.',
)
WORDS = ('harbor compass glider meadow barnacle seal tidal beacon estuary anchor pebble notebook '
         'plankton river wave sail current kelp reef marsh chart shore herring cove tide')
INTRO = '<start_of_turn>user\nRead the field notebook below.\n\n'


def check_inputs(output):
    model_file = output / 'assets' / FILENAME
    if model_file.stat().st_size != MODEL_BYTES or bench.digest(model_file) != MODEL_SHA:
        raise ValueError('The local fixture GGUF differs from its published identity')
    model = dict(id=MODEL_ID, name=FILENAME, revision=SOURCE_REVISION,
                 source=f'https://huggingface.co/{MODEL_ID}/resolve/{SOURCE_REVISION}/{FILENAME}',
                 sha256=MODEL_SHA, bytes=MODEL_BYTES, window_tokens=WINDOW,
                 path=str(model_file.relative_to(output)))
    receipt = bench.OUT / '3.load.json'
    if bench.digest(receipt) != LOAD3_SHA:
        raise ValueError('The delivered binary provenance differs from the pinned AQB receipt')
    run = bench.read(receipt)
    provenance = run['factory_provenance']
    executable = next(Path(arg) for arg in run['argv'] if arg.endswith('/llama-server'))
    if bench.digest(executable) != provenance['llama_server_sha256']:
        raise ValueError('The extracted executable differs from the delivered AQB image')
    engine = dict(image_id=provenance['image_id'], sha256=provenance['llama_server_sha256'],
                  source_commit=provenance['source_commit'], executable=str(executable))
    return model, engine


def tokenize(server, content):
    response = server.post(dict(content=content, add_special=True, parse_special=True),
                           path='/tokenize', timeout=30)
    tokens = response['tokens']
    if not isinstance(tokens, list) or not tokens or any(type(token) is not int for token in tokens):
        raise ValueError('The fixture tokenizer did not return a token ID list')
    return tokens


def make_prompts(server):
    target = WINDOW * 3 // 2
    document, ids = fit_notebook(INTRO, '', WORDS, lambda text: tokenize(server, text), target)
    texts = [f'{document}\n\n{question}<end_of_turn>\n<start_of_turn>model\n' for question in QUESTION]
    tokens = [tokenize(server, text) for text in texts]
    common = sum(1 for _ in takewhile(lambda pair: pair[0] == pair[1], zip(*tokens)))
    if not WINDOW < common < min(map(len, tokens)) or abs(common - target) > 8:
        raise ValueError('The two questions do not give the planned ~1.5-window common prompt')
    return dict(window_tokens=WINDOW, document_tokens=len(ids), shared_prefix_tokens=common,
                document=document, questions=list(QUESTION),
                requests=[dict(prompt=text, token_ids=ids) for text, ids in zip(texts, tokens)])


def read_request_cache(raw, expected_tokens):
    """Read the first cached-token count for one completed request."""
    tasks = first_cached_tasks(raw)
    if len(tasks) != 1:
        raise ValueError('The raw log slice does not contain exactly one inference request')
    task = tasks[0]
    count = task.get('cached_tokens')
    if (task['slot_id'] != 0 or task.get('prompt_tokens') != expected_tokens or 'end' not in task
            or type(count) is not int or not 0 <= count < expected_tokens):
        raise ValueError('The task lacks a valid initial cached-token observation')
    return task


def request(server, cell):
    start = server.log.stat().st_size
    timing = lab.request(server, cell['prompt'], 16, benchmark=True, cache_prompt=True)
    # The terminal stream event and server-side task release can be adjacent.
    for _ in range(20):
        with server.log.open('rb') as log:
            log.seek(start)
            raw = log.read()
        if 'stop processing:' in raw.decode(errors='replace'):
            break
        time.sleep(0.05)
    count = len(cell['token_ids'])
    task = read_request_cache(raw, count)
    if timing['generated_tokens'] != 16 or timing['prompt_tokens'] != count - task['cached_tokens']:
        raise ValueError('Fixture completion disagrees with the logged prompt or generation count')
    return dict(timing, tokenized_prompt_tokens=count, cache_prompt=True, server_log_start=start,
                server_log_end=start + len(raw), cache_evidence=task)


def run_config(output, name, model, engine, prompts):
    arm = output / name
    arm.mkdir(exist_ok=False)
    scope = capped_run.RunScope(output, arm, dict(resources=dict(memory_cap=capped_run.CAP,
        need_available_gib=100, device_budget_mib=110000, floor_gib=8, gate_wait_s=120)), uuid4().hex)
    env = dict(capped_run.user_bus_env(), CUDA_VISIBLE_DEVICES='-1')
    record = dict(status='admitting', args=[*BASE, *CONFIGS[name]], server_log=f'{name}/server.log',
                  cache_prompt=True, memory_cap=scope.cap, swap_cap_bytes=0, rows=[])
    receipt = arm / 'receipt.json'
    atomic_json(receipt, record)
    server = None
    try:
        record['gate'] = scope.gate()
        record['status'] = 'launch_reserved'
        atomic_json(receipt, record)
        if bench.digest(Path(engine['executable'])) != engine['sha256']:
            raise ValueError('The delivered executable changed before fixture launch')
        server = capped_run.Server(scope, engine['executable'], str(output / model['path']),
                                   record['args'], env, 'server.log', capture_stdout=True)
        record.update(status='loaded', argv=server.argv, ready_s=server.ready_s, pid=server.proc.pid,
                      cpu_only=dict(cuda_visible_devices=env['CUDA_VISIBLE_DEVICES'], requested_gpu_layers=0))
        startup = server.log.read_text(errors='replace')
        if (not re.search(r'\bn_swa\s*=\s*512\b', startup)
                or re.search(r'offloaded [1-9]\d*/|CUDA\d+\s+(?:model|KV|compute) buffer size', startup)):
            raise ValueError('Server did not confirm the pinned sliding window and CPU-only buffers')
        full_swa = 'using full-size SWA cache' in startup
        if full_swa != (name == 'configured'):
            raise ValueError('Server log shows the other configuration\'s SWA mode')
        record['full_swa'] = full_swa
        if prompts is None:
            prompts = make_prompts(server)
            atomic_json(output / 'prompts.json', prompts)
        for item in prompts['requests']:
            if tokenize(server, item['prompt']) != item['token_ids']:
                raise ValueError('Fixture baseline and configured input tokens differ')
            record['rows'].append(request(server, item))
            atomic_json(receipt, record)
        initial, followup = (row['cache_evidence'] for row in record['rows'])
        if initial['cached_tokens'] != 0 or initial['task_id'] == followup['task_id']:
            raise ValueError('Fixture should start with an empty slot and run two independent tasks')
        record.update(status='complete', cached_tokens=followup['cached_tokens'], prompt_tokens=followup['prompt_tokens'],
                      shared_prefix_tokens=prompts['shared_prefix_tokens'])
    except BaseException as error:
        record.update(status='stopped', error=dict(code=getattr(error, 'code', type(error).__name__), message=str(error)))
        raise
    finally:
        try:
            if server:
                server.close()
                record['server_closed'] = server.proc.poll() is not None
        finally:
            path = arm / 'server.log'
            if path.is_file():
                record['server_log_sha256'] = bench.digest(path)
            atomic_json(receipt, record)
    return record, prompts


def run(output=OUT):
    model, engine = check_inputs(output)
    report = dict(format='muse-cpu-swa-fixture/1', status='admitting', model=model,
                  engine=engine, configurations={}, stage='factory')
    path = output / 'summary.json'
    with QuietLease(bench.BASE/'lab-lease', timeout_s=60):
        with path.open('x', encoding='utf-8') as file:
            json.dump(report, file)
        try:
            prompts = None
            for name in CONFIGS:
                record, prompts = run_config(output, name, model, engine, prompts)
                report['configurations'][name] = record
                atomic_json(path, report)
            report['status'] = 'complete'
        except BaseException as error:
            report.update(status='stopped', error=dict(code=getattr(error, 'code', type(error).__name__), message=str(error)))
            for name in CONFIGS:
                receipt = output / name / 'receipt.json'
                if receipt.is_file():
                    report['configurations'][name] = bench.read(receipt)
            raise
        finally:
            atomic_json(path, report)
            files = {str(file.relative_to(output)): bench.digest(file) for file in sorted(output.rglob('*'))
                     if file.is_file() and file.name != 'manifest.json' and 'assets' not in file.relative_to(output).parts}
            atomic_json(output / 'manifest.json', dict(format='muse-cpu-swa-fixture-manifest/1',
                        status=report['status'], files=files, model_sha256=model['sha256']))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Run both gated CPU configurations once')
    args = parser.parse_args()
    if args.execute:
        def interrupt(_number, _frame):
            raise KeyboardInterrupt('Fixture interrupted')
        signal.signal(signal.SIGTERM, interrupt)
        report = run()
        for name, result in report['configurations'].items():
            print(f'{name}: {result["cached_tokens"]}/{result["prompt_tokens"]} prompt tokens reused')
    else:
        model, engine = check_inputs(OUT)
        print(json.dumps(dict(status='verified_inputs', model=model, engine=engine, configurations=CONFIGS), indent=2))


if __name__ == '__main__':
    main()
