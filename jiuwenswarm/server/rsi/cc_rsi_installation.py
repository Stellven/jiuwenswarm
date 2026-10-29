"""Explicit Root-sealed native gateway and separate finite broker composition."""
from __future__ import annotations

import base64
import copy
import json
import os
from pathlib import Path
import stat

from .cc_rsi_broker import InstalledHumanOperatorClient
from .cc_rsi_operator import NativeCcOperatorAdapter, validate_operator_policy
from .cc_rsi_projection import CcRsiProjection, ProjectionError, _fields

GATEWAY_CONFIG = Path('/etc/ai4r/cc-rsi-gateway.json')
GATEWAY_KEY = Path('/etc/ai4r/cc-rsi-gateway.key')
PUBLICATION = '/run/ai4r-rsi-ui/publication.json'
COMPLETION = Path('/etc/ai4r/cc-rsi-installation.json')


def protected_bytes(path, *, uid, mode, limit=262144):
    path = Path(path)
    if os.name != 'posix' or not path.is_absolute():
        raise ProjectionError('Installed Linux CC custody required')
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ProjectionError('CC installation ancestry custody differs')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode or info.st_size > limit:
            raise ProjectionError('CC installation file custody differs')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit: raise ProjectionError('CC installation exceeds finite bound')
        return raw
    finally: os.close(descriptor)


class InstalledNativeGateway:
    def __init__(self, authority, signer, client, policy, *, projection=None):
        self.authority = authority
        self.policy = copy.deepcopy(validate_operator_policy(policy))
        if self.policy['origin'] != authority.origin:
            raise ProjectionError('CC gateway differs from native authentication origin')
        self.adapter = NativeCcOperatorAdapter(authority, signer, client, self.policy['operators'],workspace_id=self.policy.get('workspace_id'))
        self.projection = projection or CcRsiProjection(PUBLICATION)

    def snapshot(self, headers, params):
        principal = self.authority.authenticate_ws(headers, 'status')
        view = self.projection.snapshot(params)
        if self.policy.get('workspace_id') not in principal.workspace_ids: return view
        for node in view['nodes']:
            candidate = self.policy['candidates'].get(node['hash'])
            if candidate is None or candidate['node_id'] != node['id']: continue
            for action in ('admit', 'activate'):
                if action in self.policy['operators'].get(principal.account_id, ()) and candidate[action + '_request_ref'] is not None:
                    # This authorizes a manual request. Actual signed package,
                    # current qualification and Library eligibility are checked
                    # independently by Root before any effect or success.
                    node[action] = {'allowed': True, 'blocker': None}
        return view

    async def execute(self, headers, params):
        return await self.adapter.execute(headers, params)


def load_native_gateway(authority):
    if not os.path.lexists(GATEWAY_CONFIG): return None
    config_raw = protected_bytes(GATEWAY_CONFIG, uid=0, mode=0o440)
    value = json.loads(config_raw)
    completed_installation('gateway_config_sha256',config_raw)
    _fields(value, 'schema policy gateway_uid gateway_public_key')
    if value['schema'] != 'ai4r-cc-rsi-native-gateway-installation:1' or type(value['gateway_uid']) is not int or value['gateway_uid'] != 10001 or os.getegid() != 10001 or value['gateway_uid'] != os.geteuid():
        raise ProjectionError('Explicit native gateway installation identity differs')
    validate_operator_policy(value['policy'])
    if value['policy']['schema'] != 'ai4r-cc-rsi-root-operator-policy:2':
        raise ProjectionError('Workspace-bound CC gateway policy required')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from jiuwenswarm.research_rsi.signing import Signer
    secret = protected_bytes(GATEWAY_KEY, uid=value['gateway_uid'], mode=0o400, limit=32)
    if len(secret) != 32: raise ProjectionError('Dedicated CC gateway signing key required')
    signer = Signer(Ed25519PrivateKey.from_private_bytes(secret), value['policy']['gateway_key_id'])
    public = base64.urlsafe_b64encode(signer.public_bytes()).decode().rstrip('=')
    if public != value['gateway_public_key']:
        raise ProjectionError('CC gateway key differs from Root installation pin')
    return InstalledNativeGateway(authority, signer, InstalledHumanOperatorClient(), value['policy'])


def root_engine(installation, key, journal):
    from .cc_rsi_library import ProtectedLibraryComposition
    completed_installation('operator_config_sha256',protected_bytes('/etc/ai4r/cc-rsi-operator.json',uid=0,mode=0o600))
    if any(installation[key] != 10001 for key in ('gateway_uid','socket_gid')):
        raise ProjectionError('Installed native M1 gateway UID and primary socket group required')
    library = installation.get('library')
    _fields(library, 'python python_sha256 bindings_path config_path state_root timeout')
    return ProtectedLibraryComposition(installation['policy'], **library).engine(key, journal)


def completed_installation(field,raw):
    import hashlib
    done=json.loads(protected_bytes(COMPLETION,uid=0,mode=0o440))
    _fields(done,'schema plan_sha256 source_build_id entrypoint_sha256 gateway_config_sha256 operator_config_sha256 app_deployed broker_started admission_performed activation_performed')
    if done['schema']!='ai4r-cc-rsi-installation-complete:1' or done[field]!=hashlib.sha256(raw).hexdigest() or any(done[key] is not False for key in ('app_deployed','broker_started','admission_performed','activation_performed')):
        raise ProjectionError('Exact completed Root CC installation required')
    from jiuwenswarm.research.native_ports import verify_installed_build
    if verify_installed_build()!=done['source_build_id']:
        raise ProjectionError('CC installation differs from the actual installed package build')
    return done
