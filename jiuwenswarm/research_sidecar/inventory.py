"""Fresh host observations; container limits never stand in for physical hardware."""
from datetime import datetime,timezone
import os
import platform
from pathlib import Path
import socket
import uuid
import psutil
import subprocess
import json


def utc():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _commit_snapshot():
    """Windows system commit counters, bytes -> MiB; never process VMS."""
    if platform.system()!='Windows':return None
    program="$ErrorActionPreference='Stop'; Get-CimInstance Win32_PerfRawData_PerfOS_Memory | Select-Object -Property CommitLimit,CommittedBytes | ConvertTo-Json -Compress"
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',program],capture_output=True,text=True,timeout=15,check=False)
        value=json.loads(result.stdout)
        if result.returncode or set(value)!={'CommitLimit','CommittedBytes'} or any(type(v) is not int or v<0 for v in value.values()) or value['CommitLimit']<=0:return None
        return {'commit_limit_mb':value['CommitLimit']//2**20,'commit_used_mb':value['CommittedBytes']//2**20,
            'source':'Win32_PerfRawData_PerfOS_Memory','scope':'Windows system committed virtual memory',
            'raw_unit':'bytes','reported_unit':'MiB','raw':value,'observed_at':utc()}
    except (OSError,ValueError,subprocess.TimeoutExpired):return None


def collect(*,campaign_id,run_id,repeat_index,host_profile,role,budgets,workspace,requirements=None,capture=None):
    if role not in {'orchestration','experiment'}:raise ValueError('invalid host role')
    memory=psutil.virtual_memory();swap=psutil.swap_memory();storage=psutil.disk_usage(str(workspace))
    commit=_commit_snapshot()
    if commit is not None and capture is not None:capture('system-commit',commit)
    unavailable=[{'field':'accelerators','reason':'accelerator detection not qualified on this host'},
        {'field':'execution_peaks','reason':'not yet sampled; append separate immutable peak capture after execution'}]
    if commit is None:unavailable += [{'field':key,'reason':'Qualified system committed-memory counter unavailable on this OS/host'} for key in ('commit_limit_mb','commit_used_mb')]
    reasons=[]
    if Path('/.dockerenv').exists():reasons.append('host inventory must run on the experiment host, outside the sidecar container')
    requirements=requirements or {}
    if memory.available/2**20<requirements.get('min_physical_mb',0):reasons.append('physical memory below required available capacity')
    if requirements.get('min_commit_mb',0)>0:
        if commit is None:reasons.append('required committed-memory dimension unavailable')
        elif commit['commit_limit_mb']-commit['commit_used_mb']<requirements['min_commit_mb']:reasons.append('available system commit below required capacity')
    arch={'amd64':'x86_64','x86_64':'x86_64','arm64':'aarch64','aarch64':'aarch64'}.get(platform.machine().lower(),platform.machine().lower())
    if requirements.get('arch','any') not in {'any',arch}:reasons.append('host architecture mismatch')
    if requirements.get('accelerator')=='required':reasons.append('required accelerator qualification unavailable')
    if host_profile!='other_declared':reasons.append('named hardware profile has not been independently qualified')
    return {'schema':'hardware-inventory:1','inventory_id':'inventory_'+uuid.uuid4().hex,'campaign_id':campaign_id,'run_id':run_id,'repeat_index':repeat_index,
        'collected_at':utc(),'collector_version':'host:2','role':role,'host_id':socket.gethostname(),'host_profile':host_profile,'host_profile_confirmed':not reasons,
        'cpu_model':platform.processor() or platform.machine(),'cpu_arch':arch,'cpu_cores':psutil.cpu_count(logical=False) or 1,'cpu_threads':psutil.cpu_count() or 1,
        'memory_total_mb':int(memory.total/2**20),'memory_available_mb':int(memory.available/2**20),
        'commit_limit_mb':commit['commit_limit_mb'] if commit else None,'commit_used_mb':commit['commit_used_mb'] if commit else None,
        'pagefile_mb':int(swap.total/2**20),'pagefile_used_mb':int(swap.used/2**20),'memory_model':'unknown','accelerators':[],
        'no_accelerator_confirmed':False,'storage_total_mb':int(storage.total/2**20),'storage_free_mb':int(storage.free/2**20),
        'os_name':platform.system(),'os_version':platform.version(),'runtime_versions':{'python':platform.python_version()},
        'container_limits':{'cpu_limit':None,'memory_limit_mb':None,'pids_limit':None},'declared_budgets':budgets,
        'background_workload':{'status':'unknown','items':[]},'power_profile':'unknown','static_ref':None,'unavailable_fields':unavailable,
        'readiness':'blocked' if reasons else 'ready','readiness_reasons':reasons,'execution_peaks':None}


class PeakSampler:
    def __init__(self,pids):self.pids=tuple(pids);self.working=None;self.commit=None
    def sample(self):
        working=0;commit=0;seen=False
        for pid in self.pids:
            try:
                value=psutil.Process(pid).memory_info();working+=value.rss;commit+=value.vms;seen=True
            except (psutil.NoSuchProcess,psutil.AccessDenied):continue
        if seen:self.working=max(self.working or 0,working);self.commit=max(self.commit or 0,commit)
        return {'peak_working_set_mb':self.working/2**20 if self.working is not None else None,
            'peak_commit_mb':None,'paging_events':None,'sampled_at':utc(),
            'unavailable_reasons':['VMS is not committed memory; OS committed-memory/page-event counters unavailable']}
