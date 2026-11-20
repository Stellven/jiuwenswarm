#!/usr/bin/env python3
"""Replay selected expert uploads from a llama.cpp recorder trace against the source GGUF."""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import ctypes as C
import hashlib
import itertools
import json
import mmap
from pathlib import Path
import runpy
import statistics
import time


def copy_groups(event, tensors):
    ids = sorted({expert for row in event['expert_ids'] for expert in row})
    copies = []
    for role in ('gate', 'up', 'down'):
        name = f"blk.{event['layer']}.ffn_{role}_exps.weight"
        shard, (offset, shape, _, size) = tensors[name]
        count = shape[2]
        stride, remainder = divmod(size, count)
        if remainder or min(ids) < 0 or max(ids) >= count:
            raise ValueError(f'Invalid IDs or tensor stride for {name}')
        for _, group in itertools.groupby(enumerate(ids), key=lambda pair: pair[1] - pair[0]):
            consecutive = [expert for _, expert in group]
            first, last = consecutive[0], consecutive[-1]
            length = len(consecutive) * stride + (min(512, stride) if last + 1 < count else 0)
            copies.append((shard, offset + first * stride, first * stride, length))
    return copies


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events', required=True, type=Path)
    p.add_argument('--model', required=True, type=Path, help='First GGUF shard from the recorded run')
    p.add_argument('--converter', required=True, type=Path, help='Original conversion tool with GGUFFile header reader')
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--plan-only', action='store_true')
    args = p.parse_args()
    reader = runpy.run_path(str(args.converter))['GGUFFile']
    paths = sorted(args.model.parent.glob(args.model.name.replace('00001-of-', '*-of-')))
    tensors = {name: (i, info) for i, path in enumerate(paths) for name, info in reader(path).tensors.items()}
    events = [json.loads(line) for line in args.events.read_bytes().splitlines()]
    summary = events.pop()
    if summary['type'] != 'summary' or summary['lost'] or summary['transfer_incomplete']:
        raise ValueError('Expected a complete recorder trace with known submitted byte counts')
    batches = defaultdict(list)
    for ev in events:
        if ev['bytes_transferred'] == 0:
            continue
        copies = copy_groups(ev, tensors)
        if sum(item[-1] for item in copies) != ev['bytes_transferred']:
            raise ValueError(f"Reconstructed bytes disagree at layer {ev['layer']} microbatch {ev['microbatch']}")
        batches[ev['microbatch'], ev['layer']].extend(copies)
    total = sum(item[-1] for copies in batches.values() for item in copies)
    if total != summary['bytes_transferred'] or total <= 0:
        raise ValueError('Reconstructed bytes disagree with recorder summary')
    record = {'schema':'spark-mmap-expert-copy-replay/1', 'event_sha256':hashlib.sha256(args.events.read_bytes()).hexdigest(),
              'converter_sha256':hashlib.sha256(args.converter.read_bytes()).hexdigest(),
              'shards':list(map(str, paths)), 'submitted_bytes':total, 'groups':len(batches),
              'copy_calls':sum(map(len,batches.values())), 'samples':[],
              'scope':'Replay of traced copy ranges from original pageable file mappings. One CUDA stream, synchronized per nonempty layer and microbatch; reusable destination buffer, no concurrent model compute. First pass includes uncontrolled file residency. Later passes reuse those pages.'}
    if not args.plan_only:
        if 'spark-capped-' not in Path('/proc/self/cgroup').read_text():
            raise SystemExit('Run memory and CUDA workload under bin/capped')
        lib = C.CDLL('/usr/local/cuda/lib64/libcudart.so')
        def cuda(name, *values):
            error = getattr(lib, name)(*values)
            if error:
                raise RuntimeError(f'{name} returned CUDA error {error}')
        with ExitStack() as stack:
            addresses = []
            for path in paths:
                src = stack.enter_context(path.open('rb'))
                pages = stack.enter_context(mmap.mmap(src.fileno(), 0, access=mmap.ACCESS_COPY))
                addresses.append(C.addressof(C.c_char.from_buffer(pages)))
            device, stream = C.c_void_p(), C.c_void_p()
            required = max(dst+n for copies in batches.values() for _, _, dst,n in copies)
            cuda('cudaMalloc', C.byref(device), C.c_size_t(required))
            stack.callback(cuda, 'cudaFree', device)
            cuda('cudaStreamCreateWithFlags', C.byref(stream), 1)
            stack.callback(cuda, 'cudaStreamDestroy', stream)
            for repetition in range(4):
                start = time.perf_counter()
                for copies in batches.values():
                    for i, src, dst, size in copies:
                        cuda('cudaMemcpyAsync', C.c_void_p(device.value+dst), C.c_void_p(addresses[i]+src), C.c_size_t(size), 1, stream)
                    cuda('cudaStreamSynchronize', stream)
                elapsed = time.perf_counter() - start
                sample = dict(pass_index=repetition, wall_s=elapsed, measured_GB_s=total/elapsed/1e9)
                record['samples'].append(sample)
                print(json.dumps(sample),flush=True)
            record['warm_median_GB_s'] = statistics.median(row['measured_GB_s'] for row in record['samples'][1:])
    with args.out.open('x') as output:
        json.dump(record, output, indent=2)
        output.write('\n')
    print(total, 'submitted bytes verified', flush=True)


if __name__ == '__main__':
    main()
