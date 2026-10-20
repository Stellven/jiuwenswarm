"""Actual app/custodian UID/GID access boundary over a disposable inbox."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def test_app_can_read_public_exact_bytes_but_only_custodian_can_publish():
    assert os.name == 'posix' and os.geteuid() == 0, 'Use the job-owned Linux verification image with scoped UID setup capabilities'
    root = Path(tempfile.mkdtemp(prefix='ai4r-inbox-dac-'))
    try:
        root.chmod(0o755); public = root / 'public'; public.mkdir(mode=0o2750)
        os.chown(public, 12002, 13000); public.chmod(0o2750)
        raw = b'public exact original bytes; no signing key or hidden fixture'
        ref = {'id': 'opaque:public-item', 'sha256': hashlib.sha256(raw).hexdigest()}
        for name, data in [(ref['sha256'] + '.bytes', raw), ('original-byte-index.json', json.dumps(
                {'schema': 'ai4r-original-bytes:1', 'refs': {ref['id']: ref['sha256']}}).encode())]:
            path = public / name; path.write_bytes(data); os.chown(path, 12002, 13000); path.chmod(0o640)
        script = '''import json,sys
from pathlib import Path
from jiuwenswarm.research.contracts.inbox import SignedInboxReader
root=Path(sys.argv[1]); ref=json.loads(sys.argv[2])
assert SignedInboxReader(root).read(ref)==bytes.fromhex(sys.argv[3])
for path in [root/'original-byte-index.json',root/(ref['sha256']+'.bytes'),root/'unauthorized']:
    try: path.open('wb')
    except PermissionError: pass
    else: raise AssertionError('app obtained inbox write authority')
'''
        process = subprocess.run([sys.executable, '-c', script, str(public), json.dumps(ref), raw.hex()],
            user=10001, group=10001, extra_groups=(13000,), capture_output=True, timeout=15)
        assert process.returncode == 0, process.stderr.decode()
        denied = subprocess.run([sys.executable, '-c', script, str(public), json.dumps(ref), raw.hex()],
            user=10001, group=10001, extra_groups=(), capture_output=True, timeout=15)
        assert denied.returncode != 0
        writer = subprocess.run([sys.executable, '-c', 'from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"custodian-only")', str(public/'published')],
            user=12002, group=13000, extra_groups=(), capture_output=True, timeout=15)
        assert writer.returncode == 0, writer.stderr.decode()
        assert (public/'published').read_bytes() == b'custodian-only'
    finally:
        shutil.rmtree(root)
