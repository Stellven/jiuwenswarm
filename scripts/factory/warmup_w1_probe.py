"""Read-only Linux residency, process memory, and timestamp probes for W1."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import stat
import time


PAGE_SIZE = os.sysconf('SC_PAGE_SIZE')
CHUNK_BYTES = (1 << 30) // PAGE_SIZE * PAGE_SIZE
LOW_BITS = bytes(value & 1 for value in range(256))
MAP_FAILED = ctypes.c_void_p(-1).value
LOG_TIME = re.compile(r'^(\d+)\.([0-5]\d)\.(\d{3})\.(\d{3})\s+[IDWE]\s+')
PROC_MEMORY = {
    'VmRSS': 'rss_bytes', 'VmHWM': 'peak_rss_bytes', 'VmSize': 'virtual_bytes',
    'RssAnon': 'anonymous_rss_bytes', 'RssFile': 'file_rss_bytes', 'RssShmem': 'shared_rss_bytes',
    'VmSwap': 'swap_bytes',
}
SCOPE_MEMORY = {
    'memory.current': 'current_bytes', 'memory.peak': 'peak_bytes', 'memory.max': 'max_bytes',
    'memory.swap.current': 'swap_current_bytes', 'memory.swap.max': 'swap_max_bytes',
}
COUNTER_REASON = (
    'The pinned AQB build exposes MoE hit and miss totals only when its cache is destroyed. '
    'The server metrics and slots interfaces do not export MoE hit or miss counters.'
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


@lru_cache(maxsize=1)
def libc():
    functions = ctypes.CDLL(None, use_errno=True)
    functions.mmap.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_longlong)
    functions.mmap.restype = ctypes.c_void_p
    functions.mincore.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p)
    functions.mincore.restype = ctypes.c_int
    functions.munmap.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    functions.munmap.restype = ctypes.c_int
    return functions


def syscall_error(operation, path):
    errno = ctypes.get_errno()
    return OSError(errno, f'{operation}: {os.strerror(errno)}', path)


def shard_residency(path, expected_size):
    """Map without access permissions and query Linux's file cache without reading it."""
    ops = libc()
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size:
            raise ValueError(f'Residency source differs from the pinned shard size: {path.name}')
        # Linux can return a synthetic all-resident vector when neither the
        # owner/capability nor the inode write-permission test passes.
        if info.st_uid != os.geteuid() and not os.access(f'/proc/self/fd/{fd}', os.W_OK, effective_ids=True):
            raise PermissionError(f'Insufficient permission for a trustworthy mincore sample: {path.name}')
        resident_pages = 0
        partial_page_bytes = 0
        vector = ctypes.create_string_buffer((min(CHUNK_BYTES, expected_size) + PAGE_SIZE - 1) // PAGE_SIZE)
        for offset in range(0, expected_size, CHUNK_BYTES):
            length = min(CHUNK_BYTES, expected_size - offset)
            pages = (length + PAGE_SIZE - 1) // PAGE_SIZE
            address = ops.mmap(None, length, 0, mmap.MAP_SHARED, fd, offset)
            if address == MAP_FAILED:
                raise syscall_error('mmap', path)
            try:
                if ops.mincore(address, length, vector):
                    raise syscall_error('mincore', path)
                page_flags = ctypes.string_at(vector, pages).translate(LOW_BITS)
                resident_pages += page_flags.count(b'\x01')
                remainder = length % PAGE_SIZE
                if remainder and page_flags[-1]:
                    partial_page_bytes = PAGE_SIZE - remainder
            finally:
                if ops.munmap(address, length):
                    raise syscall_error('munmap', path)
        if os.fstat(fd).st_size != expected_size:
            raise ValueError(f'Shard size changed during residency sampling: {path.name}')
    finally:
        os.close(fd)
    return dict(name=path.name, file_bytes=expected_size, resident_pages=resident_pages,
                total_pages=(expected_size + PAGE_SIZE - 1) // PAGE_SIZE,
                resident_bytes=resident_pages * PAGE_SIZE - partial_page_bytes)


def pack_residency(manifest_path, expected_sha256=None):
    """Sample every named shard; verify the manifest pin without reading tensor bytes."""
    manifest_path = Path(manifest_path).resolve(strict=True)
    with manifest_path.open('rb') as stream:
        raw = stream.read((1 << 20) + 1)
    if len(raw) > 1 << 20:
        raise ValueError('Pack manifest exceeds the residency probe size limit')
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Pack manifest SHA-256 differs from the W1 pin')
    manifest = json.loads(raw)
    files = manifest['files']
    if not isinstance(files, list) or not files:
        raise ValueError('Pack manifest has no shards')
    paths = {}
    for shard in files:
        name, size = shard['name'], shard['bytes']
        if not isinstance(name, str) or not name or Path(name).name != name or name in ('.', '..') or name in paths:
            raise ValueError('Pack manifest must name unique shard basenames')
        if type(size) is not int or size <= 0:
            raise ValueError(f'Invalid file size for pinned shard: {name}')
        paths[name] = size
    if sum(paths.values()) != manifest['bytes']:
        raise ValueError('Pack manifest total disagrees with its shard sizes')

    started_utc, started = utc_now(), time.monotonic()
    shards = [shard_residency(manifest_path.parent / name, size) for name, size in paths.items()]
    resident_bytes = sum(row['resident_bytes'] for row in shards)
    return dict(status='measured', method='linux_mincore_prot_none', started_utc=started_utc, finished_utc=utc_now(),
                elapsed_s=round(time.monotonic() - started, 6), manifest=str(manifest_path), manifest_sha256=digest,
                page_size_bytes=PAGE_SIZE, shard_count=len(shards), total_bytes=manifest['bytes'],
                total_pages=sum(row['total_pages'] for row in shards), resident_bytes=resident_bytes,
                resident_pages=sum(row['resident_pages'] for row in shards),
                resident_fraction=resident_bytes / manifest['bytes'], shards=shards)


def process_identity(pid, proc_root, executable):
    """Resolve the launched executable through the scoped wrapper's child tree."""
    seen, matches, pending = set(), [], [pid]
    while pending:
        child = pending.pop()
        if child in seen:
            continue
        seen.add(child)
        node = proc_root / str(child)
        try:
            actual = (node / 'exe').readlink()
            if actual == executable:
                matches.append(child)
            else:
                children = node / 'task' / str(child) / 'children'
                pending.extend(int(token) for token in children.read_text().split())
        except FileNotFoundError:
            continue  # descendants can finish while the scope is read
    if len(matches) != 1:
        raise ValueError('Could not match exactly one running llama-server to the capped wrapper')
    return matches[0]


def process_memory(node):
    values = {}
    for line in (node / 'status').read_text().splitlines():
        label, _, rest = line.partition(':')
        if label in PROC_MEMORY:
            value, unit = rest.split()
            if unit != 'kB':
                raise ValueError(f'Unexpected /proc memory unit for {label}')
            values[PROC_MEMORY[label]] = int(value) * 1024
    if not {'rss_bytes', 'peak_rss_bytes'} <= values.keys():
        raise ValueError('llama-server /proc/status lacks resident memory counters')
    stat_fields = (node / 'stat').read_text().rpartition(') ')[2].split()
    values.update(minor_faults=int(stat_fields[7]), major_faults=int(stat_fields[9]),
                  starttime_ticks=int(stat_fields[19]))
    return values


def scope_memory(node, unit, cgroup_root):
    membership = next((line[3:] for line in (node / 'cgroup').read_text().splitlines()
                       if line.startswith('0::')), None)
    if not membership:
        raise ValueError('llama-server has no cgroup v2 membership')
    group = Path(membership)
    if not group.is_absolute() or '..' in group.parts or group.name != unit:
        raise ValueError('llama-server cgroup differs from the named capped scope')
    path = cgroup_root / group.relative_to('/')
    values = {}
    for file, key in SCOPE_MEMORY.items():
        try:
            data = (path / file).read_text().strip()
        except FileNotFoundError:
            if file in ('memory.peak', 'memory.swap.current'):
                continue  # optional accounting, on kernels without the corresponding counter
            raise
        values[key] = data if data == 'max' and file.endswith('.max') else int(data)
    return dict(cgroup=membership, unit=unit, **values)


def server_memory(server, *, proc_root=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup')):
    """Measure both the llama-server PID and its exact MemoryMax/MemorySwapMax scope."""
    unit_arg = server.argv.index('--unit')
    unit = server.argv[unit_arg + 1]
    if not unit.endswith('.scope'):
        unit += '.scope'
    executable = Path(server.argv[unit_arg + 2]).resolve(strict=True)
    wrapper_pid = server.proc.pid
    pid = process_identity(wrapper_pid, proc_root, executable)
    node = proc_root / str(pid)
    memory = process_memory(node)
    scope = scope_memory(node, unit, cgroup_root)
    return dict(status='measured', sampled_utc=utc_now(), wrapper_pid=wrapper_pid, server_pid=pid,
                process=memory, scope=scope)


def log_event(line, number, marker):
    timestamp = LOG_TIME.match(line)
    if not timestamp or marker not in line[timestamp.end():]:
        return None
    minutes, seconds, millis, micros = map(int, timestamp.groups())
    elapsed_us = ((minutes * 60 + seconds) * 1000 + millis) * 1000 + micros
    return dict(line=number, timestamp=timestamp[0].split()[0], elapsed_us=elapsed_us, marker=marker)


def startup_warmup(log):
    """Read logger-relative startup milestones; slot init bounds the empty-run interval."""
    start = end = ready = None
    with Path(log).open(encoding='utf-8', errors='replace') as stream:
        for number, line in enumerate(stream, 1):
            marker = log_event(line, number, 'warming up the model with an empty run')
            if marker:
                if start:
                    raise ValueError('Multiple empty-run starts in one W1 server log')
                start = marker
            if start and not end:
                end = log_event(line, number, 'load_model: initializing, n_slots =')
            if ready := log_event(line, number, 'server_on_li: listening on'):
                break
    if not start or not end or not ready:
        return dict(status='unavailable', reason='Missing timestamped warmup, slot initialization or listening marker',
                    start=start, end=end, ready=ready)
    if not start['elapsed_us'] <= end['elapsed_us'] <= ready['elapsed_us']:
        raise ValueError('Warmup and readiness timestamps are out of order')
    return dict(status='bounded', elapsed_s=(end['elapsed_us'] - start['elapsed_us']) / 1e6,
                log_listening_elapsed_s=ready['elapsed_us'] / 1e6,
                method='empty-run marker to first slot initialization, including intervening setup',
                start=start, end=end, ready=ready)


def counter_probe(server, log_start=None, log_end=None):
    """Pinned AQB has no request-granularity counters; skip without touching the server."""
    return dict(status='unavailable', reason=COUNTER_REASON)


def counter_delta(before, after):
    """No delta is available for the pinned build's lifetime-only counters."""
    return dict(status='unavailable', reason=COUNTER_REASON)
