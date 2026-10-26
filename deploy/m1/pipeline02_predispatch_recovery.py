"""Explicit root-only abandonment of one proven unsubmitted native attempt.

This operator action preserves every original result. It only removes the exact
bridge active pointer after independently proving the request was not submitted.
A new attempt must use a distinct identity; this is not workflow recovery.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

_parents = Path(__file__).resolve().parents
REPO = _parents[2] if len(_parents) > 2 else Path.cwd()
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from benchmarks.harbor_pilot.bridge import Config, output_lock, read_json, now
from benchmarks.harbor_suite.contracts import canonical, pin, regular, require
from jiuwenswarm.research_sidecar.client import ResearchClient, ClientError


def worker_processes(uid):
    found = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = next(line for line in (path / 'status').read_text().splitlines() if line.startswith('Uid:'))
        except FileNotFoundError:
            continue  # Process exited during the read; it cannot dispatch now.
        if uid in map(int, fields.split()[1:]):
            found.append(int(path.name))
    return sorted(found)


def append_receipt(folder, stem, value):
    path = folder / (stem + '-' + uuid.uuid4().hex + '.json')
    raw = canonical(value)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(folder, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try: os.fsync(directory)
    finally: os.close(directory)
    return path


async def abandon(suite_path, campaign_id, request_id):
    require(os.name == 'posix' and os.geteuid() == 0, 'root Linux operator required')
    require(campaign_id.startswith('harbor-') and len(campaign_id) == 31
            and all(c in '0123456789abcdef' for c in campaign_id[7:]), 'exact original Harbor campaign required')
    require(request_id.startswith('request-') and len(request_id) == 40
            and all(c in '0123456789abcdef' for c in request_id[8:]), 'exact original request required')
    suite = read_json(regular(suite_path))
    require(suite.get('mode') == 'live' and suite.get('schema') == 'ai4r-harbor-suite-config:1', 'live suite required')
    bridge = Config.load(suite['runner_config'])
    require(str(bridge.output_root) == suite['output_root'], 'operator output root differs')
    controls = read_json(regular(suite['controller_config']))
    require(controls.get('schema') == 'ai4r-native-controller-config:1'
            and controls.get('worker_uid') == 11001, 'original native controller identity required')
    custody = Path(controls['custody_root']) / campaign_id
    require(custody.is_dir() and custody.stat().st_uid == 0 and not custody.stat().st_mode & 0o077
            and not any(p.is_symlink() for p in (custody, *custody.parents)), 'original root-only custody required')
    frozen_path = regular(custody / 'frozen.json')
    with output_lock(bridge.output_root):
        active_path = regular(bridge.output_root / '.harbor-pilot-active.json')
        active_raw = active_path.read_bytes(); active = read_json(active_path)
        require(active.get('campaign_id') == campaign_id, 'another campaign owns the active pointer')
        folder = bridge.output_root / campaign_id
        require(not (folder / 'ledger.sqlite').exists() and not (folder / 'ledger.sqlite').is_symlink()
                and not list(folder.glob('ledger.sqlite-*')), 'any original ledger forbids predispatch abandonment')
        paths = list((folder / 'runs').glob('*/run_record.json'))
        require(len(paths) == 1, 'retain exactly one original queued denominator entry')
        row = read_json(regular(paths[0])); pilot = read_json(regular(folder / 'pilot-receipt.json'))
        require(row.get('campaign_id') == campaign_id and row.get('request_id') == request_id
                and row.get('app_run_id') is None and row.get('execution_state') == 'queued'
                and row.get('collection_state') == 'pending' and row.get('submission') is None,
                'original row is not demonstrably unsubmitted')
        require(pilot.get('campaign_id') == campaign_id and pilot.get('app_run_id') is None
                and pilot.get('error_type') == 'PermissionError' and pilot.get('terminal_confirmed') is False,
                'original controller PermissionError receipt required')
        require(not worker_processes(11001), 'worker process still exists; request delivery remains uncertain')
        client = ResearchClient(bridge.endpoint, bridge.token_file, http_authority=bridge.http_authority)
        captures = []
        async def capture(response):
            raw = await response.aread()
            captures.append({'method': response.request.method, 'path': response.request.url.path,
                             'status_code': response.status_code, 'body_utf8': raw.decode('utf-8'),
                             'sha256': hashlib.sha256(raw).hexdigest()})
        client.http.event_hooks['response'] = [capture]
        try:
            try:
                await client.reconcile(request_id)
            except ClientError as error:
                require(error.status_code == 404 and error.response_record
                        and error.response_record.get('category') == 'not_found',
                        'authenticated original request lookup did not conclusively return not_found')
            else:
                raise ValueError('original app request exists; abandonment is forbidden')
        finally:
            await client.close()
        require(len(captures) == 1 and captures[0]['status_code'] == 404,
                'actual authenticated not_found capture required')
        # Recheck immediately before the only permitted destructive operation.
        require(not worker_processes(11001) and not (folder / 'ledger.sqlite').exists()
                and active_path.read_bytes() == active_raw, 'original containment conditions changed')
        authorization = {'schema': 'ai4r-predispatch-containment:1', 'observed_at': now(),
            'campaign_id': campaign_id, 'request_id': request_id,
            'operation': 'authorize_matching_unsubmitted_pointer_release',
            'original_row': {'path': str(paths[0]), **pin(paths[0])},
            'original_pilot': pin(folder / 'pilot-receipt.json'), 'original_frozen': pin(frozen_path),
            'original_active': {'value': active, 'sha256': hashlib.sha256(active_raw).hexdigest()},
            'api_lookup': captures[0], 'ledger_absent': True, 'worker_processes': [],
            'original_measurement_status': 'unavailable', 'requires_new_distinct_identity': True}
        authorization_path = append_receipt(custody, 'predispatch-authorization', authorization)
        active_path.unlink()
        result = {'schema': 'ai4r-predispatch-containment-result:1', 'observed_at': now(),
                  'campaign_id': campaign_id, 'request_id': request_id,
                  'authorization_receipt': str(authorization_path),
                  'authorization_sha256': pin(authorization_path)['sha256'],
                  'operation': 'matching_active_pointer_removed',
                  'original_files_preserved': True, 'original_measurement_status': 'unavailable',
                  'requires_new_distinct_identity': True}
        receipt_path = append_receipt(custody, 'predispatch-result', result)
        return {**result, 'containment_receipt': str(receipt_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-config', required=True)
    parser.add_argument('--campaign-id', required=True)
    parser.add_argument('--request-id', required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(abandon(args.suite_config, args.campaign_id, args.request_id))))


if __name__ == '__main__':
    main()
