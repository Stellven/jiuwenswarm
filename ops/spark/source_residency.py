#!/usr/bin/env python3
"""Sample external DeepSeek source-page residency without reading tensor payloads."""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import ctypes as C
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import random
import re
import runpy
import subprocess

PAGE = os.sysconf('SC_PAGE_SIZE')
CLASSES = ('expert', 'engram', 'dense')
SCHEMA = 'spark-source-regions/1'
LLAMA_EXPERT = re.compile(r'blk\.\d+\.ffn_(gate|up|down|gate_up)_exps\.weight')
STRATA_EXPERT = re.compile(r'layers\.\d+\.ffn\.experts\.\d+\.w[123]\.weight')


def identity(st):
    return dict(device=st.st_dev, inode=st.st_ino, size=st.st_size, mtime_ns=st.st_mtime_ns)


def merge(spans):
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def file_geometry(path, regions):
    resolved = path.resolve(strict=True)
    file_id = identity(resolved.stat())
    if any(not 0 <= start < end <= file_id['size'] for spans in regions.values() for start, end in spans):
        raise ValueError(f'Tensor extent outside {path}')
    return dict(path=str(path), resolved_path=str(resolved), identity=file_id,
                regions={name: merge(regions[name]) for name in CLASSES})


class ExactHeader:
    """Expose only requested header bytes to the retained GGUF header parser."""
    def __init__(self, fd, size):
        self.fd, self.size = fd, min(size, 16 * 1024**2)

    def __len__(self):
        return self.size

    def __getitem__(self, part):
        return os.pread(self.fd, part.stop - part.start, part.start)


def llama_geometry(model, converter, expert_extents=False):
    converter_bytes = converter.read_bytes()
    converter_sha = hashlib.sha256(converter_bytes).hexdigest()
    retained = runpy.run_path(str(converter))
    reader = retained['GGUFFile']
    shard = retained['SPLIT_RE'].fullmatch(model.name)
    if shard is None or shard['no'] != '00001' or shard['count'] != '00006':
        raise ValueError('Pass the first of the six converted llama.cpp GGUF shards')
    geometry = []
    for number in range(1, 7):
        path = model.parent / f"{shard['prefix']}-{number:05d}-of-00006.gguf"
        regions = defaultdict(list)
        tensors = []
        with path.open('rb', buffering=0) as stream:
            fd = stream.fileno()
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_RANDOM)
            header = reader.__new__(reader)
            header.path = path
            header._parse(ExactHeader(fd, os.fstat(fd).st_size))
            for name, (offset, shape, _, length) in header.tensors.items():
                kind = ('expert' if LLAMA_EXPERT.fullmatch(name) else 'engram'
                        if name == retained['TABLE'] or '.engram_' in name else 'dense')
                regions[kind].append((offset, offset + length))
                if expert_extents and kind == 'expert':
                    tensors.append(dict(name=name, offset=offset, length=length, shape=shape))
        source = file_geometry(path, regions)
        if expert_extents:
            source['expert_tensors'] = tensors
        geometry.append(source)
    return dict(files=geometry, converter=str(converter), converter_sha256=converter_sha)


def strata_geometry(pack):
    settings = (pack / 'ds4.txt').read_bytes()
    index = (pack / 'tensors.txt').read_bytes()
    config = dict(line.split(' ', 1) for line in settings.decode().splitlines() if ' ' in line)
    model_dir = Path(config['model_dir'])
    files, rows, excluded = {}, defaultdict(lambda: defaultdict(list)), []
    for line in index.decode().splitlines():
        parts = line.split()
        if parts and parts[0] == 'file':
            files[int(parts[1])] = model_dir / parts[2]
        elif parts and parts[0] == 't':
            _, name, _, file_id, offset, length, *_ = parts
            file_id, offset, length = map(int, (file_id, offset, length))
            if 'dspark-' in files[file_id].name:
                continue  # Fair S uses --dspark none.
            kind = 'expert' if STRATA_EXPERT.fullmatch(name) else 'engram' if '.engram.' in name else 'dense'
            rows[file_id][kind].append((offset, offset + length))
    geometry = []
    for file_id, path in sorted(files.items()):
        if file_id not in rows:
            excluded.append(str(path))
        else:
            geometry.append(file_geometry(path, rows[file_id]))
    engram_index = pack / 'engram.bin'
    geometry.append(file_geometry(engram_index, defaultdict(list, engram=[(0, engram_index.stat().st_size)])))
    return dict(files=geometry, settings_sha256=hashlib.sha256(settings).hexdigest(),
                tensor_index_sha256=hashlib.sha256(index).hexdigest(), pack=str(pack),
                files_without_active_tensors=excluded)


