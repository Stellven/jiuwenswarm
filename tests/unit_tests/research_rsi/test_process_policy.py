"""Actual Linux filter mechanics only, not a complete IF015 campaign."""
import errno
import json
import os
import subprocess
import sys
import tempfile

import pytest

from jiuwenswarm.research_rsi.process_policy import POLICY,program_prefix,security_program
from jiuwenswarm.research_rsi.worker import WORKER_PROGRAM,worker_program,timing_program,validate_profile


def test_process_policy_changes_only_explicit_current_programs():
    assert worker_program()==WORKER_PROGRAM
    assert worker_program(process_policy=POLICY)==program_prefix()+WORKER_PROGRAM
    assert timing_program(3,process_policy=POLICY)==program_prefix()+timing_program(3)
    with pytest.raises(ValueError):worker_program(process_policy='caller_program')


def test_profile3_requires_exact_installed_policy_and_preserves_old_profiles():
    pin={'id':'unit','sha256':'a'*64}
    old=dict(schema='ai4r-rsi-worker-profile:1',target_kind='ranking-v1',session_ref=pin,target_ref=pin,parent_ref=pin,
        contract_ref=pin,environment_ref=pin,hardware_ref=pin,memory_mb=64,pids_max=16,timeout_s=1)
    assert validate_profile(old)==old
    current=dict(old,schema='ai4r-rsi-worker-profile:3',process_policy=POLICY)
    assert validate_profile(current)==current
    with pytest.raises(ValueError):validate_profile(dict(current,process_policy=None))
    with pytest.raises(ValueError):validate_profile(dict(old,process_policy=POLICY))


def test_real_linux_single_process_filter_denies_fork_exec_and_socket():
    if sys.platform!='linux':return
    def identity():
        if os.geteuid()==0:os.setgroups([]);os.setgid(12003);os.setuid(12003)
    assert os.geteuid() in (0,12003),'Linux test requires its disposable worker identity'
    body=b'''import errno,json,os,socket,subprocess,sys
results={}
try:
    pid=os.fork()
except OSError as error:results['fork_errno']=error.errno
else:
    if pid==0:os._exit(0)
    os.waitpid(pid,0);results['fork_errno']=0
try:subprocess.run([sys.executable,'-c','pass'],check=True)
except OSError as error:results['exec_errno']=error.errno
else:results['exec_errno']=0
try:
    connection=socket.socket();connection.close()
except OSError as error:results['socket_errno']=error.errno
else:results['socket_errno']=0
results['ordinary_result']=sum([1,2,3])
print(json.dumps(results))
'''
    command=[sys.executable,'-I','-c',security_program(body).decode()]
    result=subprocess.run(command,capture_output=True,text=True,timeout=10,preexec_fn=identity)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==dict(fork_errno=errno.EPERM,exec_errno=errno.EPERM,socket_errno=errno.EPERM,ordinary_result=6)


