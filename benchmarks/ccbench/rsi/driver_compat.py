"""Derived host-driver adapter: publish shared broker responses group-readable.

The pinned partner driver and protocol remain unchanged. Only the exact shared
response.pending file gains group-read before the original atomic rename.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys


def require(ok, reason):
    if not ok: raise ValueError(reason)


def shared_writer(original, broker):
    broker = Path(broker).absolute()
    require(not any(p.is_symlink() for p in (broker, *broker.parents)), 'LINKED_SHARED_BROKER_DENIED')
    initial = broker.stat()
    require(stat.S_ISDIR(initial.st_mode) and initial.st_gid == 10001, 'SHARED_BROKER_GROUP_REQUIRED')
    identity = (initial.st_dev, initial.st_ino, initial.st_uid, initial.st_gid)
    def write(path, value, *, raw=False):
        path = Path(path).absolute()
        shared = path.parent == broker and re.fullmatch(r'[a-f0-9]{32}\.response\.pending', path.name)
        if not shared:
            return original(path, value, raw=raw)
        current = broker.stat()
        require(not any(p.is_symlink() for p in (broker, *broker.parents))
                and identity == (current.st_dev, current.st_ino, current.st_uid, current.st_gid),
                'SHARED_BROKER_CUSTODY_CHANGED')
        original(path, value, raw=raw)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and info.st_uid == os.geteuid() and info.st_gid == 10001,
                    'SHARED_RESPONSE_CUSTODY_CHANGED')
            os.fchmod(descriptor, 0o640)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return write


def load_driver():
    home = Path(__file__).resolve().parent
    source = home / 'partner-source'
    plan = json.loads((home / 'plan.json').read_bytes())
    inventory_raw = (home / 'artifact-pins.json').read_bytes()
    require(hashlib.sha256(inventory_raw).hexdigest() == plan['artifact_pins_sha256'], 'DRIVER_INVENTORY_CHANGED')
    pins = json.loads(inventory_raw)
    for name in ('driver_compat.py', 'partner-source/benchmarks/ccbench/nativetask/run_native_task.py',
                 'partner-source/benchmarks/harbor_suite/value_host.py',
                 'partner-source/benchmarks/harbor_suite/value_data.py'):
        path = home / name
        require(not any(p.is_symlink() for p in (path, *path.parents))
                and hashlib.sha256(path.read_bytes()).hexdigest() == pins[name], 'DRIVER_SOURCE_CHANGED: ' + name)
    sys.path.insert(0, str(source))
    path = source / 'benchmarks/ccbench/nativetask/run_native_task.py'
    spec = importlib.util.spec_from_file_location('frozen_t1_native_driver', path)
    driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)
    require(driver.REPO.resolve() == source.resolve(), 'FROZEN_DRIVER_SOURCE_ROOT_DIFFERS')
    original_plan, original_broker = driver.command_plan, driver.broker_main
    def command_plan(args, attempt):
        result = original_plan(args, attempt)
        require(Path(result['broker'][2]).resolve() == path.resolve(), 'FROZEN_BROKER_COMMAND_DIFFERS')
        result['broker'][2] = str(home / 'driver_compat.py')
        return result
    def broker_main(args):
        session = driver.bounded(driver.ROOT / 'sessions' / driver.identifier(args.session_id))
        from benchmarks.harbor_suite import value_host
        value_host.write_once = shared_writer(value_host.write_once, session / 'native/broker')
        host_work = plan.get('host_model_work_root')
        if host_work is not None:
            work_root = Path(host_work['path'])
            require(work_root.is_absolute() and not any(p.is_symlink() for p in (work_root, *work_root.parents)),
                    'LINKED_HOST_MODEL_WORK_ROOT_DENIED')
            info = work_root.stat()
            require(stat.S_ISDIR(info.st_mode)
                    and (info.st_dev, info.st_ino, info.st_uid, info.st_gid)
                        == (host_work['device'], host_work['inode'], host_work['uid'], host_work['gid']),
                    'HOST_MODEL_WORK_ROOT_CUSTODY_CHANGED')
            plan_digest = hashlib.sha256((home / 'plan.json').read_bytes()).hexdigest()
            model_work = work_root / ('t1-' + plan_digest + '-' + driver.identifier(args.session_id))
            model_work.mkdir(mode=0o700, exist_ok=False)
            complete_original = value_host.complete
            async def complete(request, **kwargs):
                kwargs['working'] = model_work
                return await complete_original(request, **kwargs)
            value_host.complete = complete
        return original_broker(args)
    driver.command_plan, driver.broker_main = command_plan, broker_main
    return driver


def probe_publication(campaign):
    # Exact frozen helper and the same compatibility function used by _broker.
    load_driver()
    from benchmarks.harbor_suite.value_data import write_once
    campaign = Path(campaign)
    broker = campaign / 'broker'
    broker.mkdir(parents=True)
    publish = shared_writer(write_once, broker)
    pending = broker / '00000000000000000000000000000000.response.pending'
    publish(pending, {'probe': 'shared-response'})
    require(stat.S_IMODE(pending.stat().st_mode) == 0o640, 'PREPUBLICATION_MODE_DIFFERS')
    pending.rename(broker / '00000000000000000000000000000000.response.json')
    private = campaign.parent / 'private-response.json'
    publish(private, {'probe': 'private-receipt'})
    require(stat.S_IMODE(private.stat().st_mode) == 0o600, 'PRIVATE_RECEIPT_MODE_CHANGED')
    (broker / 'host-response').write_text('host')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--probe-publication':
        probe_publication(sys.argv[2])
    else:
        raise SystemExit(load_driver().main())
