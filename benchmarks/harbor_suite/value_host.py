"""Private filesystem completion broker for isolated native value workers.

No listening port and no credentials enter the worker container. The host uses
the existing Codex helper, validates its original wire receipt, and charges the
campaign scheduler before dispatch. Only one explicitly reserved arm is served.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from .value_data import write_once
from .value_schedule import Schedule


async def account_pin(binary):
    """Observe existing sign-in identity without inference or retaining email."""
    from jiuwenswarm.research.local_model_codex import arguments, child_environment, native_profile
    kwargs = {'stdin': asyncio.subprocess.PIPE, 'stdout': asyncio.subprocess.PIPE,
              'stderr': asyncio.subprocess.DEVNULL, 'env': child_environment(native_profile())}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    process = await asyncio.create_subprocess_exec(*arguments(binary, 'medium'), **kwargs)
    try:
        async def request(ident, method, params):
            process.stdin.write((json.dumps({'id': ident, 'method': method, 'params': params}) + '\n').encode())
            await process.stdin.drain()
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), 20)
                if not line:
                    raise RuntimeError('account metadata transport closed')
                value = json.loads(line)
                if value.get('id') == ident:
                    if 'error' in value:
                        raise RuntimeError('account metadata request rejected')
                    return value['result']
        await request(1, 'initialize', {'clientInfo': {'name': 'cc_value_metadata', 'version': '1.0'}})
        process.stdin.write(b'{"method":"initialized"}\n')
        await process.stdin.drain()
        account = (await request(2, 'account/read', {'refreshToken': False})).get('account') or {}
        if account.get('type') != 'chatgpt' or not account.get('email'):
            raise RuntimeError('native host is not signed in to a ChatGPT account')
        return hashlib.sha256(account['email'].encode()).hexdigest()
    finally:
        if process.returncode is None:
            process.terminate()
        await asyncio.wait_for(process.wait(), 10)


def validate_request(value, filename):
    fields = {'schema', 'request_id', 'prompt', 'timeout_s', 'model', 'reasoning_effort'}
    if (not isinstance(value, dict) or set(value) != fields
            or value['schema'] != 'native-value-completion-request:1'
            or not isinstance(value['request_id'], str)
            or not re.fullmatch('[a-f0-9]{32}', value['request_id'])
            or filename != value['request_id'] + '.request.json'
            or value['model'] not in {'gpt-6.1-sol', 'gpt-6-luna'} or value['reasoning_effort'] != 'medium'
            or not isinstance(value['prompt'], str) or not value['prompt'].strip()
            or len(value['prompt'].encode()) > 1024 * 1024
            or type(value['timeout_s']) not in (float, int)
            or not 0 < value['timeout_s'] <= 600):
        raise ValueError('invalid frozen completion request')
    return value


async def complete(request, *, binary, working, fingerprint, ledger, pair, arm, private, system=None):
    from jiuwenswarm.research.local_model_codex import execute_async
    from jiuwenswarm.research.local_models import native_codex_response
    ident = request['request_id']
    policy = {'id': 'local-value-codex', 'name': 'Value campaign Codex',
              'model_name': request['model'], 'revision': 'native-app-server-pinned',
              'enabled': True, 'context_window': 262144, 'max_prompt_bytes': 1024 * 1024,
              'timeout_s': 600, 'reasoning_effort': request['reasoning_effort']}
    backend = {'kind': 'host-codex-app-server', 'host_python': '/usr/bin/python3',
               'codex_executable': str(binary), 'working_directory': str(working),
               'codex_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
               'account_fingerprint': fingerprint}
    payload = {'model': policy, 'prompt': request['prompt'], 'timeout_s': request['timeout_s'],
               **{k: backend[k] for k in ('codex_executable', 'working_directory',
                                         'codex_sha256', 'account_fingerprint')}}
    remaining_s = ledger.claim(pair, arm, ident, model=request['model'], effort=request['reasoning_effort'])
    payload['timeout_s'] = min(payload['timeout_s'], remaining_s)
    began = time.monotonic()
    # If the process dies here the dispatched ledger entry remains unresolved.
    # Optional developer message for this call only (the product default says tools are unavailable).
    from jiuwenswarm.research import local_model_codex
    default_system = local_model_codex.SYSTEM
    if system:
        local_model_codex.SYSTEM = system
    try:
        original = await execute_async(payload)
    finally:
        local_model_codex.SYSTEM = default_system
    receipt = private / (ident + '.receipt.json')
    write_once(receipt, original)
    result = {'schema': 'native-value-completion-response:1', 'request_id': ident,
              'status': original['outcome'], 'text': '', 'identity': {'effective': None},
              'usage': {}, 'reasoning_effort': None, 'elapsed_s': time.monotonic() - began}
    try:
        bundle, observation, text = native_codex_response(original['response_text'],
            {'backend': backend, 'model': policy}, prompt=request['prompt'])
        result.update(text=text, identity=observation['identity'], usage=observation['usage'],
                      reasoning_effort=bundle['reasoning_effort'], error=bundle['error_code'])
        state = 'completed' if bundle['outcome'] == 'completed' else (
            'unknown' if bundle['outcome'] == 'outcome_unknown' else 'failed')
    except Exception as exc:
        # Invalid proof cannot establish containment of a submitted request.
        state = 'unknown'
        result.update(status='outcome_unknown', error='receipt_validation_' + type(exc).__name__)
    ledger.finish(ident, state, evidence=str(receipt),
                  effective_model=result['identity'].get('effective'),
                  effective_effort=result['reasoning_effort'])
    return result


async def serve(args):
    root = args.directory.resolve()
    private = args.private.resolve()
    root.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    working = private / 'empty-workspaces'
    working.mkdir(exist_ok=True)
    fingerprint = await account_pin(args.binary.resolve())
    ledger = Schedule(args.ledger)
    until = time.monotonic() + args.seconds
    handled = 0
    try:
        while time.monotonic() < until and not (root / 'STOP').exists():
            for path in sorted(root.glob('*.request.json')):
                response = root / path.name.replace('.request.json', '.response.json')
                if response.exists():
                    continue
                if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError('invalid broker request file')
                request = validate_request(json.loads(path.read_text('utf-8')), path.name)
                result = await complete(request, binary=args.binary.resolve(), working=working,
                    fingerprint=fingerprint, ledger=ledger, pair=args.pair, arm=args.arm, private=private,
                    system=getattr(args, 'system', None))
                # Publish only a complete response file; polling workers never
                # observe a partially written JSON document.
                temporary = root / (request['request_id'] + '.response.pending')
                write_once(temporary, result)
                temporary.rename(response)
                handled += 1
                print(json.dumps({'request_id': request['request_id'], 'status': result['status'],
                                  'calls_consumed': ledger.status()['calls_consumed']}), flush=True)
                if result['status'] == 'outcome_unknown':
                    return 2
            await asyncio.sleep(0.15)
        return 0
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--pair', required=True)
    parser.add_argument('--arm', choices=['native', 'native-skills', 'cc'], required=True)
    parser.add_argument('--seconds', type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 10800:
        parser.error('broker wall budget must be 1..10800 seconds')
    return asyncio.run(serve(args))


if __name__ == '__main__':
    raise SystemExit(main())
