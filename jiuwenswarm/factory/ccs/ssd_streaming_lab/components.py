"""Bounded positional reads and an explicitly separate replay cost model."""
from concurrent.futures import ThreadPoolExecutor, CancelledError
import math
import os
import tempfile
import threading


def integer(value, name, low=0, high=2**40):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name + ' must be a bounded integer')
    return value


def ranges_validate(ranges):
    if not isinstance(ranges, list) or len(ranges) > 10000:
        raise ValueError('ranges must be a list of at most 10000 [offset,length] pairs')
    result = []
    for pair in ranges:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('expected [offset,length]')
        result.append((integer(pair[0], 'offset'), integer(pair[1], 'length', 1, 16*1024*1024)))
    return result


def coalesce(ranges, max_gap=0, max_read_bytes=16*1024*1024):
    integer(max_gap, 'max_gap', 0, 1024*1024)
    integer(max_read_bytes, 'max_read_bytes', 1, 16*1024*1024)
    merged = []
    for offset, length in sorted(ranges_validate(ranges)):
        if length > max_read_bytes:
            raise ValueError('individual read exceeds max_read_bytes')
        end = offset + length
        if merged and offset <= merged[-1][1] + max_gap and max(end, merged[-1][1])-merged[-1][0] <= max_read_bytes:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([offset, end])
    return [(start, end-start) for start, end in merged]


class BoundedPread:
    """Caller-owned descriptor; bounded submitted work and bytes, cancellable queued I/O.

    Running POSIX pread cannot be interrupted. cancel() marks queued/running results
    unusable; close() waits for workers before caller may close the descriptor.
    """
    def __init__(self, fd, workers=2, max_inflight=4, max_inflight_bytes=16*1024*1024):
        integer(workers, 'workers', 1, 32)
        integer(max_inflight, 'max_inflight', 1, 128)
        integer(max_inflight_bytes, 'max_inflight_bytes', 1, 64*1024*1024)
        self.fd = fd
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.limit, self.byte_limit = max_inflight, max_inflight_bytes
        self.lock = threading.Lock()
        self.pending, self.pending_bytes, self.peak, self.peak_bytes = 0, 0, 0, 0
        self.cancelled = threading.Event()
        self.closed = False

    def submit(self, offset, length):
        offset, length = ranges_validate([[offset, length]])[0]
        with self.lock:
            if self.closed or self.cancelled.is_set(): raise CancelledError()
            if self.pending >= self.limit or self.pending_bytes + length > self.byte_limit:
                raise BlockingIOError('inflight count or byte limit reached')
            self.pending += 1
            self.pending_bytes += length
            self.peak, self.peak_bytes = max(self.peak,self.pending), max(self.peak_bytes,self.pending_bytes)
        def read():
            if self.cancelled.is_set(): raise CancelledError()
            data = os.pread(self.fd, length, offset)
            if len(data) != length: raise EOFError('short positional read')
            if self.cancelled.is_set(): raise CancelledError()
            return data
        try:
            future = self.pool.submit(read)
        except BaseException:
            with self.lock:
                self.pending -= 1; self.pending_bytes -= length
            raise
        def done(_):
            with self.lock:
                self.pending -= 1; self.pending_bytes -= length
        future.add_done_callback(done)
        return future

    def cancel(self): self.cancelled.set()

    def close(self):
        with self.lock: self.closed = True
        self.pool.shutdown(wait=True, cancel_futures=True)


def fixture_read(inputs):
    text = inputs['data']
    if not isinstance(text, str) or len(text.encode('utf-8')) > 1024*1024:
        raise ValueError('data must be UTF-8 text of at most 1 MiB')
    ranges = ranges_validate(inputs['ranges'])
    if sum(n for _, n in ranges) > 4*1024*1024: raise ValueError('result byte bound exceeded')
    payload = text.encode('utf-8')
    if any(o+n > len(payload) for o,n in ranges): raise ValueError('range beyond fixture')
    merged = coalesce(ranges, inputs.get('max_gap', 0))
    blocks = []
    with tempfile.TemporaryFile() as stream:
        stream.write(payload); stream.flush()
        reader = BoundedPread(stream.fileno(), workers=2, max_inflight=2, max_inflight_bytes=16*1024*1024)
        try:
            for i in range(0,len(merged),2):
                batch = merged[i:i+2]
                futures = [reader.submit(o,n) for o,n in batch]
                blocks.extend((o,f.result()) for (o,n),f in zip(batch,futures))
        finally: reader.close()
    output = []
    for offset,length in ranges:
        output.append(next(data[offset-start:offset-start+length].hex() for start,data in blocks if start<=offset and offset+length<=start+len(data)))
    return dict(scope='real CPU positional reads of owned temporary fixture; no SSD benchmark',
                hex_data=output, coalesced_ranges=merged, peak_inflight=reader.peak, peak_inflight_bytes=reader.peak_bytes)


def evaluate(inputs):
    ranges = ranges_validate(inputs['ranges'])
    merged = coalesce(ranges, inputs.get('max_gap', 0))
    bandwidth = inputs.get('bytes_per_second', 1_000_000_000)
    latency = inputs.get('read_latency_seconds', 0.0001)
    for value in (bandwidth,latency):
        if type(value) not in (int,float) or not math.isfinite(value): raise ValueError('finite numeric costs required')
    if bandwidth<=0 or latency<0: raise ValueError('invalid cost model')
    count = integer(inputs.get('max_inflight', 2), 'max_inflight', 1, 128)
    lanes = [0.0]*count
    for offset,length in merged:
        lane = min(range(count),key=lambda i:lanes[i])
        lanes[lane] += latency + length / bandwidth
    return dict(scope='replay cost model; independent-lane bandwidth assumption; no measured performance',
                reads=len(merged), requested_bytes=sum(n for _,n in ranges), read_bytes=sum(n for _,n in merged),
                modeled_seconds=max(lanes), coalesced_ranges=merged)


def dispatch(capability, inputs):
    if capability == 'plan': return dict(coalesced_ranges=coalesce(inputs['ranges'],inputs.get('max_gap',0)))
    if capability == 'evaluate': return evaluate(inputs)
    if capability == 'read_fixture': return fixture_read(inputs)
    raise ValueError('unknown capability')