class Mincore:
    def __init__(self):
        self.lib = C.CDLL(None, use_errno=True)
        self.lib.mmap.argtypes = [C.c_void_p, C.c_size_t, C.c_int, C.c_int, C.c_int, C.c_long]
        self.lib.mmap.restype = C.c_void_p
        self.lib.mincore.argtypes = [C.c_void_p, C.c_size_t, C.POINTER(C.c_ubyte)]
        self.lib.munmap.argtypes = [C.c_void_p, C.c_size_t]

    def inspect(self, source, stride, seed, expert_pages=None):
        fd = os.open(source['path'], os.O_RDONLY | os.O_CLOEXEC)
        address = None
        extent = source['identity']['size']
        try:
            stat = os.fstat(fd)
            if identity(stat) != source['identity']:
                raise ValueError(f'Source inode changed: {source["path"]}')
            # Linux can return an all-resident vector for files the caller may
            # neither own nor write. Refuse to interpret those vectors.
            if stat.st_uid != os.geteuid() and not os.access(source['path'], os.W_OK, effective_ids=True):
                raise PermissionError(f'mincore disclosure permission unavailable: {source["path"]}')
            address = self.lib.mmap(None, extent, mmap.PROT_READ, mmap.MAP_PRIVATE, fd, 0)
            if address == C.c_void_p(-1).value:
                address = None
                raise OSError(C.get_errno(), 'mmap failed')
            return {kind: self.sample_region(address, spans, stride, f'{seed}/{kind}',
                                             expert_pages if kind == 'expert' else None)
                    for kind, spans in source['regions'].items()}
        finally:
            if address is not None:
                self.lib.munmap(address, extent)
            os.close(fd)

    def sample_region(self, address, spans, stride, seed, page_observations=None):
        pages = merge((start // PAGE, (end + PAGE - 1) // PAGE) for start, end in spans)
        ends = []
        total_pages = 0
        for start, end in pages:
            total_pages += end - start
            ends.append(total_pages)
        rng = random.Random(seed)
        flag = C.c_ubyte()
        hits = samples = estimated_pages = 0
        for begin in range(0, total_pages, stride):
            stop = min(begin + stride, total_pages)
            ordinal = rng.randrange(begin, stop)
            index = bisect_right(ends, ordinal)
            page = pages[index][1] - (ends[index] - ordinal)
            if self.lib.mincore(address + page * PAGE, PAGE, C.byref(flag)) != 0:
                raise OSError(C.get_errno(), 'mincore failed')
            resident = flag.value & 1
            if page_observations is not None:
                page_observations.append((page, stop - begin, resident))
            hits += resident
            samples += 1
            estimated_pages += (stop - begin) * resident
        return dict(payload_bytes=sum(end - start for start, end in spans), intersecting_pages=total_pages,
                    sampled_pages=samples, resident_sampled_pages=hits, estimated_resident_pages=estimated_pages)


def cgroup_accounting(scope):
    path = Path(json.loads(scope.read_text())['cgroup']).resolve(strict=True)
    if not path.is_relative_to('/sys/fs/cgroup') or not path.name.startswith('spark-capped-'):
        raise ValueError('Scope receipt does not name a Spark capped cgroup')
    stat = dict(line.split() for line in (path / 'memory.stat').read_text().splitlines())
    return dict(path=str(path), memory_current_bytes=int((path / 'memory.current').read_text()),
                stat_bytes={name: int(stat[name]) for name in ('file', 'anon', 'file_mapped', 'shmem') if name in stat})


def snapshot(geometry, view, stride, seed, scope):
    if geometry['schema'] != SCHEMA or stride < 1:
        raise ValueError('Expected a source region manifest and positive sampling step')
    selected = [name for name in ('llama', 'strata') if view in (name, 'both')]
    files = [f for name in selected for f in geometry['views'][name]['files']]
    if sum((f['identity']['size'] // PAGE + stride - 1) // stride for f in files) > 100_000:
        raise ValueError('Sampling is limited to 100,000 source pages; increase --pages-per-sample')
    reader = Mincore()
    observations = {}
    started = datetime.now(timezone.utc).isoformat()
    for name in selected:
        found = []
        total = defaultdict(Counter)
        for source in geometry['views'][name]['files']:
            expert_pages = [] if name == 'llama' and os.getenv('SPARK_EXPERT_SAMPLE_DETAIL') == '1' else None
            measured = reader.inspect(source, stride, seed, expert_pages)
            file_result = {k: source[k] for k in ('path', 'resolved_path', 'identity')} | {'regions': measured}
            if expert_pages is not None:
                # Reuse the existing mincore observations; no additional page queries or payload reads.
                file_result['expert_sample_columns'] = ['page_index', 'stratum_pages', 'resident']
                file_result['expert_page_samples'] = expert_pages
            found.append(file_result)
            for kind, values in measured.items():
                total[kind].update(values)
        summary = {}
        for kind, values in total.items():
            pages = values['intersecting_pages']
            summary[kind] = dict(values, estimated_resident_fraction=values['estimated_resident_pages'] / pages if pages else None)
        observations[name] = dict(total=summary, files=found)
    return dict(schema='spark-source-residency/1', scope='Linux host/inode file page cache', started=started,
                completed=datetime.now(timezone.utc).isoformat(), page_size=PAGE, pages_per_sample=stride,
                seed=seed, method='One deterministic random page per fixed-size stratum, weighted by stratum pages',
                views=observations, scope_accounting=cgroup_accounting(scope) if scope else None,
                limitations='Resident source pages are distinct from cgroup charges, process RSS and GPU residency. '
                'Snapshots span multiple syscalls. Categories can overlap on a tensor boundary page. '
                'The same page IDs are resampled across repeated snapshots for each geometry.')


def cold_start(geometry, stride, seed, pooled_screen=False):
    """Advise eviction of only the indexed model files, between capped launches."""
    lock_path = Path.home() / 'predemo-spark/gpu.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        quiet = subprocess.run([str(Path(__file__).parent / 'bin/quiet')],
                               capture_output=True, text=True, check=not pooled_screen)
        preflight = json.loads(quiet.stdout)
        if pooled_screen and (quiet.returncode not in (0, 1) or preflight['model_processes'] or preflight['mem_available_gib'] < 110):
            raise ValueError('Pooled screening source conditioning requires no other model and at least 110 GiB available')
        before = snapshot(geometry, 'both', stride, seed, None)
        files = {}
        for view in geometry['views'].values():
            for item in view['files']:
                files[item['resolved_path']] = item['identity']
        for path, expected in files.items():
            with open(path, 'rb') as source:
                if identity(os.fstat(source.fileno())) != expected:
                    raise ValueError(f'Source file identity changed: {path}')
                os.posix_fadvise(source.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        after = snapshot(geometry, 'both', stride, seed, None)
        return {'schema': 'spark-source-cache-conditioning/1', 'method': 'file-specific POSIX_FADV_DONTNEED',
                'quiet': preflight, 'advised_files': sorted(files),
                'before': before, 'after': after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    index = modes.add_parser('index')
    index.add_argument('--llama-model', type=Path, required=True)
    index.add_argument('--converter', type=Path, required=True)
    index.add_argument('--strata-pack', type=Path, required=True)
    index.add_argument('--out', type=Path, required=True)
    sample = modes.add_parser('sample')
    sample.add_argument('--regions', type=Path, required=True)
    sample.add_argument('--view', choices=['llama', 'strata', 'both'], default='both')
    sample.add_argument('--pages-per-sample', type=int, default=4096)
    sample.add_argument('--seed', type=int, default=20261120)
    sample.add_argument('--scope-json', type=Path)
    sample.add_argument('--out', type=Path, required=True)
    reset = modes.add_parser('cold-start')
    reset.add_argument('--regions', type=Path, required=True)
    reset.add_argument('--pages-per-sample', type=int, default=4096)
    reset.add_argument('--seed', type=int, default=20261120)
    reset.add_argument('--out', type=Path, required=True)
    reset.add_argument('--pooled-screen', action='store_true', help='Record CPU overlap for the candidate-only screen')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a new output file')
    if args.mode == 'index':
        result = dict(schema=SCHEMA, views=dict(llama=llama_geometry(args.llama_model.absolute(), args.converter.resolve()),
                                               strata=strata_geometry(args.strata_pack.resolve())))
    else:
        raw = args.regions.read_bytes()
        geometry = json.loads(raw)
        if args.mode == 'cold-start':
            result = cold_start(geometry, args.pages_per_sample, args.seed, args.pooled_screen)
        else:
            result = snapshot(geometry, args.view, args.pages_per_sample, args.seed, args.scope_json)
        result['regions_sha256'] = hashlib.sha256(raw).hexdigest()
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
