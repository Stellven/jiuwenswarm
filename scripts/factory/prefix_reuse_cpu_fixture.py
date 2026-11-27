"""Gated factory-stage SWA fixture using the delivered engine executable on CPU."""

import argparse
from itertools import takewhile
import json
from pathlib import Path
import signal
import time
from uuid import uuid4

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.lab_lifecycle import QuietLease, atomic_json
from jiuwenswarm.factory.ccs.kv_reuse_lab.cpu_fixture import read_request_cache, verify, verify_mode
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
        record['full_swa'] = verify_mode(startup, model['window_tokens'], configured=name == 'configured')
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


def recorded_evidence(output):
    """Regenerate a portable verifier packet from the sealed Spark evidence."""
    manifest = bench.read(output / 'manifest.json')
    required = {'summary.json', 'prompts.json', *(f'{name}/server.log' for name in CONFIGS)}
    if manifest['status'] != 'complete' or not required <= manifest['files'].keys():
        raise ValueError('Recorded CPU fixture evidence is incomplete')
    for name, digest in manifest['files'].items():
        path = output / name
        if (not path.resolve().is_relative_to(output.resolve()) or path.is_symlink()
                or bench.digest(path) != digest):
            raise ValueError(f'CPU fixture file changed: {name}')
    summary = bench.read(output / 'summary.json')
    prompts = bench.read(output / 'prompts.json')
    if summary['model']['sha256'] != manifest['model_sha256']:
        raise ValueError('CPU fixture model identity differs from the sealed evidence')
    configurations = {}
    for name, flags in CONFIGS.items():
        arm = summary['configurations'][name]
        if (arm['args'] != [*BASE, *flags] or arm['status'] != 'complete' or arm['server_closed'] is not True
                or arm['server_log'] != f'{name}/server.log'
                or arm['server_log_sha256'] != manifest['files'][arm['server_log']]):
            raise ValueError(f'{name}: Recorded CPU configuration is inconsistent')
        args = arm['argv']
        model_index = args.index('-m')
        fit_index = args.index('-fitt', model_index + 2)
        if (args[model_index - 1] != summary['engine']['executable']
                or Path(args[model_index + 1]) != output / summary['model']['path']
                or args[model_index + 2:fit_index] != ['-lm', 'mmap', *arm['args']]
                or arm['gate']['ok'] is not True or 'MemoryMax=96G' not in args or 'MemorySwapMax=0' not in args):
            raise ValueError(f'{name}: Recorded CPU executable, model or arguments differ')
        raw = (output / arm['server_log']).read_bytes()
        rows = arm['rows']
        first, second = rows
        if not 0 <= first['server_log_start'] < first['server_log_end'] <= second['server_log_start'] < second['server_log_end'] <= len(raw):
            raise ValueError(f'{name}: Recorded server log intervals are invalid')
        slices = [raw[row['server_log_start']:row['server_log_end']].decode(errors='replace') for row in rows]
        configurations[name] = dict(model_sha256=summary['model']['sha256'],
                                    executable_sha256=summary['engine']['sha256'],
                                    extra_args=list(flags), cache_prompt=arm['cache_prompt'],
                                    startup_log=raw[:first['server_log_start']].decode(errors='replace'),
                                    request_logs=slices)
    return dict(model=summary['model'], executable_sha256=summary['engine']['sha256'],
                request_tokens=[row['token_ids'] for row in prompts['requests']], configurations=configurations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument('--execute', action='store_true', help='Run both gated CPU configurations once')
    commands.add_argument('--verify', action='store_true', help='Check existing evidence without starting a process')
    args = parser.parse_args()
    if args.execute:
        def interrupt(_number, _frame):
            raise KeyboardInterrupt('Fixture interrupted')
        signal.signal(signal.SIGTERM, interrupt)
        report = run()
        for name, result in report['configurations'].items():
            print(f'{name}: {result["cached_tokens"]}/{result["prompt_tokens"]} prompt tokens reused')
    elif args.verify:
        print(json.dumps(verify(recorded_evidence(OUT)), indent=2))
    else:
        model, engine = check_inputs(OUT)
        print(json.dumps(dict(status='verified_inputs', model=model, engine=engine, configurations=CONFIGS), indent=2))


if __name__ == '__main__':
    main()
