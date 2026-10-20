"""Root-only fixed helper ports, with separate visible and custody authorities."""
import asyncio
import json
import os
from pathlib import Path
import stat
from .worker import WorkerBroker,PublicBytes,PROTOCOL
from .records import RecordStore
from .fixed_resources import closed


async def serve(path):
    from jiuwenswarm.research.private_rpc import PrivateRPCServer
    if not hasattr(os,'geteuid') or os.geteuid()!=0:raise ValueError('A separately owned root worker broker is required')
    p=Path(path);meta=p.lstat()
    if p.is_symlink() or not stat.S_ISREG(meta.st_mode) or meta.st_uid!=0 or meta.st_mode&0o077 or meta.st_size>65536:raise ValueError('Unsafe worker broker configuration')
    config=closed(json.loads(p.read_bytes()),{'root','cgroup_root','public_roots','profile_refs','visible_port','hidden_port'},'ai4r-rsi-worker-service:1')
    # A broker receives only public bodies/profiles and caller-role input
    # stores. It must not receive either oracle contents or an account/key root.
    for forbidden in ('/hidden-fixtures','/var/lib/ai4r-rsi/custodian','/var/lib/ai4r-rsi/accounts','/var/lib/ai4r','/var/lib/ai4r-accounts','/var/run/docker.sock'):
        if os.path.lexists(forbidden):raise ValueError('Forbidden private mount is present in the broker')
    root=Path(config['root'])
    if not root.is_absolute() or any(v.is_symlink() for v in (root,*root.parents)):raise ValueError('Unsafe worker root')
    root.mkdir(mode=0o711,parents=True,exist_ok=True)
    if root.stat().st_uid!=0 or stat.S_IMODE(root.stat().st_mode)!=0o711:raise ValueError('Worker root custody differs')
    public=PublicBytes(config['public_roots']);servers=[];tasks=[];stores=[]
    try:
        for hidden,name,uid in ((False,'visible_port',12001),(True,'hidden_port',12002)):
            value=closed(config[name],{'socket_path','session_id','capability','input_roots'},'ai4r-rsi-worker-port:1')
            capture=RecordStore(root/(name+'-captures'));stores.append(capture)
            broker=WorkerBroker(root=root/name,cgroup_root=config['cgroup_root'],profiles=config['profile_refs'],public_reader=public,
                input_reader=PublicBytes(value['input_roots']),capture_store=capture,hidden=hidden)
            failures=broker.executor.prerequisites()
            if failures:raise ValueError('Worker confinement prerequisites unavailable')
            async def prerequisites(payload,current=broker):
                if payload:raise ValueError('Worker prerequisite payload must be empty')
                return {'ready':not current.executor.prerequisites(),'limitations':current.executor.prerequisites(),'worker_uid':12003,'profile_refs':config['profile_refs']}
            async def timing_batch(payload,current=broker):return await current.run(payload,timing=True)
            server=PrivateRPCServer(value['socket_path'],protocol=PROTOCOL,session_id=value['session_id'],capability=value['capability'],
                handlers={'run_helper':broker.run,'run_timing_batch':timing_batch,'prerequisites':prerequisites,'cancel_session':broker.cancel},allowed_uids={uid},socket_mode=0o660,directory_mode=0o710,group_id=uid)
            await server.start();servers.append(server)
        await asyncio.Event().wait()
    finally:
        for server in servers:await server.close()
        for store in stores:store.close()


def main(path):return asyncio.run(serve(path))
