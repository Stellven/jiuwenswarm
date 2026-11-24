#!/usr/bin/env python3
"""Unprivileged Linux file page-cache measurement and preparation (Python 3.10)."""
import argparse
import ctypes
import json
import mmap
import os
import time


PAGE_SIZE = mmap.PAGESIZE
WINDOW_BYTES = 1024 ** 3
_RESIDENT_BITS = bytes(i & 1 for i in range(256))
_libc = ctypes.CDLL(None, use_errno=True)
_libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                       ctypes.c_int, ctypes.c_int, ctypes.c_longlong]
_libc.mmap.restype = ctypes.c_void_p
_libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                          ctypes.POINTER(ctypes.c_ubyte)]
_libc.mincore.restype = ctypes.c_int
_libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
_libc.munmap.restype = ctypes.c_int


def _check_ranges(ranges, file_bytes):
    if not isinstance(ranges, list):
        raise ValueError('ranges must be a JSON list of {name, offset, size}')
    for row in ranges:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str):
            raise ValueError('each range needs a string name')
        for key in ('offset', 'size'):
            value = row.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f'range {key} must be a nonnegative integer')
        if row['offset'] + row['size'] > file_bytes:
            raise ValueError(f'range {row["name"]!r} extends beyond EOF')
    return ranges


def load_ranges(path):
    with open(path) as stream:
        return json.load(stream)


def _measure(fd, offset, size):
    """Map without touching data; bound both mapping and mincore vector size."""
    started = time.monotonic()
    end = offset + size
    cursor = offset - offset % PAGE_SIZE
    resident_bytes = pages = 0
    while size and cursor < end:
        length = min(WINDOW_BYTES, end - cursor)
        count = (length + PAGE_SIZE - 1) // PAGE_SIZE
        address = _libc.mmap(None, length, mmap.PROT_READ, mmap.MAP_SHARED, fd, cursor)
        if address == ctypes.c_void_p(-1).value:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))
        try:
            vector = (ctypes.c_ubyte * count)()
            if _libc.mincore(address, length, vector) != 0:
                errno = ctypes.get_errno()
                raise OSError(errno, os.strerror(errno))
            # Count in C rather than looping over millions of pages in Python.
            resident_bytes += bytes(vector).translate(_RESIDENT_BITS).count(b'\x01') * PAGE_SIZE
            if cursor < offset and vector[0] & 1:
                resident_bytes -= offset - cursor
            if cursor + count * PAGE_SIZE > end and vector[-1] & 1:
                resident_bytes -= cursor + count * PAGE_SIZE - end
            pages += count
        finally:
            _libc.munmap(address, length)
        cursor += length
    return dict(file_bytes=size, resident_bytes=resident_bytes,
                resident_pct=100 * resident_bytes / size if size else 0.0,
                pages=pages, elapsed_ms=(time.monotonic() - started) * 1000)


def resident(path, ranges=None):
    """Return file residency; optional ranges are measured independently."""
    with open(path, 'rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        if ranges is not None:
            _check_ranges(ranges, size)
        result = _measure(stream.fileno(), 0, size)
        if ranges is not None:
            result['ranges'] = [dict(_measure(stream.fileno(), r['offset'], r['size']),
                                     name=r['name'], offset=r['offset'], size=r['size'])
                                for r in ranges]
        return result


def evict(path):
    """Request eviction of clean pages, with observations rather than a guarantee."""
    before = resident(path)
    with open(path, 'rb') as stream:
        os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    return {'before': before, 'after': resident(path)}


def warm(path, ranges=None, prefix_bytes=None):
    """Read exactly the chosen ranges or prefix, in ascending file order."""
    if (ranges is None) == (prefix_bytes is None):
        raise ValueError('warm requires exactly one of ranges or prefix_bytes')
    started = time.monotonic()
    total = 0
    with open(path, 'rb', buffering=0) as stream:
        size = os.fstat(stream.fileno()).st_size
        if prefix_bytes is not None:
            if (not isinstance(prefix_bytes, int) or isinstance(prefix_bytes, bool)
                    or prefix_bytes < 0):
                raise ValueError('prefix_bytes must be a nonnegative integer')
            ranges = [dict(name='prefix', offset=0, size=min(prefix_bytes, size))]
        _check_ranges(ranges, size)
        for row in sorted(ranges, key=lambda r: r['offset']):
            stream.seek(row['offset'])
            remaining = row['size']
            while remaining:
                data = stream.read(min(1024 ** 2, remaining))
                if not data:
                    raise OSError('unexpected EOF while warming')
                remaining -= len(data)
                total += len(data)
    return dict(read_bytes=total, elapsed_ms=(time.monotonic() - started) * 1000,
                ranges=ranges, after=resident(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['resident', 'evict', 'warm'])
    parser.add_argument('file')
    parser.add_argument('--json', action='store_true')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--ranges', help='JSON list of {name, offset, size}')
    selection.add_argument('--prefix-bytes', type=int)
    args = parser.parse_args()
    try:
        ranges = load_ranges(args.ranges) if args.ranges else None
        if args.action == 'resident':
            if args.prefix_bytes is not None:
                raise ValueError('--prefix-bytes is for warm only')
            result = resident(args.file, ranges)
        elif args.action == 'evict':
            if args.ranges or args.prefix_bytes is not None:
                raise ValueError('evict operates on the whole file')
            result = evict(args.file)
        else:
            result = warm(args.file, ranges, args.prefix_bytes)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'page_cache: {exc}\n')
    print(json.dumps(result, indent=None if args.json else 2))


if __name__ == '__main__':
    main()
