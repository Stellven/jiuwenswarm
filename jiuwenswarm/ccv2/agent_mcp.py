"""MCP front door for agents: discover, read, call, start and stop CCs in a folder.

One stdio server per agent session. It wraps one `Host` (so receipts, call keys
and instance records persist in `--store`) and one folder of CC packages
(`--ccs DIR`, each child holding a `cc.yaml`).

Authority comes only from `--grant` flags and `--workspace`; an agent cannot
widen them. Reading a material never grants execution.
"""
from __future__ import annotations

import argparse
import functools
import json
import uuid
from pathlib import Path
from typing import Any

from .ccv2 import CCError, Host, callable_entries, service_entries

MAX_TEXT = 200_000


class Catalog:
    def __init__(self, ccs: Path, store: Path, grants=(), workspace: Path | None = None):
        self.ccs = Path(ccs).resolve()
        resources = {}
        if workspace:
            resources['workspace'] = {'kind': 'workspace', 'path': str(Path(workspace).resolve())}
        self.host = Host(store, resources=resources, session_grants=list(grants))
        self.releases: dict[str, str] = {}
        self.errors: dict[str, dict] = {}

    # -- discovery ---------------------------------------------------------
    def scan(self) -> list[dict]:
        self.releases.clear()
        self.errors.clear()
        entries = []
        for folder in sorted(p for p in self.ccs.iterdir() if (p / 'cc.yaml').is_file()) if self.ccs.is_dir() else []:
            try:
                release = self.host.prepare(folder)
                release = release['release'] if isinstance(release, dict) else release
                declaration = self.host.describe(release)
            except CCError as e:
                self.errors[folder.name] = e.record()
                entries.append({'folder': folder.name, 'usable': False, 'error': e.record()})
                continue
            self.releases[declaration['id']] = release
            entries.append(self.summary(declaration, release, folder.name))
        return entries

    @staticmethod
    def summary(declaration: dict, release: str, folder: str) -> dict:
        callable_ = callable_entries(declaration)
        services = service_entries(declaration)
        caps = {}
        for name, cap in declaration.get('capabilities', {}).items():
            caps[name] = {
                'kind': 'service' if name in services else 'finite',
                'does': cap.get('does'),
                'takes': sorted(cap.get('takes', {})),
                'gives': sorted(cap.get('gives', {})),
                'needs': cap.get('needs', []),
                'effects': cap.get('changes', []),
                'binding': (declaration['bindings'].get(cap.get('using', 'default')) or {}).get('kind'),
            }
        return {
            'cc': declaration['id'], 'version': declaration['version'], 'release': release,
            'folder': folder, 'usable': True, 'capabilities': caps,
            'materials': {k: v.get('description') for k, v in declaration.get('materials', {}).items()},
            'callable': sorted(callable_), 'services': sorted(services),
        }

    def release_for(self, cc: str) -> str:
        if cc not in self.releases:
            self.scan()
        if cc not in self.releases:
            raise CCError('UNKNOWN_CC', f'{cc!r} not found in {self.ccs}; known: {sorted(self.releases)}')
        return self.releases[cc]

    # -- use ---------------------------------------------------------------
    def material(self, cc: str, name: str) -> dict:
        release = self.release_for(cc)
        meta = self.host.material(release, name)
        _, bundle = self.host.release(release)
        path = Path(bundle) / meta['path']
        data = path.read_bytes()
        text = data[:MAX_TEXT].decode('utf-8', errors='replace')
        return {'cc': cc, 'material': name, 'media_type': meta.get('media_type'),
                'description': meta.get('description'), 'truncated': len(data) > MAX_TEXT, 'text': text,
                'authority': 'Reading this grants no execution authority.'}

    def start(self, cc: str, capability: str, inputs: dict | None, key: str | None) -> dict:
        instance = self.host.start(self.release_for(cc), capability, inputs or {}, key=key or str(uuid.uuid4()))
        endpoints = instance.get('endpoints') or {}
        if instance.get('state') == 'running' and endpoints:
            handle = f"env-{instance['id']}"
            self.host.resources[handle] = {'kind': 'environment', 'url': next(iter(endpoints.values())),
                                           'instance': instance['id']}
            instance = dict(instance, handle=handle)
        return instance


def build(catalog: Catalog):
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP('cc-v2')

    def guarded(fn):
        @functools.wraps(fn)  # keeps the real signature so MCP advertises the right arguments
        def run(*a, **k):
            try:
                return fn(*a, **k)
            except CCError as e:
                return {'error': e.record()}
        return run

    @mcp.tool()
    @guarded
    def cc_list() -> Any:
        """List the Capability Capsules available to this session: their capabilities (finite or service), materials, and whether each declaration is usable. Start here."""
        return {'ccs': catalog.scan(), 'folder': str(catalog.ccs)}

    @mcp.tool()
    @guarded
    def cc_describe(cc: str) -> Any:
        """Full normalized declaration of one CC (ports, bindings, effects)."""
        return catalog.host.describe(catalog.release_for(cc))

    @mcp.tool()
    @guarded
    def cc_material(cc: str, material: str) -> Any:
        """Read a passive material (instructions, methodology, reference). Reading it does not authorize running anything."""
        return catalog.material(cc, material)

    @mcp.tool()
    @guarded
    def cc_artifact(path: str) -> Any:
        """Register a local file as an artifact ({uri, sha256}) usable as an artifact input."""
        return catalog.host.put_artifact(Path(path))

    @mcp.tool()
    @guarded
    def cc_call(cc: str, capability: str, inputs: dict | None = None, key: str | None = None) -> Any:
        """Run a finite capability and return its receipt. Reuse the same `key` to retry without running twice; omit it for a fresh call. A receipt state of failed/blocked/unknown is not a success."""
        return catalog.host.call(catalog.release_for(cc), capability, inputs or {}, key=key or str(uuid.uuid4()))

    @mcp.tool()
    @guarded
    def cc_start(cc: str, capability: str, inputs: dict | None = None, key: str | None = None) -> Any:
        """Start a served capability (native process or image). Returns the instance with native endpoints and, when running, a `handle` you can pass to client CCs. Always cc_stop it when done."""
        return catalog.start(cc, capability, inputs, key)

    @mcp.tool()
    @guarded
    def cc_instance(instance: str) -> Any:
        """Inspect a started instance (state, readiness, endpoints, image identity)."""
        return catalog.host.inspect_instance(instance)

    @mcp.tool()
    @guarded
    def cc_stop(instance: str) -> Any:
        """Stop an instance this session owns and confirm it stopped. A state other than 'stopped' means stop was not confirmed."""
        return catalog.host.stop(instance)

    return mcp


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ccs', required=True, help='folder containing CC packages (each with cc.yaml)')
    p.add_argument('--store', required=True)
    p.add_argument('--grant', action='append', default=[])
    p.add_argument('--workspace', help="path exposed as the 'workspace' handle")
    a = p.parse_args(argv)
    build(Catalog(Path(a.ccs), Path(a.store), a.grant, Path(a.workspace) if a.workspace else None)).run()


if __name__ == '__main__':
    main()
