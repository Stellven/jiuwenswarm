#!/usr/bin/env python3
"""Collect the deployed demo's read-only records for the offline browser export."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import importlib.util
import ipaddress
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

API = '/api/factory'
RUN_ORDERS = (1, 2, 3)
FIXTURE = '/capsules/kv_reuse_lab/fixture'
FIXTURE_FILES = {'stock': 'stock.log', 'configured': 'configured.log', 'summary': 'summary.json'}
ARM_NAMES_BOX = re.compile(r'<section class="arm-names"[^>]*>.*?</section>', re.S)
RUN_FOUR_LETTER = re.compile(r'<tr><th scope="row">E</th><td>[^<]*</td></tr>')
RUN_FOUR_COMPOSITION = ' AQBCE = AQBC + E (Run 4).'


# URLSearchParams uses application/x-www-form-urlencoded with '*' allowed and '~' escaped.
def endpoint(route, **query):
    if not query:
        return API + route
    return API + route + '?' + urlencode(sorted(query.items()), safe='*').replace('~', '%7E')


def segment(value):
    return quote(value, safe="-_.!~*'()")


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Snapshot:
    def __init__(self, origin, cache):
        self.origin = origin
        self.cache = cache
        self.entries = {}
        self.excluded_demos = []
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def capture(self, key):
        cache_path = self.cache / sha256(key.encode()).hexdigest() if self.cache else None
        if cache_path and cache_path.is_file():
            return json.loads(cache_path.read_bytes())
        try:
            response = self.opener.open(self.origin + key, timeout=90)
        except HTTPError as error:
            if error.code not in (404, 422):
                raise
            response = error
        with response:
            status = response.status
            content_type = response.headers.get_content_type()
            raw = response.read()
        body = json.loads(raw) if content_type == 'application/json' else raw.decode('utf-8')
        value = {'status': status, 'contentType': content_type, 'body': body}
        if cache_path:
            cache_path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return value

    def get(self, key, *, optional=False):
        if key not in self.entries:
            self.entries[key] = self.capture(key)
        entry = self.entries[key]
        if entry['status'] != 200 and not optional:
            # Source paths in unsuccessful responses may include private locations.
            raise ValueError(f'Deployed GET returned {entry["status"]} for endpoint {key.split("?")[0]}')
        return entry['body']

    def many(self, keys, workers, *, optional=False):
        keys = sorted(set(keys) - self.entries.keys())
        with ThreadPoolExecutor(max_workers=workers) as pool:
            self.entries.update(zip(keys, pool.map(self.capture, keys)))
        for key in keys:
            self.get(key, optional=optional)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def file_paths(rows):
    return {row['path'] for row in rows if row.get('path') and row.get('integrity') != 'missing'}


def artifact_paths(detail):
    return {artifact: file['path'] for file in detail['files'] if file['integrity'] != 'missing'
            for artifact in file.get('artifact_ids', ())}


def scope_evidence(evidence, aliases, runs, artifacts, files):
    def retained(row):
        if not isinstance(row, dict) or row.get('run_id') not in aliases:
            return None
        run_id = aliases[row['run_id']]
        result = {**row, 'run_id': run_id, 'run_name': runs[run_id]['name']}
        if row.get('path') and row['path'] not in files[run_id]:
            path = artifacts[run_id].get(row.get('artifact_id') or row.get('report_artifact_id'))
            if not path:
                return None
            result['path'] = path
        return result

    result = {}
    for key, value in evidence.items():
        if key == 'runs':
            ids = dict.fromkeys(aliases[row['id']] for row in value if row['id'] in aliases)
            result[key] = [{field: runs[run_id][field] for field in ('id', 'name', 'kind')} for run_id in ids]
        elif isinstance(value, list):
            result[key] = [row for item in value if (row := retained(item)) is not None]
        elif key == 'latest_builder_run':
            builder = retained(value)
            if builder:
                for part in ('build', 'lab', 'report'):
                    entry = retained(builder.get(part))
                    if entry and part in ('build', 'lab') and entry.get('artifact'):
                        entry['artifact'] = retained(entry['artifact'])
                    builder[part] = entry
            result[key] = builder
        else:
            result[key] = retained(value)
    return result


def capsule_file_links(evidence):
    for field in ('artifacts', 'analyses'):
        yield from evidence[field]
    if receipt := evidence['latest_verify_receipt']:
        yield receipt
    if builder := evidence['latest_builder_run']:
        if report := builder.get('report'):
            yield report
        for part in ('build', 'lab'):
            if (entry := builder.get(part)) and entry.get('artifact'):
                yield entry['artifact']


def retain_original_files(snapshot, details, aliases, artifacts, files, workers):
    linked = {}
    for detail in details:
        for row in capsule_file_links(detail['evidence']):
            original_id, path = row.get('run_id'), row.get('path')
            run_id = aliases.get(original_id)
            artifact = row.get('artifact_id') or row.get('report_artifact_id')
            if run_id and path and path not in files[run_id] and artifact not in artifacts[run_id]:
                linked[endpoint('/runs/' + segment(original_id) + '/file', path=path)] = (run_id, path, artifact)
    snapshot.many(linked.keys(), workers, optional=True)
    for key, (run_id, path, artifact) in sorted(linked.items()):
        entry = snapshot.entries.pop(key)
        if entry['status'] != 200:
            continue
        body = entry['body']
        offline_key = endpoint('/runs/' + segment(run_id) + '/file', path=path)
        snapshot.entries[offline_key] = entry
        run_detail = snapshot.get(endpoint('/runs/' + segment(run_id)))
        run_detail['files'].append({field: value for field, value in body.items() if field not in ('content', 'truncated')})
        files[run_id].add(path)
        if artifact:
            artifacts[run_id][artifact] = path


def recover_material(snapshot, materials, release_roots):
    import yaml

    recovered = 0
    for key, (digest, file) in materials.items():
        if snapshot.entries[key]['status'] == 200 or not re.fullmatch('[0-9a-f]{64}', digest or ''):
            continue
        for root in release_roots:
            bundle = root / digest / 'bundle'
            target = bundle / file['path']
            if not target.resolve().is_relative_to(bundle.resolve()) or not target.is_file():
                continue
            with target.open('rb') as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024 or sha256(raw).hexdigest() != file['expected_sha256']:
                continue
            content = raw.decode('utf-8', errors='replace')
            parsed = None
            try:
                if target.suffix == '.json':
                    parsed = json.loads(content)
                elif target.suffix in ('.yml', '.yaml') and not any(
                    isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken, yaml.tokens.TagToken))
                    for token in yaml.scan(content)
                ):
                    parsed = yaml.safe_load(content)
                parsed = json.loads(json.dumps(parsed, allow_nan=False, default=str))
            except (ValueError, TypeError, RecursionError, yaml.YAMLError):
                parsed = None
            body = dict(file, content=content, parsed=parsed, integrity='verified', truncated=False)
            snapshot.entries[key] = {'status': 200, 'contentType': 'application/json', 'body': body}
            recovered += 1
            break
    return recovered


def collect(snapshot, workers, release_roots):
    listing = snapshot.get(endpoint('/runs'))
    snapshot.excluded_demos = [row for row in listing['runs'] if row.get('demo') and row.get('demo_order') not in RUN_ORDERS]
    selected = [row for row in listing['runs'] if row.get('demo') and row.get('demo_order') in RUN_ORDERS]
    selected.sort(key=lambda run: run['demo_order'])
    if tuple(row['demo_order'] for row in selected) != RUN_ORDERS or any(row['kind'] != 'bundle' for row in selected):
        raise ValueError('Expected three deployed curated demo replays in order')
    listing.update(runs=selected, launch_templates=[], launch_enabled=False, live_demos_enabled=False)
    runs = {row['id']: row for row in selected}
    aliases = {run_id: run_id for run_id in runs}
    artifacts, files, node_keys, file_keys = {}, {}, [], []
    for run_id in runs:
        path = '/runs/' + segment(run_id)
        detail = snapshot.get(endpoint(path))
        original_id = detail['run'].get('original_run_id')
        if original_id:
            aliases[original_id] = run_id
        artifacts[run_id] = artifact_paths(detail)
        files[run_id] = file_paths(detail['files'])
        nodes = {node['node_id'] for graph in (detail['graph'], detail['recorded_plan']) for node in graph['nodes']}
        node_keys.extend(endpoint(path + '/nodes/' + segment(node)) for node in nodes)
        file_keys.extend(endpoint(path + '/file', path=file) for file in files[run_id])
        snapshot.get(endpoint(path + '/story', since=0))
        snapshot.get(endpoint(path + '/state'), optional=True)
        snapshot.get(endpoint(path + '/session'), optional=True)
    snapshot.many(node_keys, workers)
    diff_keys, materials = [], {}
    for key in node_keys:
        node = snapshot.get(key)
        path = key.removeprefix(API)
        diff_keys.extend(endpoint(path + '/diff', output=output['id']) for output in node['outputs']
                         if output['kind'] == 'diff' and ((output.get('summary') or {}).get('diff_artifact_id') or output.get('artifact_ids')))
        materials.update({endpoint(path + '/material', cc=capsule['id'], path=file['path']): (capsule['material_digest'], file)
                          for capsule in node['capsules'] if capsule.get('material_source') == 'sealed'
                          for file in capsule['files'] if file.get('integrity') != 'missing'})
    print(f'Collecting {len(file_keys)} run files, {len(node_keys)} nodes, {len(diff_keys)} diffs and {len(materials)} sealed materials', flush=True)
    snapshot.many(file_keys, workers)
    snapshot.many(materials.keys(), workers, optional=True)
    recovered = recover_material(snapshot, materials, release_roots) if release_roots else 0
    snapshot.many(diff_keys, workers, optional=True)

    catalog = snapshot.get(endpoint('/capsules', usage='false'))
    snapshot.get(endpoint('/capsules'))
    snapshot.get(endpoint('/headlines'))
    shared_files = file_paths([catalog['contract']['raw'], catalog['contract']['readable'], *catalog['owner_ontology']])
    usage_catalog = snapshot.get(endpoint('/capsules'))
    name_counts = Counter(card['name'] for card in catalog['capsules'])
    # The deployed lookup accepts a full capsule ID when two bundles share a name.
    for card in (*catalog['capsules'], *usage_catalog['capsules']):
        if name_counts[card['name']] > 1:
            card['name'] = card['id']
    cards = {card['name']: card for card in catalog['capsules']}
    capsule_keys = {name: endpoint('/capsules/' + segment(name)) for name in cards}
    print(f'Collecting {len(capsule_keys)} capsule entries', flush=True)
    snapshot.many(capsule_keys.values(), workers)
    retain_original_files(snapshot, (snapshot.get(key) for key in capsule_keys.values()), aliases, artifacts, files, workers)
    capsule_files = []
    for name, key in capsule_keys.items():
        detail = snapshot.get(key)
        detail['name'] = name
        detail['evidence'] = scope_evidence(detail['evidence'], aliases, runs, artifacts, files)
        snapshot.entries[endpoint('/capsules/' + segment(detail['id']))] = snapshot.entries[key]
        capsule_files.extend(endpoint('/capsules/' + segment(name) + '/file', path=file)
                             for file in file_paths(detail['files']) | (shared_files if detail['starred'] else set()))
    for card in usage_catalog['capsules']:
        evidence = snapshot.get(capsule_keys[card['name']])['evidence']
        card.update(used_in_runs=len(evidence['runs']), featured_analysis_at=None if not evidence['analyses'] else card.get('featured_analysis_at'))
    print(f'Collecting {len(capsule_files)} capsule files', flush=True)
    snapshot.many(capsule_files, workers)
    snapshot.get(endpoint(FIXTURE))
    fixture = {filename: snapshot.get(endpoint(FIXTURE + '/' + name)) for name, filename in FIXTURE_FILES.items()}
    return fixture, recovered


REMOTE_URL = re.compile(r'(?i)\b(?:https?|ftp|ssh|git|wss?)://[^\s"\'`<>\[\]{}()\\]+')
FILE_URL = re.compile(r'(?i)\bfile://[^\s"\'`<>\[\]{}()\\]+')
SCP_URL = re.compile(r'(?i)\b[\w.-]+@[\w.-]+:[^\s"\'`<>\[\]{}()\\]+')
HOME_PATH = re.compile(r'(?i)(?:/(?:home|users)/[\w.-]+|/root(?=/|\b)|[a-z]:\\{1,2}users\\{1,2}[\w.-]+)(?=/|\\|\b)')
HOST = re.compile(r'(?i)\b(?:[\w-]+\.)+(?:ts\.net|local|internal|localhost)\b|\blocalhost\b')
IPV4 = re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
IPV6 = re.compile(r'(?<![\w:])(?:[\da-f]{1,4}:){1,7}:[\da-f:]+(?![\w:])', re.I)
PRIVATE_FIELDS = re.compile(r'(?i)^(?:host(?:_?name)?|account(?:_?(?:name|id))?|username|email|login|oauth_subject)$')


def private_ip(match):
    try:
        address = ipaddress.ip_address(match[0])
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address in ipaddress.ip_network('100.64.0.0/10')


class Scrub:
    def __init__(self, redact, terms):
        self.redact = redact
        self.count = Counter()
        self.terms = re.compile(r'(?<![\w@+-])(?:' + '|'.join(map(re.escape, terms)) + r')(?![\w+-])', re.I) if terms else None

    def text(self, value):
        scrubbed = self.redact.scrub_bytes(value.encode('utf-8')).decode('utf-8')
        self.count['additional credential and account patterns'] += int(scrubbed != value)
        value = scrubbed
        for name, pattern, replacement in (
            ('remote URLs', REMOTE_URL, '#external-reference'),
            ('file URLs', FILE_URL, '#local-reference'),
            ('remote login paths', SCP_URL, '[remote path removed]'),
            ('home paths', HOME_PATH, '~'),
            ('private hostnames', HOST, '[host removed]'),
            ('known local host and account names', self.terms, '[private name removed]'),
        ):
            if pattern:
                value, count = pattern.subn(replacement, value)
                self.count[name] += count
        for pattern in (IPV4, IPV6):
            def replace_ip(match):
                if not private_ip(match):
                    return match[0]
                self.count['private network addresses'] += 1
                return '[address removed]'

            value = pattern.sub(replace_ip, value)
        return value

    def value(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.value(item) for item in value]
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                safe_key = self.text(key)
                if safe_key in result:
                    raise ValueError('Redaction would collapse two record keys')
                if isinstance(item, str) and item and (self.redact.sensitive(key, item) or PRIVATE_FIELDS.fullmatch(key)):
                    item = '[private field removed]'
                    self.count['private account, host and credential fields'] += 1
                result[safe_key] = self.value(item)
            return result
        return value


def mock_scan(root, mock_exporter):
    # This is the original mock package scanner's compiled expression, loaded
    # without invoking the mock export or touching its data sources.
    secret = load_source(mock_exporter, 'mock_export_secret_pattern').SECRET
    checked = 0
    hits = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        checked += 1
        if secret.search(path.read_text(encoding='utf-8', errors='ignore')):
            hits.append(path.relative_to(root).as_posix())
    if hits:
        raise ValueError('Mock package secret scan matched files: ' + ', '.join(hits))
    return checked


def scope_report_letters(content):
    def selected_runs(match):
        return RUN_FOUR_LETTER.sub('', match[0]).replace(RUN_FOUR_COMPOSITION, '')

    return ARM_NAMES_BOX.sub(selected_runs, content)


def write_site(snapshot, fixture, output, scrub):
    output.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for path, entry in sorted(snapshot.entries.items()):
        if scrub.text(path) != path:
            raise ValueError('Private data found in an API key; cannot publish without a matched route rewrite')
        if path.endswith('/file?path=reports%2Flab-report.html') and entry['status'] == 200:
            original = entry['body']['content']
            scoped = scope_report_letters(original)
            scrub.count['out-of-scope run removed from report letter boxes'] += int(scoped != original)
            entry = {**entry, 'body': {**entry['body'], 'content': scoped}}
        mapping[path] = scrub.value(entry)
    data = json.dumps(mapping, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    for run in snapshot.excluded_demos:
        if run['id'] in data or run['name'] in data:
            raise ValueError(f'An excluded demo appears in the staged records (demo order {run["demo_order"]})')
    destination = output / 'data.js'
    with NamedTemporaryFile(mode='w', encoding='utf-8', prefix='.data-', dir=output.parent, delete=False) as temporary:
        temporary.write('window.__MUSE_STATIC__ = ' + data + ';\n')
    staged = Path(temporary.name)
    staged.chmod(0o644)
    staged.replace(destination)
    evidence = output / 'evidence' / 'prefix-reuse'
    evidence.mkdir(parents=True, exist_ok=True)
    for filename, value in sorted(fixture.items()):
        value = scrub.value(value)
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        (evidence / filename).write_text(text, encoding='utf-8')
    return mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', help='Loopback origin serving the deployed Factory API')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--cache', type=Path, help='Private capture directory outside the export')
    parser.add_argument('--mock-exporter', required=True, type=Path, help='Existing mock package export_ui_mock.py')
    parser.add_argument('--private-term', action='append', default=[], help='Known host or account literal to scrub')
    parser.add_argument('--release-root', action='append', type=Path, default=[],
                        help='Read-only sealed capsule release store for verified missing replay material')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--scan-only', action='store_true')
    args = parser.parse_args()
    if args.scan_only:
        print(f'Mock package secret scan passed over {mock_scan(args.output, args.mock_exporter)} files')
        return
    if not args.origin or not args.audit:
        parser.error('--origin and --audit are required for capture')
    url = urlsplit(args.origin)
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1') or url.path or url.query or url.fragment:
        parser.error('--origin must be a loopback HTTP origin')
    if args.cache:
        args.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    redact = load_source(Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/redact.py', 'factory_redact')
    scrub = Scrub(redact, args.private_term)
    snapshot = Snapshot(args.origin, args.cache)
    fixture, recovered = collect(snapshot, args.workers, args.release_root)
    mapping = write_site(snapshot, fixture, args.output, scrub)
    checked = mock_scan(args.output, args.mock_exporter)
    counts = Counter(entry['status'] for entry in mapping.values())
    missing = [key for key, entry in mapping.items() if entry['status'] != 200]
    run_ids = [row['id'] for row in mapping[endpoint('/runs')]['body']['runs']]
    audit = {
        'GET responses': dict(sorted(counts.items())),
        'Replay ids': run_ids,
        'Capsule entries': len(mapping[endpoint('/capsules')]['body']['capsules']),
        'Sealed capsule material files recovered from pinned releases': recovered,
        'Fixture originals': sorted(fixture),
        'Scrub counts': dict(sorted(scrub.count.items())),
        'Mock package secret scan': {'files checked': checked, 'matches': 0},
        'Unsuccessful deployed GET responses': missing,
        'Data snapshot SHA-256': sha256((args.output / 'data.js').read_bytes()).hexdigest(),
    }
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(mapping)} GET records. Mock package secret scan passed over {checked} files.')


if __name__ == '__main__':
    main()
