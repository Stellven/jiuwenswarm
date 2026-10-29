"""Private container helper; only sanitized account state leaves this process."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ACCOUNT_ROOT = Path('/var/lib/ai4r-rsi/controller/accounts')
SCHEMA = 'ai4r-rsi-model-status:1'
STATES = {'ready', 'signed_out', 'subscription_required', 'unavailable'}
PLANS = {'free', 'plus', 'pro', 'team', 'business', 'enterprise', 'edu', 'go'}
MODEL_ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,127}\Z')
FINGERPRINT = re.compile(r'[a-f0-9]{64}\Z')


def sanitized(status, fingerprint, models):
    state = status.get('state')
    state = state if state in STATES else 'unavailable'
    plan = status.get('plan')
    ids = sorted({row['id'] for row in models.get('models', [])[:100]
                  if isinstance(row, dict) and isinstance(row.get('id'), str) and MODEL_ID.fullmatch(row['id'])})
    return {'schema': SCHEMA, 'state': state, 'plan': plan if isinstance(plan, str) and plan in PLANS else None,
            'account_fingerprint': fingerprint if isinstance(fingerprint, str) and FINGERPRINT.fullmatch(fingerprint) else None,
            'models': ids if state == 'ready' else []}


def valid_summary(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'state', 'plan', 'account_fingerprint', 'models'}:
        return False
    if (value['schema'] != SCHEMA or not isinstance(value['state'], str) or value['state'] not in STATES
            or not isinstance(value['models'], list) or len(value['models']) > 100):
        return False
    try:
        return value == sanitized(value, value['account_fingerprint'], {'models': [{'id': v} for v in value['models']]})
    except (TypeError, ValueError):
        return False


def validate_profile():
    if sys.platform != 'linux' or os.geteuid() != 12001 or os.getegid() != 12001:
        raise ValueError('Private helper requires the fixed Linux account')
    if any(path.is_symlink() for path in (ACCOUNT_ROOT, *ACCOUNT_ROOT.parents)):
        raise ValueError('Profile links are forbidden')
    meta = ACCOUNT_ROOT.lstat()
    if not stat.S_ISDIR(meta.st_mode) or (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) != (12001, 12001, 0o700):
        raise ValueError('Private account custody differs')


def persist_summary(value):
    if not valid_summary(value):
        raise ValueError('Invalid sanitized result')
    path = ACCOUNT_ROOT / 'setup-status.json'
    # O_NOFOLLOW + same-directory atomic replacement prevents following a
    # profile-owned link into any other mounted file.
    tmp = ACCOUNT_ROOT / 'setup-status.new'
    descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


async def existing_status():
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    service = SubscriptionService(ACCOUNT_ROOT)
    try:
        async with asyncio.timeout(90):
            status = await service.status()
            fingerprint = service.account_fingerprint
            models = await service.models() if status.get('state') == 'ready' else {'models': []}
            if service.account_fingerprint != fingerprint:
                raise ValueError('Account changed during discovery')
            return sanitized(status, service.account_fingerprint, models)
    finally:
        await service.transport.close()


async def initialize_owned_config():
    from jiuwenswarm.server.runtime.codex_subscription.transport import AppServerTransport
    transport = AppServerTransport(ACCOUNT_ROOT)
    try:
        async with asyncio.timeout(60):
            await transport.start()
    finally:
        await transport.close()


@contextmanager
def login_profile_lock():
    """Respect the packaged transport's existing single-owner profile lock."""
    import fcntl
    descriptor = os.open(ACCOUNT_ROOT / 'app-server.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a+b') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def login():
    if os.environ.get('JIUWENSWARM_M1_PROFILE') != '1' or not all(s.isatty() for s in (sys.stdin, sys.stdout, sys.stderr)):
        raise ValueError('Device login requires the explicit isolated profile and human terminal')
    # Obtain the exact current owned configuration from the packaged transport;
    # do not duplicate or relax its strict tool/provider policy.
    asyncio.run(initialize_owned_config())
    from codex_cli_bin import bundled_codex_path
    from jiuwenswarm.server.runtime.codex_subscription.transport import child_environment
    with login_profile_lock():
        result = subprocess.run([str(bundled_codex_path()), 'login', '--device-auth'],
                                cwd=ACCOUNT_ROOT / 'chat-workspace',
                                env=child_environment(ACCOUNT_ROOT / 'codex-home'), timeout=840)
    if result.returncode:
        raise ValueError('Private device login did not complete')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('login', 'status'))
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        validate_profile()
        if args.operation == 'login':
            login()
        value = asyncio.run(existing_status())
        persist_summary(value)
    except Exception:
        # Never stringify exceptions from the private protocol or auth client.
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
