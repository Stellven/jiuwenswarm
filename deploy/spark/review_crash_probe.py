"""Small CPU-only process/container crash probes for the existing Spark collector.

No model weights, builds, agent/controller, GPU workload, or unrelated services
are started/stopped. Recovery is a fresh process using a durable scoped intent.
This tests process death, not host reboot or power-loss durability.
"""
import argparse,ctypes,hashlib,json,os,signal,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path('/home/user2/software-factory-spark-20261113')
COLLECTOR=ROOT/'sources/collector'
IMAGE='sha256:1b6c3196f68f1c26d2aa873bf8cd9917362ffe7554fbb7e5aff2eee1f4864bbc'


def atomic(path,value):
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex)
    with temporary.open('x') as stream:
        json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def docker(*args,required=True):
    p=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=15)
    if required and p.returncode:raise RuntimeError(p.stderr[:1000])
    return p


def worker(intent):
    sys.path.insert(0,str(COLLECTOR))
    from spark_comparison import docker_cell as dc
    dc.MEMORY=int(intent['memory_bytes'])
    old=dc.memory_sample
    def sample(*args,**kwargs):
        try:return old(*args,**kwargs)
        except OSError as exc:
            if exc.errno==19:raise FileNotFoundError(str(exc)) from exc
            raise
    dc.memory_sample=sample
    mode=intent['mode']
    code=("import time,sys;print('probe-ready',flush=True);time.sleep(.3);sys.exit(23)" if mode=='engine_exit' else
          "import time;print('probe-ready',flush=True);time.sleep(.3);x=bytearray(256*1024*1024);time.sleep(10)" if mode=='oom' else
          "import time\nfor i in range(600):\n print('probe-tick',i,flush=True)\n time.sleep(.1)\n")
    dc.run_docker(['/usr/bin/python3','-c',code],output=Path(intent['directory'])/'collector',image=IMAGE,gpu=False,
                  timeout_s=30,interval_ms=100,guard_gib=.015625,name=intent['container_name'])


def recover(directory):
    directory=Path(directory);intent=json.loads((directory/'intent.json').read_text())
    assert intent['directory']==str(directory.resolve())
    assert intent['container_name'].startswith('strata-rsi-review-')
    # Exact unique name and pinned image, persisted before create; never a global label reaper.
    p=docker('inspect',intent['container_name'],required=False)
    if p.returncode:
        record=dict(container_missing=True,removed=True)
    else:
        info=json.loads(p.stdout)[0]
        assert info['Name']=='/'+intent['container_name'] and info['Image']==intent['image']
        record=dict(container_id=info['Id'],was_running=info['State']['Running'],exit_code_before_recovery=info['State']['ExitCode'],oom_killed=info['State']['OOMKilled'])
        atomic(directory/'inspect-recovered.json',info)
        docker('rm','-f',info['Id'])
        record['removed']=docker('inspect',info['Id'],required=False).returncode!=0
    record['original_final_report_exists']=(directory/'collector/report.json').exists()
    record['recovery_authority']='Exact durable intent name plus matching immutable image; fresh recovery process.'
    receipt=directory/'recovery.json'
    if receipt.exists():receipt=directory/('recovery-recheck-'+uuid.uuid4().hex+'.json')
    atomic(receipt,record)
    return record


def run(root):
    # Adopt only this proof's orphaned attach client, so it can be reaped after collector SIGKILL.
    assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
    rows=[]
    for mode in ('engine_exit','oom','collector_sigkill','collector_sigkill_lost_inspect'):
        directory=root/mode;directory.mkdir(parents=True,exist_ok=False)
        intent=dict(mode=mode,directory=str(directory.resolve()),container_name='strata-rsi-review-'+uuid.uuid4().hex,
                    image=IMAGE,memory_bytes=64*2**20 if mode=='oom' else 256*2**20)
        atomic(directory/'intent.json',intent)
        process=None;record=dict(mode=mode)
        try:
            with (directory/'worker.stdout').open('w') as out,(directory/'worker.stderr').open('w') as err:
                process=subprocess.Popen([sys.executable,__file__,'--worker',str(directory/'intent.json')],stdout=out,stderr=err,start_new_session=True)
            if mode.startswith('collector_sigkill'):
                deadline=time.monotonic()+15;log=directory/'collector/stdout.log'
                while time.monotonic()<deadline:
                    if log.exists() and log.read_bytes().count(b'probe-tick')>=3:break
                    if process.poll() is not None:raise RuntimeError('Collector exited before kill point')
                    time.sleep(.05)
                else:raise TimeoutError('Probe did not reach kill point')
                os.kill(process.pid,signal.SIGKILL);process.wait(timeout=5)
                info=json.loads(docker('inspect',intent['container_name']).stdout)[0]
                record.update(collector_rc=process.returncode,raw_stdout_survived=log.stat().st_size>0,
                              container_still_running_after_collector_death=info['State']['Running'],
                              final_report_missing_after_collector_death=not (directory/'collector/report.json').exists())
                assert record['collector_rc']==-9 and record['raw_stdout_survived']
                assert record['container_still_running_after_collector_death'] and record['final_report_missing_after_collector_death']
                if mode.endswith('lost_inspect'):
                    (directory/'collector/inspect-created.json').rename(directory/'collector/inspect-created.quarantined.json')
            else:
                process.wait(timeout=40)
                report=json.loads((directory/'collector/report.json').read_text())
                record.update(collector_report_reason=report['reason'],container_exit_code=report.get('container_exit_code'),quiescent=report['quiescent'],oom_killed=report.get('container_oom_killed'))
                assert record['quiescent']
                if mode=='engine_exit':assert record['container_exit_code']==23
                else:assert record['oom_killed'] and record['container_exit_code']==137
            subprocess.run([sys.executable,__file__,'--recover',str(directory)],check=True,capture_output=True,timeout=20)
            record['recovery']=json.loads((directory/'recovery.json').read_text());assert record['recovery']['removed']
            record['status']='passed'
        finally:
            if process and process.poll() is None:process.kill();process.wait(timeout=5)
            # Recovery is scoped and idempotent, including failed assertions during the proof.
            recover(directory)
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try:
                    pid,_=os.waitpid(-1,os.WNOHANG)
                    if pid==0:time.sleep(.05)
                except ChildProcessError:break
        rows.append(record)
        atomic(root/'summary.json',dict(scope='CPU-only lifecycle probes, not model performance',host_reboot_power_loss='not_tested',results=rows))
        print(json.dumps(record),flush=True)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',type=Path);p.add_argument('--recover',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.worker:worker(json.loads(a.worker.read_text()))
    elif a.recover:recover(a.recover)
    else:
        root=a.output or ROOT/'results'/('review-crash-'+uuid.uuid4().hex[:10])
        root.mkdir(parents=True,exist_ok=False);run(root);print(str(root))

if __name__=='__main__':main()
