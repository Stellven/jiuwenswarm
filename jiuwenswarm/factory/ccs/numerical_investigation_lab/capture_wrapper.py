"""Explicit native recorder entry: drain existing dump hook through FIFO into RAM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import threading
from capture_adapter import MARKER, MAX_BYTES, witness


class FifoCapture:
    """Nonblocking reader starts before fopen; retain bounded bytes, drain overflow.

    Empty reads before a writer opens are expected. Once the child has exited,
    drain all buffered bytes and stop on empty/EAGAIN, including a never-opened
    FIFO. The engine's lifetime remains bounded by its existing recorder.
    """
    def __init__(self, path, limit):
        self.path=Path(path)
        self.limit=limit
        self.raw=bytearray()
        self.actual_bytes=0
        self.digest=hashlib.sha256()
        self.done=threading.Event()
        self.error=None
        os.mkfifo(self.path,0o600)
        # Open in the parent before the child so native fopen never lacks a reader.
        self.fd=os.open(self.path,os.O_RDONLY|os.O_NONBLOCK)
        self.thread=threading.Thread(target=self._read,name='native-logit-fifo',daemon=True)
        self.thread.start()

    def _read(self):
        try:
            while True:
                try:
                    chunk=os.read(self.fd,65536)
                except BlockingIOError:
                    chunk=b''
                if chunk:
                    self.actual_bytes+=len(chunk)
                    self.digest.update(chunk)
                    remaining=self.limit-len(self.raw)
                    if remaining>0:
                        self.raw.extend(chunk[:remaining])
                    continue
                if self.done.is_set():
                    break
                # Avoid spinning on an unopened FIFO or writer HUP; exits promptly.
                self.done.wait(.01)
        except OSError as exc:
            self.error=str(exc)
        finally:
            os.close(self.fd)

    def finish(self):
        self.done.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            raise ValueError('FIFO reader did not stop after engine exit')
        if self.error:
            raise ValueError('FIFO reader failed: '+self.error)


def tmp_free_bytes():
    stat=os.statvfs('/tmp')
    return stat.f_bavail*stat.f_frsize


def tmp_resources():
    status=os.statvfs('/tmp')
    return dict(free_bytes=status.f_bavail*status.f_frsize,total_bytes=status.f_blocks*status.f_frsize)


def failure_witness(capture,vocabulary_size,error,child_returncode,free_before):
    width=vocabulary_size*4
    return dict(format='strata-native-logit-capture-failure/1',error=str(error),
        capture_transport='fifo_ram',vocabulary_size=vocabulary_size,expected_rows=50,
        expected_bytes=50*width,actual_bytes=capture.actual_bytes,
        retained_bytes=len(capture.raw),capture_file_count=1,
        float_alignment_remainder=capture.actual_bytes%4,
        row_alignment_remainder=capture.actual_bytes%width,
        complete_rows=capture.actual_bytes//width,
        raw_sha256=capture.digest.hexdigest(),hashed_bytes=capture.actual_bytes,
        hash_scope='entire_observed_fifo_stream',complete_capture=False,
        child_returncode=child_returncode,tmp_free_bytes_before=free_before,
        tmp_free_bytes_after=tmp_free_bytes(),reader_error=capture.error)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--vocabulary-size',type=int,required=True)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command or not 2<=args.vocabulary_size<=262144:
        parser.error('bounded vocabulary and original engine command required')
    if command.count('--dspark')!=1 or command[command.index('--dspark')+1:command.index('--dspark')+2]!=['none'] or '--serve' not in command or '--parallel' in command:
        parser.error('single-conversation --serve --dspark none required')
    resources_before=tmp_resources()
    free_before=resources_before['free_bytes']
    with tempfile.TemporaryDirectory(prefix='strata-capture-',dir='/tmp') as directory:
        prefix=str(Path(directory)/'logits')
        expected=50*args.vocabulary_size*4
        capture=FifoCapture(prefix+'.1.f32',min(MAX_BYTES,expected)+1)
        env=dict(os.environ,DS4_SERVE_DUMP=prefix)
        child_returncode=None
        try:
            child=subprocess.run(command,env=env,check=False)
            child_returncode=child.returncode
            capture.finish()
            if child_returncode:
                raise ValueError('native engine exited unsuccessfully')
            if len(list(Path(directory).glob('*.f32')))!=1 or not stat.S_ISFIFO(capture.path.stat().st_mode):
                raise ValueError('exactly one original FIFO request dump required')
            if capture.actual_bytes!=expected or len(capture.raw)!=expected:
                raise ValueError('dump truncated, oversized or wrong row count')
            record=witness(capture.raw,args.vocabulary_size)
            print(MARKER+json.dumps(record,sort_keys=True,separators=(',',':')),file=sys.stderr,flush=True)
            resources=dict(transport='fifo',tmp_before=resources_before,tmp_after=tmp_resources(),actual_bytes=capture.actual_bytes,expected_bytes=expected,retained_bytes=len(capture.raw))
            print('STRATA_NUMERICAL_CAPTURE_RESOURCES '+json.dumps(resources,sort_keys=True),file=sys.stderr,flush=True)
        except (OSError,ValueError) as exc:
            capture.done.set()
            capture.thread.join(timeout=2)
            record=failure_witness(capture,args.vocabulary_size,exc,child_returncode,free_before)
            print('STRATA_NUMERICAL_CAPTURE_ERROR '+json.dumps(record,sort_keys=True),file=sys.stderr,flush=True)
            return child_returncode or 1
    return 0


if __name__=='__main__':
    sys.exit(main())
