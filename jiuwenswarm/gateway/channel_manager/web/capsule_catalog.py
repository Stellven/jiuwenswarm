"""Read-only browser projection for factory CCs and their pinned materials."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

import yaml
from fastapi import HTTPException

from jiuwenswarm.ccv2.ccv2 import contained, load, release_manifest_bytes, sha, tree_files
from jiuwenswarm.factory.capsules import capsule_row
from jiuwenswarm.factory.contract import CONTRACTS
from jiuwenswarm.factory.redact import sanitize, scrub_bytes

CCS = CONTRACTS.parent / 'ccs'
MAX_FILE = 1024 * 1024
SHA256 = re.compile(r'[0-9a-f]{64}')
OWNER_MANIFEST = 'SHA256SUMS'
CONTRACT_ID = 'star-deepseek-v1'
CONTRACT_FILES = (CONTRACT_ID + '.json', CONTRACT_ID + '.md')
SECTION_KEYS = ('guide', 'method', 'ontology', 'source_map', 'validation', 'verifier')
STAR_DETAILS = {
    'observability_event_recorder': ('C1', 'Generation runtime', 'Runtime event recorder',
                                    'Instrumentation for comparing the engine paths'),
    'weight_placement_planner': ('C2', 'Weight residency', 'Weight placement planner',
                                 'Profile-driven hot-expert residency'),
    'expert_weight_cache': ('C3', 'Weight residency', 'Expert weight cache',
                            'Profile-driven hot-expert residency'),
    'expert_demand_predictor': ('C4', 'Weight residency', 'Expert demand predictor',
                                'Expert lookahead'),
    'batch_layout_mapper': ('C5', 'Generation runtime', 'Batch layout mapper',
                           'Work-split prefill chunking'),
}
CONTRACT_CLAUSES = (
    ('source', 'Pinned llama.cpp source', 'Apply the builder in an owned checkout of the pinned stock revision.'),
    ('parity', 'Greedy continuation parity', 'Preserve stock output with the feature gate unset.'),
    ('qualification', 'Verifier and scorer qualification', 'Pass the capsule verifier and frozen fixture scorer S1–S5/S5L, then retain the gate-set activation evidence.'),
    ('workload', 'Fixed Spark workload and limits', 'Use fixed 512- and 2048-token prompts, 32 greedy tokens and the same 100 GiB and eight-CPU cap.'),
    ('measurement', 'Comparable arm measurements', 'Record client TTFT over five warm ABBA repeats, with Strata and stock controls, plus load and capacity evidence.'),
)


def _visible(relative):
    return (bool(relative) and '\\' not in relative
            and not any(part in {'', '.', '..'} or part.startswith('.') for part in relative.split('/')))


def _target(root, relative):
    if not _visible(relative):
        raise ValueError('Path must be a visible relative file')
    return contained(root, relative)


def _read(root, relative):
    target = _target(root, relative)
    if not target.is_file():
        raise FileNotFoundError(relative)
    with target.open('rb') as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError('Capsule file exceeds view limit')
    return data


def _json_file(root, relative):
    return json.loads(_read(root, relative))


def _parse(relative, content):
    try:
        suffix = Path(relative).suffix
        if suffix == '.json':
            value = json.loads(content)
        elif suffix in {'.yaml', '.yml'}:
            if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken, yaml.tokens.TagToken))
                   for token in yaml.scan(content)):
                return None
            value = yaml.safe_load(content)
        else:
            return None
        return sanitize(json.loads(json.dumps(value, allow_nan=False, default=str)))
    except (ValueError, TypeError, RecursionError, yaml.YAMLError):
        return None


def _file_row(path, size=0, actual=None, expected=None):
    integrity = 'missing' if actual is None else (
        ('verified' if actual == expected else 'mismatch') if expected else 'untracked')
    return dict(path=path, size=size, sha256=actual, expected_sha256=expected, integrity=integrity)


class CapsuleCatalog:
    def __init__(self, root=CCS, contracts=CONTRACTS, owner_ontology=None):
        self.root = Path(root).resolve()
        self.contracts = Path(contracts).resolve()
        owner = owner_ontology or os.environ.get(
            'FACTORY_OWNER_ONTOLOGY_ROOT', str(Path.home() / 'predemo-spark/inputs/ontology'))
        self.owner = Path(owner).expanduser().resolve()

    def paths(self):
        paths = {path.relative_to(self.root).as_posix() for path in self.root.rglob('cc.yaml')
                 if _visible(path.relative_to(self.root).as_posix())}
        paths.update(f'{name}/cc.yaml' for name in STAR_DETAILS)
        return sorted(paths)

    def pins(self, file):
        try:
            records = _json_file(self.root, file)['releases']
        except (OSError, ValueError, KeyError, TypeError):
            return {}
        if not isinstance(records, list):
            return {}
        return {row['path']: row for row in records
                if isinstance(row, dict) and isinstance(row.get('path'), str)
                and SHA256.fullmatch(str(row.get('new_release')))}

    def owner_pins(self):
        try:
            lines = _read(self.owner, OWNER_MANIFEST).decode('utf-8').splitlines()
        except (OSError, ValueError):
            return {}
        pins = {}
        for line in lines:
            digest, _, name = line.partition('  ')
            if SHA256.fullmatch(digest) and _visible(name) and '/' not in name:
                pins[name] = digest
        return pins

    @staticmethod
    def external_row(root, relative, prefix, expected=None):
        path = f'{prefix}/{relative}'
        try:
            content = _read(root, relative)
        except (OSError, ValueError):
            return _file_row(path, expected=expected)
        return _file_row(path, len(content), sha(content), expected)

    def contract(self):
        raw, readable = [self.external_row(self.contracts, relative, 'contract') for relative in CONTRACT_FILES]
        return dict(id=CONTRACT_ID, raw=raw, readable=readable,
                    clauses=[dict(id=key, title=title, detail=detail) for key, title, detail in CONTRACT_CLAUSES])

    def previous_manifest(self, root, pin):
        """Use a previous inventory only when its retained release digest matches."""
        try:
            state = contained(root, '.cc-state')
            manifests = sorted(state.glob('*.manifest.json'))
            old_digest = pin.get('old_release')
            for path in manifests:
                target = contained(root, path.relative_to(root).as_posix())
                if target.is_file() and target.stat().st_size <= MAX_FILE:
                    content = target.read_bytes()
                    if sha(content) == old_digest:
                        return json.loads(content)
        except (OSError, ValueError):
            pass
        return {}

    def summary(self, relative, pin, *, detail=False):
        path = contained(self.root, relative)
        root = path.parent
        name = root.name
        star = STAR_DETAILS.get(name) if root.parent == self.root else None
        expected = pin.get('new_release')
        declaration, rows, digest, base = {}, [], None, {}
        try:
            declaration = load(path)
            rows = tree_files(root)
            digest = sha(release_manifest_bytes(declaration, rows))
        except (OSError, ValueError, yaml.YAMLError):
            pass
        if declaration:
            try:
                base = capsule_row(path, declaration, rows)
            except (OSError, ValueError):
                pass
        previous = self.previous_manifest(root, pin) if detail and star and digest != expected else {}
        material_decl = declaration or previous.get('declaration', {})
        materials = {key: value['path'] for key, value in material_decl.get('materials', {}).items()}
        caps = material_decl.get('capabilities', {})
        expected_files = {}
        if digest is not None and digest == expected:
            expected_files = {row['path']: row['sha256'] for row in rows}
        elif declaration and previous:
            # Transport migration changes the declaration and adds a roles sidecar.
            # Authenticate the reconstructed manifest against the current release pin.
            transport = {'cc.yaml', materials.get('roles')}
            known = [row for row in previous.get('files', []) if row['path'] not in transport]
            known.extend(row for row in rows if row['path'] in transport)
            if sha(release_manifest_bytes(declaration, known)) == expected:
                expected_files = {row['path']: row['sha256'] for row in known}
        sections = {key: materials[key] for key in SECTION_KEYS if key in materials}
        component_path = next((value for value in materials.values() if value.endswith('/component.yaml')), None)
        if component_path:
            sections['component'] = component_path
        if 'verifier' not in sections and 'verify' in caps and any(row['path'] == 'run.py' for row in rows):
            sections['verifier'] = 'run.py'
        guide = ''
        if 'guide' in sections:
            try:
                guide = _read(root, sections['guide']).decode('utf-8')
            except (OSError, ValueError):
                pass
        paragraphs = [paragraph for paragraph in guide.split('\n\n') if paragraph.strip() and not paragraph.startswith('#')]
        description = ' '.join(paragraphs[0].split()) if paragraphs else next(
            (cap.get('does', '') for cap in caps.values() if cap.get('does')), '')
        integrity = ('verified' if expected == digest else 'mismatch') if expected else (
            'untracked' if digest else 'missing')
        summary = dict(name=name, id=material_decl.get('id', name),
                       version=declaration.get('version', 'unknown'), starred=bool(star),
                       kind='builder' if star else 'support', component=star[1] if star else None,
                       subcomponent=star[2] if star else None, description=description,
                       strata_mechanism=star[3] if star else None, arm=star[0] if star else None,
                       binding=base.get('binding', 'unavailable'), capabilities=base.get('capabilities', list(caps)),
                       contract_id=CONTRACT_ID if star else None,
                       digest=digest, expected_digest=expected, integrity=integrity)
        if detail:
            indexed = {row['path']: row for row in rows if _visible(row['path'])}
            files = [_file_row(name, indexed[name]['size'], indexed[name]['sha256'], expected_files.get(name))
                     if name in indexed else _file_row(name, expected=expected_files[name])
                     for name in sorted(set(indexed) | {name for name in expected_files if _visible(name)})]
            parsed = {}
            for key in ('ontology', 'component'):
                if key in sections:
                    try:
                        parsed[key] = _parse(sections[key], _read(root, sections[key]).decode('utf-8'))
                    except (OSError, ValueError):
                        pass
            summary.update(materials=materials, sections=sections, ontology=parsed.get('ontology'),
                           component_spec=parsed.get('component'), verifier=caps.get('verify', {}).get('does'),
                           contract_clauses=[row[0] for row in CONTRACT_CLAUSES] if star else [],
                           files=files)
        return summary

    def listing(self):
        pins = self.pins('migration.json') | self.pins('star-transport-migration.json')
        capsules = []
        for relative in self.paths():
            try:
                capsules.append(self.summary(relative, pins.get(relative, {})))
            except ValueError:
                continue
        owner_pins = self.owner_pins()
        owner = [self.external_row(self.owner, name, 'owner-ontology', owner_pins.get(name))
                 for name in [OWNER_MANIFEST, *owner_pins] if owner_pins]
        return sanitize(dict(capsules=capsules, contract=self.contract(), owner_ontology=owner))

    def resolve(self, name):
        candidates = self.paths()
        direct = [relative for relative in candidates if Path(relative).parent.name == name]
        if len(direct) == 1:
            return direct[0]
        for relative in candidates:
            try:
                if load(contained(self.root, relative))['id'] == name:
                    return relative
            except (OSError, ValueError, yaml.YAMLError):
                continue
        raise HTTPException(404, 'Capsule not found')

    def detail(self, name):
        relative = self.resolve(name)
        pins = self.pins('migration.json') | self.pins('star-transport-migration.json')
        try:
            return sanitize(self.summary(relative, pins.get(relative, {}), detail=True))
        except ValueError:
            raise HTTPException(404, 'Capsule not found') from None

    def file(self, name, path):
        detail = self.detail(name)
        prefix, _, relative = path.partition('/')
        if detail['starred'] and prefix == 'contract' and relative in CONTRACT_FILES:
            root, expected = self.contracts, None
        elif detail['starred'] and prefix == 'owner-ontology':
            pins = self.owner_pins()
            if relative not in pins and (relative != OWNER_MANIFEST or not pins):
                raise HTTPException(404, 'File is not part of the pinned owner ontology')
            root, expected = self.owner, pins.get(relative)
        else:
            files = {row['path']: row for row in detail['files']}
            if path not in files:
                raise HTTPException(404, 'File is not part of this capsule')
            root = (self.root / self.resolve(name)).parent
            relative, expected = path, files[path]['expected_sha256']
        try:
            data = _read(root, relative)
        except (OSError, ValueError):
            raise HTTPException(404, 'Capsule file is unavailable') from None
        content = scrub_bytes(data).decode('utf-8', errors='replace')
        parsed = _parse(relative, content)
        if parsed is not None:
            original = _parse(relative, data.decode('utf-8', errors='replace'))
            # When key-based redaction changed a value, return only the sanitized tree.
            try:
                if Path(relative).suffix == '.json' and original != json.loads(content):
                    content = json.dumps(parsed, ensure_ascii=False, indent=2)
                elif Path(relative).suffix in {'.yaml', '.yml'} and original != yaml.safe_load(content):
                    content = yaml.safe_dump(parsed, allow_unicode=True, sort_keys=False)
            except (ValueError, yaml.YAMLError):
                pass
        return sanitize(dict(_file_row(path, len(data), sha(data), expected),
                             content=content, parsed=parsed, truncated=False))
