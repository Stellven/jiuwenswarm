"""Finite side-service launch validation; no caller-selected imports/factories.

The fixed CLI assembles the native integration from captured resource refs.
A private config cannot convert a class/module string into executable authority.
"""
import asyncio
import json
import os
from pathlib import Path
import stat
from .ports import PrivatePort,JobPort
from .runtime import RuntimeJobs
from .records import RecordStore


class RuntimeUnavailable(ValueError):pass


def load_config(path,role):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>4*1024*1024 or os.name!='nt' and (p.stat().st_mode&0o022 or p.stat().st_uid!=0):raise RuntimeUnavailable('Service configuration is not an OS-root protected regular file')
    config=json.loads(p.read_bytes())
    common={'schema','socket_path','allowed_peer_uids','record_root','binding_id','resource_binding_ref'}
    required=common|({'job_root','allowed_job_refs'} if role=='jobs' else {'custody_root','request_root','signing_key_file','signer_key_id','fixture_manifest_ref','authorized_sessions'})
    if not isinstance(config,dict) or set(config)!=required or config['schema']!='ai4r-rsi-'+role+'-service:1' or config['binding_id']!='native-isolated-v1':raise RuntimeUnavailable('Unknown finite service binding or configuration field')
    uid=12001 if role=='jobs' else 12002
    if not hasattr(os,'geteuid') or os.geteuid()!=uid:raise RuntimeUnavailable('Required isolated service UID is absent')
    forbidden={10001,10002,10011,12002,12003} if role=='jobs' else None
    if not config['allowed_peer_uids'] or any(type(v) is not int or v<0 or (v in forbidden if forbidden is not None else v!=12001) for v in config['allowed_peer_uids']):raise RuntimeUnavailable('Client UID is outside the isolated launcher/controller role')
    for name in ('socket_path','record_root',*(['job_root'] if role=='jobs' else ['custody_root','request_root','signing_key_file'])):
        value=config[name]
        if not isinstance(value,str) or not Path(value).is_absolute() or '..' in Path(value).parts:raise RuntimeUnavailable('Protected absolute service paths are required')
    if role=='jobs' and not config['allowed_job_refs']:raise RuntimeUnavailable('Exact launcher job-reference allowlist is absent')
    if role=='custodian' and not config['authorized_sessions']:raise RuntimeUnavailable('Authorized immutable custodian sessions are absent')
    return config


async def serve_jobs(config,*,controller_factory=None,public_reader=None,trace_reader=None):
    # The callable is injected by trusted bootstrap Python, never imported from
    # a config/job path. It must assemble RSI controllers in this side process;
    # the core provider returns only its own runner/registry/bridge/check handles.
    store=RecordStore(config['record_root'])
    resources=None
    if controller_factory is None:
        from .fixed_resources import assemble_jobs
        controller_factory,public_reader,trace_reader,resources=await assemble_jobs(config,store)
    jobs=RuntimeJobs(config['job_root'],controller_factory,record_store=store)
    # Only already-started approved jobs are closed. Recovery never calls the
    # proposer or oracle and never makes an interrupted session replayable.
    for pin in config['allowed_job_refs']:
        if store.job_state(pin)['state']=='outcome_unknown':
            try:store.finish_job(pin,{'state':'terminal','result':await jobs.recover(pin)})
            except (ValueError,KeyError,OSError):
                store.put({'record_kind':'rsi-job-recovery-blocked:1','job_ref':pin,
                    'reason':'Exact interrupted-session bindings/custody unavailable; no replay'})
    port=JobPort(jobs,store,allowed_refs=config['allowed_job_refs'],public_reader=public_reader,trace_reader=trace_reader)
    try:
        trial=getattr(controller_factory,'trial_port',None)
        if trial is None:
            await PrivatePort(port.handlers(),config['allowed_peer_uids']).serve(config['socket_path'])
        else:
            from .text_trial import TRIAL_SOCKET
            async with asyncio.TaskGroup() as group:
                group.create_task(PrivatePort(port.handlers(),config['allowed_peer_uids']).serve(config['socket_path']))
                group.create_task(PrivatePort(trial.handlers(),{12002}).serve(TRIAL_SOCKET))
    finally:
        store.close()
        if resources is not None:
            await resources.bridge.subscription.transport.close()
            resources.store.close()


async def serve_custodian(config,*,custodian_service=None):
    records=None;ledger=None
    if custodian_service is None:
        from .fixed_resources import assemble_custodian
        records=RecordStore(config['record_root'])
        custodian_service,ledger=await assemble_custodian(config,records)
    # Scoring callbacks/key/store are created only by trusted custodian process
    # bootstrap. No app, workbench worker or job selects an oracle implementation.
    try:await PrivatePort(custodian_service.handlers(),config['allowed_peer_uids']).serve(config['socket_path'])
    finally:
        if ledger is not None:ledger.close()
        if records is not None:records.close()


def service_main(operation,path):
    role='jobs' if operation=='serve-jobs' else 'custodian'
    config=load_config(path,role)
    return asyncio.run(serve_jobs(config) if role=='jobs' else serve_custodian(config))
