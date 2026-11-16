"""Export an existing factory recording as a self-contained, read-only HTML replay.

This module never constructs a FactoryService, dispatches a stage, launches a
process, or changes the original recording. The browser uses the same prefix
projector as the hosted application. Exported source is immutable recorded
output; its publication sequence controls when it becomes visible.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
from typing import Any


class ReplayExportError(ValueError):
    """An incomplete or inconsistent recording cannot be exported."""


_FRONTEND = Path(__file__).resolve().parents[1] / 'channels' / 'web' / 'frontend' / 'src'
_TEXT_KINDS = {'construction.cpp', 'construction.header', 'construction.cmake',
               'construction.code_diff', 'value.report', 'construction.execution',
               'construction.portability', 'construction.build'}
_ATTACHMENT_KINDS = _TEXT_KINDS | {'construction.package'}
_THEME_TOKENS = (
    'color-surface-page', 'color-surface-card', 'color-surface-hover',
    'color-surface-muted', 'color-text-primary', 'color-text-secondary',
    'color-text-inverse', 'color-border-default', 'color-border-strong',
    'color-action-primary', 'color-feedback-success', 'color-feedback-danger',
    'color-feedback-info', 'color-feedback-warning', 'color-text-disabled',
    'color-code-diff-added-surface', 'color-code-diff-removed-surface',
    'font-mono', 'font-body', 'font-size-base', 'font-size-lg', 'font-size-sm',
    'radius-sm', 'radius-md',
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ReplayExportError(f'{label}: invalid JSON') from exc


def _read(root: Path, value: str | Path, *, sha256: str | None = None,
          size: int | None = None) -> tuple[bytes, Path]:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ReplayExportError(f'Missing recorded file: {candidate}') from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ReplayExportError(f'Recorded file escapes run directory: {candidate}')
    raw = resolved.read_bytes()
    if sha256 is not None and _sha(raw) != sha256:
        raise ReplayExportError(f'SHA-256 mismatch: {candidate}')
    if size is not None and len(raw) != size:
        raise ReplayExportError(f'Recorded size mismatch: {candidate}')
    return raw, resolved


def _time(value: Any, label: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.utcoffset() is None:
            raise ValueError('timezone required')
        return result
    except (ValueError, AttributeError, TypeError) as exc:
        raise ReplayExportError(f'{label}: invalid timezone-aware timestamp') from exc


def _encoded(raw: bytes) -> str:
    return base64.b64encode(raw).decode('ascii')


def load_recording(run_dir: str | Path) -> dict:
    """Validate existing disk evidence without consulting mutable working code."""
    root = Path(run_dir).resolve(strict=True)
    run_raw, _ = _read(root, 'run.json')
    event_raw, _ = _read(root, 'events.jsonl')
    run = _json(run_raw, 'run.json')
    if not isinstance(run, dict) or not isinstance(run.get('id'), str):
        raise ReplayExportError('Invalid factory run')
    lines = event_raw.splitlines()
    if not lines or any(not line.strip() for line in lines):
        raise ReplayExportError('Event recording is empty or contains a blank record')
    events = [_json(line, f'events.jsonl:{index}') for index, line in enumerate(lines, 1)]
    previous = None
    for index, event in enumerate(events, 1):
        if (not isinstance(event, dict) or type(event.get('sequence')) is not int or
                event['sequence'] != index or not isinstance(event.get('type'), str) or
                not isinstance(event.get('payload'), dict)):
            raise ReplayExportError(f'Invalid event or noncontiguous sequence at {index}')
        recorded_time = _time(event.get('time'), f'Event {index}')
        if previous is not None and recorded_time < previous:
            raise ReplayExportError(f'Event time moved backwards at sequence {index}')
        previous = recorded_time
    if run.get('sequence') != len(events):
        raise ReplayExportError('run.json sequence does not match events.jsonl')
    revisions = [event['payload'] for event in events if event['type'] == 'graph.updated']
    if revisions != run.get('graph_revisions', []):
        raise ReplayExportError('Graph revisions differ from original graph.updated events')
    for number, revision in enumerate(revisions, 1):
        if revision.get('revision') != number:
            raise ReplayExportError('Graph revisions are not contiguous')
        ids = [node.get('id') for node in revision.get('nodes', []) if isinstance(node, dict)]
        if len(ids) != len(revision.get('nodes', [])) or len(set(ids)) != len(ids):
            raise ReplayExportError(f'Invalid node set in graph revision {number}')
        if any(edge.get('from') not in ids or edge.get('to') not in ids
               for edge in revision.get('edges', [])):
            raise ReplayExportError(f'Dangling edge in graph revision {number}')
    terminal = [event['type'].split('.', 1)[1] for event in events
                if event['type'] in {'run.completed', 'run.failed', 'run.blocked'}]
    if terminal and terminal[-1] != run.get('status'):
        raise ReplayExportError('Recorded terminal event disagrees with run status')

    recipe = run.get('recipe', {})
    if not recipe.get('manifest_path') or not recipe.get('manifest_sha256'):
        raise ReplayExportError('Recording has no immutable executor recipe')
    manifest_raw, _ = _read(root, recipe['manifest_path'], sha256=recipe['manifest_sha256'])
    manifest = _json(manifest_raw, 'recipe manifest')
    retained_recipe = {key: value for key, value in recipe.items()
                       if key not in {'manifest_path', 'manifest_sha256'}}
    if retained_recipe != manifest:
        raise ReplayExportError('run.json recipe does not match retained manifest')
    for entry in manifest.get('files', []):
        _read(root, entry['snapshot_path'], sha256=entry['sha256'], size=entry['size'])
    recipe_digest = _sha(json.dumps([(entry['relative_path'], entry['sha256'])
                                    for entry in manifest['files']],
                                   sort_keys=True).encode())
    if recipe_digest != run.get('recipe_digest'):
        raise ReplayExportError('Executor source recipe digest mismatch')
    catalog_raw, _ = _read(root, manifest['catalog_path'], sha256=manifest['catalog_sha256'])
    request_raw, _ = _read(root, manifest['request_path'], sha256=manifest['request_capture_sha256'])
    catalog = _json(catalog_raw, 'recorded catalog')

    artifacts: dict[str, dict] = {}
    for artifact in run.get('artifacts', []):
        if artifact['id'] in artifacts:
            raise ReplayExportError(f'Duplicate artifact id: {artifact["id"]}')
        raw, _ = _read(root, artifact['path'], sha256=artifact['sha256'], size=artifact['size'])
        artifacts[artifact['id']] = {'record': artifact, 'raw': raw}
    published: dict[str, int] = {}
    for event in events:
        if event['type'] != 'stage.verified':
            continue
        for artifact in event['payload'].get('outputs', []):
            retained = artifacts.get(artifact.get('id'))
            if retained is None or retained['record'] != artifact:
                raise ReplayExportError('Published artifact differs from retained artifact record')
            if artifact['producer'] != event.get('node_id'):
                raise ReplayExportError('Published artifact producer differs from lifecycle event')
            published.setdefault(artifact['id'], event['sequence'])

    attachments = {}
    commits = []
    licenses = []
    for artifact_id, item in artifacts.items():
        artifact, raw = item['record'], item['raw']
        if artifact['kind'] == 'source.checkout':
            source = _json(raw, artifact_id)
            commits.append({'artifact_id': artifact_id, 'commit_sha': source.get('commit_sha'),
                            'repository_url': source.get('repository_url', run.get('request', {}).get('repository_url')),
                            'sha256': artifact['sha256']})
            if source.get('source_dir') and artifact_id in published:
                license_path = Path(source['source_dir']) / 'LICENSE'
                license_raw, license_resolved = _read(root, license_path)
                licenses.append({'repository_url': source.get('repository_url'),
                                 'commit_sha': source.get('commit_sha'),
                                 'path': str(license_resolved), 'sha256': _sha(license_raw),
                                 'sequence': published[artifact_id],
                                 'text': license_raw.decode('utf-8'), 'base64': _encoded(license_raw)})
        if artifact['kind'] not in _ATTACHMENT_KINDS or artifact_id not in published:
            continue
        attachment = {'artifact': artifact, 'sequence': published[artifact_id], 'base64': _encoded(raw)}
        if artifact['kind'] in _TEXT_KINDS:
            try:
                attachment['text'] = raw.decode('utf-8')
            except UnicodeDecodeError as exc:
                raise ReplayExportError(f'Published source is not UTF-8: {artifact_id}') from exc
        if artifact['kind'] == 'construction.code_diff':
            diff = _json(raw, 'code diff')
            if diff.get('schema') != 'strata.code.diff.v1' or not isinstance(diff.get('files'), list):
                raise ReplayExportError('Invalid published source diff')
            for pair in diff['files']:
                if any(not isinstance(pair.get(key), str) for key in
                       ('source_path', 'generated_path', 'source_code', 'generated_code')):
                    raise ReplayExportError('Invalid published source diff pair')
            attachment['diff'] = diff
        attachments[artifact_id] = attachment

    raw_evidence = {'run.json': _encoded(run_raw), 'events.jsonl': _encoded(event_raw),
                    'recipe-manifest.json': _encoded(manifest_raw),
                    'recorded-catalog.json': _encoded(catalog_raw),
                    'recorded-request.json': _encoded(request_raw)}
    return {'schema': 'ai4r.offline-replay:1', 'run': run, 'events': events,
            'catalog': catalog, 'attachments': attachments, 'raw_evidence': raw_evidence,
            'licenses': licenses,
            'provenance': {'run_id': run['id'], 'run_sha256': _sha(run_raw),
                           'events_sha256': _sha(event_raw), 'recipe_sha256': _sha(manifest_raw),
                           'recipe_digest': recipe_digest, 'catalog_sha256': _sha(catalog_raw),
                           'source_commits': commits, 'source_files': manifest['files'],
                           'artifact_count': len(artifacts), 'event_count': len(events),
                           'graph_revision_count': len(revisions)}}


def _safe_json(value: Any) -> str:
    result = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    for literal, replacement in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'),
                                 ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        result = result.replace(literal, replacement)
    return result


def _theme_css() -> str:
    """Copy the actual host defaults; no separate replay palette is invented."""
    sources = (_FRONTEND / 'styles' / 'foundation.css',
               _FRONTEND / 'styles' / 'themes' / 'default' / 'light.css')
    declarations = {}
    for source in sources:
        for key, value in re.findall(r'--([\w-]+)\s*:\s*([^;]+);', source.read_text()):
            declarations[key] = value.strip()
    missing = set(_THEME_TOKENS) - declarations.keys()
    if missing:
        raise ReplayExportError(f'Host theme tokens missing: {sorted(missing)}')
    return ':root{\n' + '\n'.join(f'--{key}:{declarations[key]};' for key in _THEME_TOKENS) + '\n}'


_CSS = """
*{box-sizing:border-box}html,body{margin:0;height:100%;font:var(--font-size-base)/1.45 var(--font-body);color:var(--color-text-primary);background:var(--color-surface-page)}
body{display:flex;flex-direction:column;overflow:hidden}button,select,input{font:inherit}button,select{padding:6px 10px;color:inherit;background:var(--color-surface-card);border:1px solid var(--color-border-default);border-radius:var(--radius-sm)}button{cursor:pointer}button:hover,button.active{border-color:var(--color-action-primary)}button:disabled{cursor:default;color:var(--color-text-disabled)}
header{padding:16px 20px 12px}h1{font-size:var(--font-size-lg);font-weight:600;margin:0 0 4px}p{margin:0}.controls{display:flex;gap:8px;align-items:center;padding:0 20px 12px;flex-wrap:wrap}.controls input{flex:1;min-width:100px;accent-color:var(--color-action-primary)}.record{display:flex;gap:12px;align-items:center;padding:0 20px 10px;font-family:var(--font-mono);font-size:var(--font-size-sm)}
main{flex:1;min-height:0;display:grid;grid-template-columns:220px minmax(300px,1fr) minmax(320px,0.8fr);gap:12px;padding:0 20px 16px}.panel{min-width:0;min-height:0;border:1px solid var(--color-border-default);border-radius:var(--radius-md);background:var(--color-surface-card);display:flex;flex-direction:column;overflow:hidden}.panel>h2{font-size:var(--font-size-base);font-weight:600;margin:0;padding:12px;border-bottom:1px solid var(--color-border-default)}.scroll{overflow:auto;min-height:0;flex:1}.pool-group{font-weight:600;margin:12px 10px 6px}.pool-item{display:block;text-align:left;width:calc(100% - 20px);margin:0 10px 5px;padding:7px 8px}.pool-item.selected{border-color:var(--color-action-primary)}
.canvas{position:relative;overflow:auto;flex:1;min-height:0}.graph{position:relative;margin:12px;min-width:560px}.graph svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none}.edge{fill:none;stroke:var(--color-border-strong);stroke-width:1}.edge.pending{stroke-dasharray:4 4}.edge.failed,.edge.blocked{stroke:var(--color-feedback-danger)}.edge.verified{stroke:var(--color-feedback-success)}.edge.running{stroke:var(--color-feedback-info)}.edge-label{font:11px var(--font-mono);fill:var(--color-text-primary);paint-order:stroke;stroke:var(--color-surface-card);stroke-width:4px;stroke-linejoin:round}.node{position:absolute;display:flex;align-items:center;gap:8px;text-align:left;background:var(--color-surface-card);border:1px solid var(--color-border-default);padding:10px;width:172px;min-height:55px;font-size:var(--font-size-sm)}.node.selected{border-color:var(--color-action-primary)}.dot{flex:none;display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--color-text-disabled)}.dot.running{background:var(--color-feedback-info)}.dot.verified,.dot.completed{background:var(--color-feedback-success)}.dot.failed,.dot.blocked{background:var(--color-feedback-danger)}.node-label{overflow-wrap:anywhere}.tabs{display:flex;gap:5px;padding:10px;flex-wrap:wrap;border-bottom:1px solid var(--color-border-default)}.tabs button{font-size:var(--font-size-sm);padding:5px 8px}.detail-heading{padding:10px 12px;display:flex;align-items:center;gap:8px;font-weight:600}.detail-content{padding:0 12px 12px;overflow:auto;min-height:0;flex:1}.detail-content pre{margin:0;white-space:pre-wrap;word-break:break-word;font:var(--font-size-sm)/1.5 var(--font-mono)}.attempt{margin:0 0 12px}.attempt-head{display:flex;gap:8px;align-items:center;margin-bottom:6px}.command{margin:8px 0}.command .argv{color:var(--color-action-primary)}.code-pair{display:grid;grid-template-columns:1fr 1fr;gap:8px;min-width:0}.code-pair section{min-width:0}.code-pair h3{font:var(--font-size-sm)/1.45 var(--font-mono);overflow-wrap:anywhere;margin:10px 0}.code-pair pre{border:1px solid var(--color-border-default);padding:8px;max-height:65vh;overflow:auto;white-space:pre;word-break:normal}.code-pair .generated{background:var(--color-code-diff-added-surface)}.file-control{margin:6px 0;display:block;max-width:100%;overflow-wrap:anywhere;text-align:left}.event-row{border-bottom:1px solid var(--color-border-default);padding:8px 0}.event-row button{display:block;text-align:left;width:100%;font-family:var(--font-mono)}.provenance-row{margin:10px 0;word-break:break-all}.provenance-row strong{display:block}.error{color:var(--color-feedback-danger);padding:16px}a{color:var(--color-action-primary)}
@media(max-width:1100px){main{grid-template-columns:180px minmax(280px,1fr) 330px;gap:8px;padding:0 10px 10px}.code-pair{grid-template-columns:1fr}.pool-item{font-size:var(--font-size-sm)}}
"""


def export_replay(run_dir: str | Path, output: str | Path) -> dict:
    root = Path(run_dir).resolve(strict=True)
    destination = Path(output).absolute()
    if destination.resolve().is_relative_to(root):
        raise ReplayExportError('Replay output must not modify the original run directory')
    payload = load_recording(root)
    projector_path = _FRONTEND / 'features' / 'workflowDemo' / 'replayProjection.js'
    viewer_path = Path(__file__).with_name('replay_viewer.js')
    projector = projector_path.read_text()
    viewer = viewer_path.read_text()
    if re.search(r'</script', projector + viewer, re.I):
        raise ReplayExportError('Viewer source contains an unsafe script closing tag')
    payload['provenance']['projector_sha256'] = _sha(projector.encode())
    payload['provenance']['viewer_sha256'] = _sha(viewer.encode())
    payload['exported_at'] = datetime.now(timezone.utc).isoformat()
    script = projector + '\nconst REPLAY_RECORDING = ' + _safe_json(payload) + ';\n' + viewer
    script_hash = _encoded(hashlib.sha256(script.encode()).digest())
    title = html.escape(f'Software Factory — {payload["run"]["id"]}')
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'">
<title>{title}</title><style>{_theme_css()}{_CSS}</style></head><body>
<header><h1>AI4Research Software Factory</h1><p>Retrieve, compose, execute, and verify stages to construct source code.</p></header>
<div class="controls"><strong>Recorded run</strong><button id="play">Play</button><button id="previous">Previous</button><button id="next">Next</button><input id="seek" type="range" min="0" value="0" aria-label="Recorded event"><select id="speed" aria-label="Replay speed"><option value="1">1×</option><option value="4" selected>4×</option><option value="16">16×</option></select><span id="position"></span></div>
<div class="record"><span id="run-id"></span><span id="record-time"></span><span id="run-status"></span></div>
<main><aside class="panel"><h2>Stage Pool</h2><div id="pool" class="scroll"></div></aside><section class="panel"><h2 id="graph-title">Production Graph</h2><div class="canvas"><div class="graph" id="graph"></div></div></section><aside class="panel"><h2>Execution Details</h2><div class="tabs" id="tabs"></div><div id="detail-heading" class="detail-heading"></div><div id="detail" class="detail-content"></div></aside></main>
<script type="module">{script}</script></body></html>'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding='utf-8')
    return {'output': str(destination), 'sha256': _sha(document.encode()),
            'size': len(document.encode()), **payload['provenance']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = export_replay(args.run_dir, args.output)
    except (ReplayExportError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'Replay export failed: {exc}\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'source_files'}, indent=2))


if __name__ == '__main__':
    main()
