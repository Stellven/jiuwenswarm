"""Lightweight owned child/container lifecycle qualification, run by the host queue."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from .store import Store

IMAGE='sha256:754ba564cad9bfb5b8196c16721f14fb8b0ba201c272d81aef341cde2fd167c3'

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args()
    root=Path(os.environ['FACTORY_HOME'])/'probes'/a.attempt;root.mkdir(parents=True)
    child=None;cid=None;record={};status=0
    def stop(signum, frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,stop)
    try:
        with Store(Path(os.environ['FACTORY_HOME'])) as s:
            attempt=s.read('spark-deepseek-port',a.attempt)
            if attempt['request']['worker_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise ValueError('Worker changed')
        child=subprocess.Popen(['/usr/bin/python3','-c','import time;time.sleep(120)'])
        cid=subprocess.check_output(['docker','run','-d','--network=none','--read-only','--memory=64m','--memory-swap=64m','--cpus=0.25','--pids-limit=32','--label','factory.port.attempt='+a.attempt,'--entrypoint','python3',IMAGE,'-c','import time;time.sleep(120)'],text=True).strip()
        (root/'container.id').write_text(cid)
        (root/'started.json').write_text(json.dumps(dict(child=child.pid,container=cid)))
        time.sleep(120)
    except SystemExit as exc:
        status=exc.code
    finally:
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        if child:
            child.terminate()
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
            record.update(child_pid=child.pid,child_rc=child.returncode,child_reaped=not Path('/proc/'+str(child.pid)).exists())
        if cid:
            info=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
            if info['Config']['Labels'].get('factory.port.attempt')!=a.attempt:raise ValueError('Container ownership mismatch')
            subprocess.run(['docker','rm','-f',cid],check=True,capture_output=True,timeout=10)
            result=subprocess.run(['docker','inspect',cid],capture_output=True,timeout=10)
            record.update(container_id=cid,container_removed=result.returncode!=0)
        record.update(exit_status=status)
        (root/'cleanup.json').write_text(json.dumps(record,indent=2))
    return status

if __name__=='__main__':raise SystemExit(main())
