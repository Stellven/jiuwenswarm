"""Operator-pinned, key-free local inference services; no user-supplied URLs."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import stat
from time import monotonic
from urllib.parse import urlsplit

from .contracts import ResearchError

LOCAL_PRESETS = tuple(json.loads((Path(__file__).parents[1] /
    'research_contracts/model-presets/local-catalog.json').read_text(encoding='utf-8')))
_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    '127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
    '100.64.0.0/10', '::1/128', 'fd7a:115c:a1e0::/48'))


def local_endpoint_url(value):
    """Plain HTTP is restricted to explicitly pinned local/tailnet services."""
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        return False
    if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path.rstrip('/') != '/v1'):
        return False
    try:
        if port is not None and not 1 <= port <= 65535:
            return False
        address = ipaddress.ip_address(url.hostname)
        return any(address in network for network in _NETWORKS)
    except ValueError:
        return (url.hostname in {'localhost', 'host.docker.internal',
            'ai4r-model-e4b', 'ai4r-model-qwen', 'ai4r-model-bolt', 'ai4r-model-lightning', 'ai4r-model-gptoss', 'ai4r-model-gptoss20'}
            or url.hostname.endswith('.ts.net'))


class LocalModelRegistry:
    def __init__(self, path=None, *, probe=None):
        self.path = Path(path or os.environ.get('JIUWENSWARM_M1_LOCAL_MODELS', '/etc/ai4r/local-models.json'))
        self.probe = probe or self._probe
        self._cached = None

    def configuration(self):
        if not self.path.is_absolute():
            raise ResearchError('invalid_request', 'Local model configuration must use an absolute operator path')
        if not self.path.exists():
            return None, []
        if any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise ResearchError('invalid_request', 'Local model configuration custody is invalid')
        descriptor = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            metadata = os.fstat(descriptor)
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > 65536
                    or os.name == 'posix' and (metadata.st_uid not in {0, os.geteuid()} or metadata.st_mode & 0o022)):
                raise ResearchError('invalid_request', 'Local model configuration custody is invalid')
            with os.fdopen(descriptor, 'r', encoding='utf-8', closefd=False) as stream:
                value = json.load(stream)
        finally:
            os.close(descriptor)
        if (not isinstance(value, dict) or set(value) != {'schema', 'models'}
                or value['schema'] != 'ai4r-local-model-endpoints:1' or not isinstance(value['models'], list)
                or len(value['models']) > len(LOCAL_PRESETS)):
            raise ResearchError('invalid_request', 'Invalid local model configuration')
        ids = set()
        for entry in value['models']:
            if (not isinstance(entry, dict) or set(entry) != {'id', 'base_url', 'served_model', 'context_tokens', 'output_tokens', 'enabled'}
                    or entry['id'] not in {p['id'] for p in LOCAL_PRESETS} or entry['id'] in ids
                    or not local_endpoint_url(entry['base_url'])
                    or not isinstance(entry['served_model'], str) or not 0 < len(entry['served_model']) <= 256
                    or type(entry['enabled']) is not bool
                    or type(entry['context_tokens']) is not int or not 4096 <= entry['context_tokens'] <= 262144
                    or type(entry['output_tokens']) is not int or not 256 <= entry['output_tokens'] < entry['context_tokens']):
                raise ResearchError('invalid_request', 'Invalid local model endpoint')
            ids.add(entry['id'])
        raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        return hashlib.sha256(raw).hexdigest(), value['models']

    async def _probe(self, entry):
        import httpx
        async with httpx.AsyncClient(timeout=2, trust_env=False, follow_redirects=False) as client:
            response = await client.get(entry['base_url'].rstrip('/') + '/models')
            response.raise_for_status()
            if len(response.content) > 1024 * 1024:
                return False
            rows = response.json().get('data')
            return isinstance(rows, list) and sum(isinstance(row, dict) and row.get('id') == entry['served_model'] for row in rows) == 1

    async def inspect(self):
        revision, entries = self.configuration()
        if self._cached and self._cached[0] == revision and monotonic() - self._cached[1] < 5:
            return self._cached[2]
        by_id = {entry['id']: entry for entry in entries}

        async def inspect_one(preset):
            entry = by_id.get(preset['id'])
            ready = False
            reason = 'not_configured' if entry is None else 'disabled' if not entry['enabled'] else 'service_unavailable'
            if entry is not None and entry['enabled']:
                try:
                    async with asyncio.timeout(3):
                        ready = await self.probe(entry) is True
                    reason = 'ready' if ready else 'model_not_served'
                except Exception:
                    pass
            return {**preset, 'ready': ready, 'reason': reason,
                'entry': entry, 'configuration_revision': revision}
        rows = await asyncio.gather(*(inspect_one(preset) for preset in LOCAL_PRESETS))
        self._cached = revision, monotonic(), rows
        return rows

    def preflight(self, candidate):
        revision, entries = self.configuration()
        entry = next((row for row in entries if row['id'] == candidate['preset_id']), None)
        if (revision != candidate['configuration_revision'] or entry is None or not entry['enabled']
                or entry['base_url'] != candidate['base_url'] or entry['served_model'] != candidate['model_id']):
            raise ResearchError('auth_failed', 'Frozen local model endpoint is no longer authorized')
        # The native Jiuwen adapter uses auth_mode='none' for these services.
        return ''
