"""Client contract for a separately installed human operator authority.

No server, root escalation, token minting or Library implementation lives in
the web process. Installation must supply a trusted gateway proof resolver;
neither a browser actor string nor AgentRequest.user_id is an OS operator.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import socket
import stat
import struct

from .cc_rsi_projection import ProjectionError, _fields, _hash, _ref, _text

SOCKET = '/run/ai4r-rsi-ui/operator.sock'
PROTOCOL = 'ai4r-cc-rsi-human-operator:1'
MAX_FRAME = 16384


@dataclass(frozen=True)
class HumanActionAuthorization:
    """Resolved server-side by an installed trusted authentication adapter.

    The Root broker must verify this exact action's short-lived, single-use
    signed proof independently. A caller-provided actor is never sufficient.
    """
    actor: str
    action_id: str
    proof: str


class InstalledHumanOperatorClient:
    """Fixed finite socket, Root peer check, no paths/commands from browser."""
    def execute(self, action, node_id, candidate_hash, authorization):
        if action not in ('admit', 'activate') or not isinstance(authorization, HumanActionAuthorization):
            raise ProjectionError('Authenticated exact human action is required')
        _text(node_id); _hash(candidate_hash)
        for text in (authorization.actor, authorization.action_id, authorization.proof):
            _text(text)
            if not text:
                raise ProjectionError('Human action authorization is unavailable')
        if os.name != 'posix' or not hasattr(socket, 'SO_PEERCRED'):
            raise ProjectionError('Installed Unix human operator broker is unavailable')
        directory = os.lstat(os.path.dirname(SOCKET))
        endpoint = os.lstat(SOCKET)
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0 or directory.st_mode & 0o022
                or not stat.S_ISSOCK(endpoint.st_mode) or endpoint.st_uid != 0 or stat.S_IMODE(endpoint.st_mode) != 0o660):
            raise ProjectionError('Human operator broker custody differs')
        request = {'protocol': PROTOCOL, 'action': action, 'node_id': node_id, 'candidate_hash': candidate_hash,
                   'authorization': {'actor': authorization.actor, 'action_id': authorization.action_id, 'proof': authorization.proof}}
        raw = json.dumps(request, separators=(',', ':'), allow_nan=False).encode('utf8')
        if len(raw) > MAX_FRAME:
            raise ProjectionError('Human operator request exceeds finite bound')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(10)
            client.connect(SOCKET)
            _, peer_uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if peer_uid != 0:
                raise ProjectionError('Human operator peer differs')
            client.sendall(raw + b'\n')
            response = bytearray()
            while not response.endswith(b'\n'):
                part = client.recv(min(4096, MAX_FRAME + 1 - len(response)))
                if not part or len(response) + len(part) > MAX_FRAME:
                    raise ProjectionError('Human operator acknowledgement unavailable; reconcile without replay')
                response.extend(part)
        receipt = json.loads(response)
        _fields(receipt, 'action node_id candidate_hash actor receipt_ref')
        if (receipt['action'] != action or receipt['node_id'] != node_id or receipt['candidate_hash'] != candidate_hash
                or receipt['actor'] != authorization.actor):
            raise ProjectionError('Human operator receipt names another exact action')
        _ref(receipt['receipt_ref'])
        return receipt