def test_real_linux_filter_denies_all_credential_mutations_even_same_id():
    if sys.platform!='linux':return
    def identity():
        if os.geteuid()==0:os.setgroups([]);os.setgid(12003);os.setuid(12003)
    assert os.geteuid() in (0,12003),'Linux test requires its disposable worker identity'
    # Same-ID setters normally succeed even without capabilities. Establish
    # that baseline in this disposable child before installing the real filter.
    baseline='''import os,json
os.setuid(12003);os.setgid(12003)
os.setreuid(12003,12003);os.setregid(12003,12003)
os.setresuid(12003,12003,12003);os.setresgid(12003,12003,12003)
def identity_snapshot():
 status=dict(line.split(':',1) for line in open('/proc/self/status') if ':' in line)
 return {'uid':list(os.getresuid()),'gid':list(os.getresgid()),'groups':os.getgroups(),
         'proc_uid':status['Uid'].split(),'proc_gid':status['Gid'].split()}
before=identity_snapshot()
'''
    body='''import ctypes,errno
libc=ctypes.CDLL(None,use_errno=True);libc.syscall.restype=ctypes.c_long
seccomp=ctypes.CDLL('libseccomp.so.2');seccomp.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]
seccomp.seccomp_syscall_resolve_name.restype=ctypes.c_int
names=('setuid','setgid','setreuid','setregid','setresuid','setresgid','setfsuid','setfsgid','setgroups')
results={}
for name in names+tuple(name+'32' for name in names):
 number=seccomp.seccomp_syscall_resolve_name(name.encode())
 if number<0:continue
 base=name.removesuffix('32')
 for target in (12003,0,4294967294):
  value=ctypes.c_ulong(target)
  if base in ('setreuid','setregid'):args=(value,value)
  elif base in ('setresuid','setresgid'):args=(value,value,value)
  elif base=='setgroups':
   groups=(ctypes.c_uint32*1)(target);args=(ctypes.c_ulong(1),groups)
  else:args=(value,)
  ctypes.set_errno(0);result=libc.syscall(ctypes.c_long(number),*args)
  results[name+':'+str(target)]=[result,ctypes.get_errno()]
class Header(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
class Data(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
header=Header(0x20080522,0);data=(Data*2)()
ctypes.set_errno(0)
result=libc.syscall(ctypes.c_long(seccomp.seccomp_syscall_resolve_name(b'capset')),ctypes.byref(header),data)
results['capset']=[result,ctypes.get_errno()]
print(json.dumps({'results':results,'before':before,'after':identity_snapshot(),
 'ordinary_result':sum([1,2,3]),'ordinary_file':open(os.environ['POLICY_UNIT_FILE']).read()}))
'''
    with tempfile.TemporaryDirectory(prefix='ai4r-policy-unit-') as directory:
        os.chmod(directory,0o755)
        path=os.path.join(directory,'public-unit.txt')
        with open(path,'w') as stream:stream.write('ordinary public unit input')
        os.chmod(path,0o444)
        result=subprocess.run([sys.executable,'-I','-c',baseline+program_prefix().decode()+body],
            capture_output=True,text=True,timeout=10,preexec_fn=identity,env={**os.environ,'POLICY_UNIT_FILE':path})
    assert result.returncode==0,result.stderr
    captured=json.loads(result.stdout)
    assert captured['before']==captured['after']
    assert captured['before']['uid']==captured['before']['gid']==[12003]*3
    assert captured['before']['proc_uid']==captured['before']['proc_gid']==['12003']*4
    assert captured['ordinary_result']==6 and captured['ordinary_file']=='ordinary public unit input'
    assert all(value==[-1,errno.EPERM] for value in captured['results'].values())
    assert all(name+':12003' in captured['results'] for name in ('setuid','setgid','setreuid','setregid','setresuid','setresgid','setfsuid','setfsgid','setgroups'))


@pytest.mark.parametrize('fault',[None,'required-uid','required-gid','supported-variant-rule','canonical-rule'])
def test_resolved_credential_rules_fail_closed_without_submitting_native_absent_variants(monkeypatch,fault):
    if sys.platform!='linux':return
    import ctypes
    from jiuwenswarm.research_rsi.process_policy import install_process_policy
    class Function:
        def __init__(self,callback):self.callback=callback
        def __call__(self,*args):return self.callback(*args)
    numbers={};submitted=[];released=[]
    def resolve(raw):
        name=raw.decode()
        if name=='setuid' and fault=='required-uid':return -10052
        if name=='setgid' and fault=='required-gid':return -1
        if name.endswith('32') and name!='setgid32':return -10000
        numbers.setdefault(name,len(numbers)+1);return numbers[name]
    def add(context,action,number,count):
        name=next(name for name,value in numbers.items() if value==number)
        submitted.append(name)
        assert action==0x00050000|errno.EPERM and count==0
        return -1 if (name=='setgid32' and fault=='supported-variant-rule') or (name=='setresuid' and fault=='canonical-rule') else 0
    library=type('Library',(),{})()
    library.seccomp_init=Function(lambda action:1)
    library.seccomp_syscall_resolve_name=Function(resolve)
    library.seccomp_rule_add=Function(add)
    library.seccomp_load=Function(lambda context:0)
    library.seccomp_release=Function(lambda context:released.append(context))
    libc=type('Libc',(),{})();libc.prctl=Function(lambda option,*args:1 if option==39 else 0)
    monkeypatch.setattr(ctypes,'CDLL',lambda name,**kwargs:libc if name is None else library)
    monkeypatch.setattr(os,'getuid',lambda:12003);monkeypatch.setattr(os,'getgid',lambda:12003);monkeypatch.setattr(os,'getgroups',lambda:[])
    if fault:
        with pytest.raises(RuntimeError):install_process_policy()
    else:
        install_process_policy()
        assert 'setgid32' in submitted and 'setuid32' not in submitted
        assert set(('setuid','setgid','setreuid','setregid','setresuid','setresgid','setfsuid','setfsgid','setgroups','capset'))<=set(submitted)
    assert released==[1]
