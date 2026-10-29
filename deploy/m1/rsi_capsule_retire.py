"""Explicit recovery of drained capsule job groups from retained terminal evidence.

Defaults to inspection. --apply never runs jobs, changes limits, removes run
roots, or deletes historical evidence. Unproven jobs remain in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.targets.cgroup_lifecycle import (
    snapshot_group, retire_observed_group,
)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def protected(path, *, directory=False):
    path = Path(path)
    need(path.is_absolute() and path.resolve(strict=True) == path, 'EXACT_RECOVERY_PATH_REQUIRED')
    for parent in (path, *path.parents):
        meta = parent.lstat()
        need(meta.st_uid == 0 and not stat.S_IMODE(meta.st_mode) & 0o022,
             'ROOT_RECOVERY_CUSTODY_REQUIRED')
        need(not stat.S_ISLNK(meta.st_mode), 'RECOVERY_SYMLINK_DENIED')
    meta = path.lstat()
    need(stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1,
         'RECOVERY_PATH_KIND_DIFFERS')
    return path


def read_json(path):
    return json.loads(protected(path).read_bytes())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def references(value):
    if isinstance(value, dict):
        if set(value) == {'id', 'sha256'}:
            yield value
        else:
            for child in value.values():
                yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def captured(root, ref):
    sha = ref['sha256']
    need(isinstance(sha, str) and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha),
         'RECOVERY_CAPTURE_REF_INVALID')
    for folder in ('captures', 'sealed-captures'):
        path = root / folder / (sha + '.json')
        if path.exists():
            raw = protected(path).read_bytes()
            need(digest(raw) == sha, 'RECOVERY_CAPTURE_DIGEST_DIFFERS')
            return raw
    raise ValueError('RECOVERY_CAPTURE_MISSING:' + sha)


def ceased(configuration):
    raw = protected(configuration).read_bytes()
    cfg = json.loads(raw)
    need(cfg.get('schema') == 'ai4r-rsi-capsule-run-configuration:2'
         and cfg['evaluator'].get('dispatcher', 'v18-bwrap') == 'v18-bwrap',
         'PROTECTED_CAPSULE_RECOVERY_REQUIRED')
    run_id = cfg['session']['id']
    root = protected(cfg['evaluator']['root'], directory=True)
    group = protected(cfg['evaluator']['cgroup_root'], directory=True)
    owner = read_json(root / 'owner.json')
    controller = read_json(root / 'controller-owner.json')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    for role, record in (('evaluator', owner), ('controller', controller)):
        need(record.get('schema') == 'ai4r-rsi-capsule-' + role + '-owner:1'
             and record['id'] == run_id and record['configuration_sha256'] == digest(raw)
             and record['boot_id'] == boot, 'RECOVERY_OWNER_CONFIGURATION_OR_BOOT_DIFFERS')
    control = Path(configuration).parent
    exit_record = read_json(control / 'run-exit.json')
    container = read_json(control / 'run-container.json')
    need(exit_record['cid'] == container['cid'] and container['id'] == run_id
         and type(exit_record['exit_code']) is int, 'RECOVERY_KNOWN_TERMINAL_REQUIRED')
    namespaces = {owner['pid_namespace'], controller['pid_namespace']}
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            namespace = os.readlink(process / 'ns/pid')
        except (FileNotFoundError, ProcessLookupError):
            continue
        need(namespace not in namespaces, 'RECOVERY_OWNER_PROCESS_REMAINS')
    need(not (group / 'cgroup.procs').read_text().strip()
         and 'populated 0' in (group / 'cgroup.events').read_text().splitlines(),
         'RECOVERY_RUN_GROUP_BUSY')
    grant = read_json(cfg['evaluator']['grant_path'])
    need(digest(protected(cfg['evaluator']['grant_path']).read_bytes()) == cfg['evaluator']['grant_sha256']
         and grant['run_id'] == run_id and grant == cfg['session']['grant'], 'RECOVERY_GRANT_DIFFERS')
    return cfg, root, group


def plan(configuration):
    cfg, root, group = ceased(configuration)
    rows = {}
    for folder in ('captures', 'sealed-captures'):
        for path in (root / folder).glob('*.json'):
            raw = protected(path).read_bytes()
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(value, dict) or not isinstance(value.get('receipt'), dict):
                continue
            if value.get('schema') not in (
                'ai4r-rsi-whole-capsule-visible-check:1',
                'ai4r-rsi-capsule-benchmark-evidence:1',
            ):
                continue
            need(path.name == digest(raw) + '.json', 'RECOVERY_EVIDENCE_DIGEST_DIFFERS')
            rows.setdefault(value['receipt']['job_id'], []).append((value, raw))
    ready, skipped = [], []
    for leaf in sorted(group.iterdir()):
        if not leaf.is_dir() and not leaf.is_symlink():
            continue
        try:
            observation = snapshot_group(group, leaf.name)
            matches = rows.get(leaf.name, [])
            need(bool(matches), 'RECOVERY_TERMINAL_EVIDENCE_MISSING')
            # Multiple stored views must agree on the receipt and start binding.
            evidence, evidence_raw = matches[0]
            receipt, start_ref = evidence['receipt'], evidence['start_ref']
            need(all(v['receipt'] == receipt and v['start_ref'] == start_ref for v, _ in matches),
                 'RECOVERY_TERMINAL_EVIDENCE_CONFLICT')
            claim_raw = protected(root / 'claims' / (leaf.name + '.json')).read_bytes()
            start_raw = captured(root, start_ref)
            need(claim_raw == start_raw, 'RECOVERY_START_CLAIM_DIFFERS')
            start = json.loads(start_raw)
            need(start['job_id'] == leaf.name == receipt['job_id'] == receipt['invocation_id']
                 and start['grant_sha256'] == cfg['evaluator']['grant_sha256'],
                 'RECOVERY_JOB_OWNERSHIP_DIFFERS')
            need(receipt.get('observed_runtime') is True and receipt.get('ended_at')
                 and isinstance(receipt.get('termination_reason'), str)
                 and type(receipt.get('exit_code')) is int, 'RECOVERY_TERMINAL_RECEIPT_REQUIRED')
            counters = observation['counters']
            need(receipt.get('memory_events') == counters['memory.events']
                 and receipt.get('pids_events') == counters['pids.events']
                 and receipt['observed_limits']['memory_max'] == counters['memory.max'].strip()
                 and receipt['observed_limits']['pids_max'] == counters['pids.max'].strip(),
                 'RECOVERY_RECEIPT_COUNTERS_CHANGED')
            need(start['candidate_ref']['sha256'] == receipt['subject_ref']['sha256'],
                 'RECOVERY_SUBJECT_DIFFERS')
            blobs = [(start_ref, start_raw)]
            for ref in references([start, receipt]):
                blobs.append((ref, captured(root, ref)))
            ready.append(dict(observation=observation, receipt=receipt, start_ref=start_ref,
                              blobs=blobs, evidence_raw=evidence_raw))
        except (ValueError, OSError, KeyError) as error:
            skipped.append({'job_id': leaf.name, 'reason': str(error)})
    return cfg, root, group, ready, skipped


def run(configuration, *, apply=False):
    cfg, root, group, ready, skipped = plan(configuration)
    result = {'schema': 'ai4r-rsi-cgroup-recovery:1', 'run_id': cfg['session']['id'],
              'configuration_sha256': digest(protected(configuration).read_bytes()),
              'cgroup_root': str(group), 'apply': apply, 'eligible': len(ready),
              'skipped': skipped, 'retired': 0, 'model_calls': 0}
    if not apply:
        return result
    # Root-only recovery evidence is separate from the controller's public
    # closure. Held-out output bytes never become public through recovery.
    recovery_root = root / 'cgroup-retirement'
    recovery_root.mkdir(mode=0o700, exist_ok=True)
    protected(recovery_root, directory=True)
    need(stat.S_IMODE(recovery_root.stat().st_mode) == 0o700,
         'PRIVATE_RECOVERY_DIRECTORY_REQUIRED')
    store = RecordStore(recovery_root)
    try:
        for row in ready:
            # Recheck cessation against exactly the configuration/root planned,
            # not merely some new protected configuration at the same path.
            current_cfg, current_root, current_group = ceased(configuration)
            need(current_cfg == cfg and current_root == root and current_group == group
                 and digest(protected(configuration).read_bytes()) == result['configuration_sha256'],
                 'RECOVERY_CONFIGURATION_CHANGED')
            for ref, raw in row['blobs']:
                store.put_ref(ref, raw)
            source_ref = store.put_bytes(row['evidence_raw'])
            store.put({'schema': 'ai4r-rsi-cgroup-recovery-source:1',
                       'configuration_sha256': result['configuration_sha256'],
                       'source_evidence_ref': source_ref, 'start_ref': row['start_ref'],
                       'observation': row['observation']})
            retire_observed_group(group, observation=row['observation'],
                                  receipt=row['receipt'], start_ref=row['start_ref'], store=store)
            result['retired'] += 1
        result['result_ref'] = store.put(result)
        return result
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_RECOVERY_REQUIRED')
    print(json.dumps(run(args.configuration, apply=args.apply), sort_keys=True))


if __name__ == '__main__':
    main()
