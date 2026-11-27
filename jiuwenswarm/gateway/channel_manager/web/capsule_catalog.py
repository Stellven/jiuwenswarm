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
from .capsule_evidence import STAR_ARMS

CCS = CONTRACTS.parent / 'ccs'
# Display names aligned with the component atlas, keyed by stable capsule directory.
ATLAS_NAMES = 'atlas-names.json'
MAX_FILE = 1024 * 1024
SHA256 = re.compile(r'[0-9a-f]{64}')
OWNER_MANIFEST = 'SHA256SUMS'
CONTRACT_ID = 'star-deepseek-v1'
CONTRACT_FILES = (CONTRACT_ID + '.json', CONTRACT_ID + '.md')
PREFIX_FIXTURE_FILES = {
    'summary': 'summary.json',
    'stock': 'stock/server.log',
    'configured': 'configured/server.log',
}
SECTION_KEYS = {
    'guide': ('guide', 'skill'),
    'method': ('method', 'methodology'),
    'ontology': ('ontology',),
    'source_map': ('source_map', 'sources'),
    'validation': ('validation', 'verification', 'verification_units'),
    'verifier': ('verifier',),
    'profile': ('spark_profile',),
    'analysis': ('analysis',),
}
# CC-v2 roles describe tools and passive materials. These factory packages
# advertise analysis through a concrete capability, without a package kind.
ANALYSIS_CAPABILITIES = {
    'engine.expert_cache_lab': 'predict',
    'engine.gpu_kernel_lab': 'evaluate',
    'engine.heterogeneous_placement_lab': 'overlap_schedule',
    'engine.kv_reuse_lab': 'estimate',
    'engine.memory_residency_lab': 'plan',
    'engine.performance_baseline': 'ceilings',
    'engine.precision_lab': 'evaluate',
    'engine.serving_scheduler_lab': 'analyze',
    'engine.ssd_streaming_lab': 'evaluate',
    'factory.cc_workflow_lab': 'analyze_receipts',
    'factory.deep_profile': 'analyze',
    'factory.evidence_digest_lab': 'project',
    'factory.expert_prediction': 'evaluate',
    'factory.inference_lab': 'diagnose',
    'factory.methodology_ablation': 'ablation',
    'factory.methodology_diagnosis': 'diagnose',
    'factory.methodology_followup': 'followup',
    'factory.methodology_hypothesis': 'propose',
    'factory.methodology_out_of_core': 'cache_protocol',
    'factory.methodology_transfer_lab': 'analyze_abba',
    'factory.numerical_investigation_lab': 'compare_logits',
    'factory.spark_gap_analysis': 'analyze',
}
STAR_DETAILS = {
    'observability_event_recorder': ('Generation runtime', 'Runtime event recorder',
                                    'Instrumentation for comparing the engine paths'),
    'weight_placement_planner': ('Weight residency', 'Weight placement planner',
                                 'Profile-driven hot-expert residency'),
    'expert_weight_cache': ('Weight residency', 'Expert weight cache',
                            'Profile-driven hot-expert residency'),
    'expert_demand_predictor': ('Weight residency', 'Expert demand predictor',
                                'Expert lookahead'),
    'batch_layout_mapper': ('Generation runtime', 'Batch layout mapper',
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
                return None, False
            value = yaml.safe_load(content)
        else:
            return None, False
        normalized = json.loads(json.dumps(value, allow_nan=False, default=str))
        cleaned = sanitize(normalized)
        return cleaned, cleaned != normalized
    except (ValueError, TypeError, RecursionError, yaml.YAMLError):
        return None, False


def _file_row(path, size=0, actual=None, expected=None):
    integrity = 'missing' if actual is None else (
        ('verified' if actual == expected else 'mismatch') if expected else 'untracked')
    return dict(path=path, size=size, sha256=actual, expected_sha256=expected, integrity=integrity)


def atlas_names(root=CCS):
    """Read the atlas naming table; capsule directories stay the stable ids."""
    for base in (Path(root), CCS):
        try:
            document = json.loads((base / ATLAS_NAMES).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(document, dict) and isinstance(document.get('capsules'), dict):
            return document
    return {'kinds': {}, 'capsules': {}}


def _atlas_fields(entry):
    entry = entry if isinstance(entry, dict) else {}
    return dict(cc_title=entry.get('title'), cc_kind=entry.get('kind'), atlas_cc_id=entry.get('atlas_cc_id'),
                cc_component=entry.get('component'), cc_target=entry.get('target'),
                cc_summary=entry.get('summary'), former_names=entry.get('former_names') or [])


def _material(root, path):
    if path:
        try:
            return _read(root, path).decode('utf-8')
        except (OSError, ValueError):
            pass
    return ''


class CapsuleCatalog:
    def __init__(self, root=CCS, contracts=CONTRACTS, owner_ontology=None, prefix_fixture=None):
        self.root = Path(root).resolve()
        self.contracts = Path(contracts).resolve()
        owner = owner_ontology or os.environ.get(
            'FACTORY_OWNER_ONTOLOGY_ROOT', str(Path.home() / 'predemo-spark/inputs/ontology'))
        self.owner = Path(owner).expanduser().resolve()
        fixture = prefix_fixture or os.environ.get(
            'FACTORY_PREFIX_REUSE_FIXTURE_ROOT', Path.home() / 'muse-demo/r9/factory-fixture-c')
        self.prefix_fixture = Path(fixture).expanduser().resolve()
        self.names = atlas_names(self.root)

    def _fixture_artifact(self, key, pins):
        path = PREFIX_FIXTURE_FILES[key]
        expected = pins.get(path)
        if not SHA256.fullmatch(str(expected)):
            raise ValueError('Missing prefix reuse fixture pin')
        data = _read(self.prefix_fixture, path)
        if sha(data) != expected:
            raise ValueError('Prefix reuse fixture digest differs')
        return data

    def fixture_evidence(self):
        try:
            manifest = _json_file(self.prefix_fixture, 'manifest.json')
            pins = manifest.get('files', manifest)
            summary = json.loads(self._fixture_artifact('summary', pins))
            if summary.get('format') != 'muse-cpu-swa-fixture/1' or summary.get('status') not in {'complete', 'stopped'}:
                raise ValueError('Invalid prefix reuse fixture summary')
            model, engine = summary['model'], summary['engine']
            if (not SHA256.fullmatch(str(model['sha256'])) or not SHA256.fullmatch(str(engine['sha256']))
                    or manifest.get('model_sha256') != model['sha256']
                    or not 0 < model['bytes'] < 1_000_000_000 or not 0 < model['window_tokens']):
                raise ValueError('Invalid fixture model or engine identity')
            configurations = {}
            for key in ('stock', 'configured'):
                row = summary.get('configurations', {}).get(key)
                if row is None and summary['status'] == 'stopped':
                    continue
                path = PREFIX_FIXTURE_FILES[key]
                cached, prompt = row['cached_tokens'], row['prompt_tokens']
                cpu = row['cpu_only']
                if (type(cached) is not int or type(prompt) is not int or not 0 <= cached <= prompt
                        or prompt <= model['window_tokens'] or row['server_log'] != path
                        or row['server_log_sha256'] != pins.get(path) or cpu['cuda_visible_devices'] != '-1'
                        or cpu['requested_gpu_layers'] != 0
                        or row['cache_prompt'] is not True or row['server_closed'] is not True):
                    raise ValueError('Invalid prefix reuse fixture request evidence')
                log = self._fixture_artifact(key, pins)
                followup = row['rows'][1]
                evidence = followup['cache_evidence']
                start, end = followup['server_log_start'], followup['server_log_end']
                if not 0 <= start < end <= len(log) or type(evidence['task_id']) is not int:
                    raise ValueError('Invalid fixture follow-up log boundary')
                request_log = log[start:end].decode('utf-8', errors='replace')
                pattern = (rf'^\d+\.\d+\.\d+\.\d+ \w slot\s+operator\(\): id\s+\d+ \| task {evidence["task_id"]}'
                           r' \| cached n_tokens = (\d+), memory_seq_rm \[\d+, end\)$')
                match = re.search(pattern, request_log, re.M)
                if (not match or int(match[1]) != cached or match[0] != evidence['cache_line']
                        or evidence['prompt_tokens'] != prompt):
                    raise ValueError('Fixture token counts differ from the first follow-up cache line')
                checkpoint = re.search(rb'context checkpoints enabled, max = (\d+),', log)
                configurations[key] = dict(cached_tokens=cached, prompt_tokens=prompt, log_sha256=pins[path],
                                           cache_line=match[0], full_swa=b'using full-size SWA cache' in log,
                                           checkpoints_max=int(checkpoint[1]) if checkpoint else None)
            return sanitize(dict(
                status=summary['status'], configurations=configurations, summary_sha256=pins['summary.json'],
                model={name: model[name] for name in ('id', 'source', 'sha256', 'bytes', 'window_tokens')},
                engine={name: engine[name] for name in ('image_id', 'sha256')},
            ))
        except (OSError, TypeError, KeyError, ValueError, AttributeError, IndexError):
            return None

    def fixture_file(self, key):
        from starlette.responses import JSONResponse, PlainTextResponse

        evidence = self.fixture_evidence()
        if key not in PREFIX_FIXTURE_FILES or evidence is None:
            raise HTTPException(404, 'Prefix reuse fixture file is unavailable')
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
        if key == 'summary':
            return JSONResponse(evidence, headers=headers)
        arm = evidence['configurations'].get(key)
        if not arm:
            raise HTTPException(404, 'Prefix reuse fixture file is unavailable')
        return PlainTextResponse(f"Excerpt from digest-verified fixture log\n"
                                 f"SHA-256 {arm['log_sha256']}\n\n{arm['cache_line']}\n", headers=headers)

    def paths(self):
        paths = {path.relative_to(self.root).as_posix() for path in self.root.rglob('cc.yaml')
                 if _visible(path.relative_to(self.root).as_posix())}
        paths.update(f'{name}/cc.yaml' for name in STAR_DETAILS)
        return sorted(paths)

    def pins(self, file, *, release_key='new_release'):
        try:
            records = _json_file(self.root, file)['releases']
        except (OSError, ValueError, KeyError, TypeError):
            return {}
        if not isinstance(records, list):
            return {}
        return {row['path']: row for row in records
                if isinstance(row, dict) and isinstance(row.get('path'), str)
                and SHA256.fullmatch(str(row.get(release_key)))}

    def release_pins(self):
        pins = self.pins('migration.json') | self.pins('star-transport-migration.json')
        migrations = [row for path in sorted(self.root.glob('*-migration.json'))
                      for row in self.pins(path.name, release_key='to_release').values()]
        # Advance only through releases whose previous digest is already pinned.
        remaining = migrations[:]
        while remaining:
            pending = []
            for row in remaining:
                relative = row['path']
                from_release = row.get('from_release')
                if from_release and from_release == pins.get(relative, {}).get('new_release'):
                    pins[relative] = dict(old_release=from_release, new_release=row['to_release'])
                else:
                    pending.append(row)
            if len(pending) == len(remaining):
                break
            remaining = pending
        return pins

    @staticmethod
    def file_pins(root, manifest):
        try:
            lines = _read(root, manifest).decode('utf-8').splitlines()
        except (OSError, ValueError):
            return {}
        pins = {}
        for line in lines:
            digest, _, name = line.partition('  ')
            if SHA256.fullmatch(digest) and _visible(name):
                pins[name] = digest
        return pins

    def owner_pins(self):
        return {name: digest for name, digest in self.file_pins(self.owner, OWNER_MANIFEST).items() if '/' not in name}

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

    def retained_manifest(self, root, digest):
        """Read an inventory only when its retained release digest matches."""
        if not digest:
            return {}
        try:
            state = contained(root, '.cc-state')
            manifests = sorted(state.glob('*.manifest.json'))
            for path in manifests:
                target = contained(root, path.relative_to(root).as_posix())
                if target.is_file() and target.stat().st_size <= MAX_FILE:
                    content = target.read_bytes()
                    if sha(content) == digest:
                        return json.loads(content)
        except (OSError, ValueError):
            pass
        return {}

    def summary(self, relative, pin, *, detail=False):
        root = contained(self.root, Path(relative).parent.as_posix())
        path = root / 'cc.yaml'
        name = root.name
        star = STAR_DETAILS.get(name) if root.parent == self.root else None
        expected = pin.get('new_release')
        declaration, rows, digest, base = {}, [], None, {}
        try:
            declaration = load(_target(root, 'cc.yaml'))
            rows = tree_files(root)
            digest = sha(release_manifest_bytes(declaration, rows))
        except (OSError, ValueError, yaml.YAMLError):
            pass
        if declaration:
            try:
                base = capsule_row(path, declaration, rows)
            except (OSError, ValueError):
                pass
        retained, previous = {}, {}
        if star and expected != digest and (detail or not declaration):
            retained = self.retained_manifest(root, expected)
            if not retained:
                previous = self.retained_manifest(root, pin.get('old_release'))
        material_decl = declaration or (retained or previous).get('declaration', {})
        materials = {key: value['path'] for key, value in material_decl.get('materials', {}).items()}
        caps = material_decl.get('capabilities', {})
        expected_files = {}
        if digest is not None and digest == expected:
            expected_files = {row['path']: row['sha256'] for row in rows}
        elif retained:
            expected_files = {row['path']: row['sha256'] for row in retained['files']}
        elif declaration and previous:
            # Transport migration changes the declaration and adds a roles sidecar.
            # Authenticate the reconstructed manifest against the current release pin.
            transport = {'cc.yaml', materials.get('roles')}
            known = [row for row in previous.get('files', []) if row['path'] not in transport]
            known.extend(row for row in rows if row['path'] in transport)
            if sha(release_manifest_bytes(declaration, known)) == expected:
                expected_files = {row['path']: row['sha256'] for row in known}
        if checksum_path := materials.get('checksums'):
            expected_files = self.file_pins(root, checksum_path) | expected_files
        sections = {}
        for section, keys in SECTION_KEYS.items():
            path = next((materials[key] for key in keys if key in materials), None)
            if path:
                sections[section] = path
        component_path = materials.get('component') or next(
            (path for path in materials.values() if Path(path).name.lower() in {'component.yaml', 'component.json'}), None)
        if component_path:
            sections['component'] = component_path
        if 'verifier' not in sections and 'verify' in caps and any(row['path'] == 'run.py' for row in rows):
            sections['verifier'] = 'run.py'
        component_spec = _parse(component_path, _material(root, component_path))[0] if component_path else None
        capsule_id = material_decl.get('id', name)
        analysis_path = sections.get('analysis')
        analysis_meta = _parse(analysis_path, _material(root, analysis_path))[0] if analysis_path else None
        declared_kind = analysis_meta.get('kind') if isinstance(analysis_meta, dict) else None
        title = analysis_meta.get('title') if isinstance(analysis_meta, dict) else None
        analysis_cap = ('analyze' if declared_kind == 'analysis' and 'analyze' in caps
                        else ANALYSIS_CAPABILITIES.get(capsule_id))
        if star or (isinstance(component_spec, dict) and component_spec.get('kind') == 'builder_spec'):
            kind = 'builder'
        else:
            kind = 'analysis' if declared_kind == 'analysis' or analysis_cap in caps else 'factory-support'
        overview = _material(root, sections.get('guide') if star else sections.get('guide') or sections.get('method'))
        intro = next((text.strip() for text in overview.split('\n\n')
                      if text.strip() and not text.lstrip().startswith(('#', '```', '|'))), '')
        description = caps.get(analysis_cap, {}).get('does') or ' '.join(intro.split()) or next(
            (cap['does'] for cap in caps.values()), '')
        integrity = ('verified' if expected == digest else 'mismatch') if expected else (
            'untracked' if digest else 'missing')
        summary = dict(name=name, id=capsule_id,
                       version=declaration.get('version', 'unknown'), starred=bool(star),
                       kind=kind, title=title if isinstance(title, str) else None, component=star[0] if star else None,
                       subcomponent=star[1] if star else None, description=description,
                       strata_mechanism=star[2] if star else None, arm=STAR_ARMS.get(capsule_id) if star else None,
                       binding=base.get('binding', 'unavailable'), capabilities=base.get('capabilities', list(caps)),
                       contract_id=CONTRACT_ID if star else None,
                       digest=digest, expected_digest=expected, integrity=integrity,
                       **_atlas_fields(self.names['capsules'].get(Path(relative).parent.as_posix())))
        if detail:
            indexed = {row['path']: row for row in rows if _visible(row['path'])}
            files = [_file_row(name, indexed[name]['size'], indexed[name]['sha256'], expected_files.get(name))
                     if name in indexed else _file_row(name, expected=expected_files[name])
                     for name in sorted(set(indexed) | {name for name in expected_files if _visible(name)})]
            ontology_path = sections.get('ontology')
            ontology = _parse(ontology_path, _material(root, ontology_path))[0] if ontology_path else None
            summary.update(materials=materials, sections=sections, ontology=ontology,
                           component_spec=component_spec, verifier=caps.get('verify', {}).get('does'),
                           capability_descriptions={name: cap['does'] for name, cap in caps.items()},
                           contract_clauses=[row[0] for row in CONTRACT_CLAUSES] if star else [],
                           files=files)
        return summary

    def listing(self):
        pins = self.release_pins()
        capsules = []
        for relative in self.paths():
            try:
                capsules.append(self.summary(relative, pins.get(relative, {})))
            except (OSError, ValueError):
                continue
        owner_pins = self.owner_pins()
        owner = [self.external_row(self.owner, name, 'owner-ontology', owner_pins.get(name))
                 for name in [OWNER_MANIFEST, *owner_pins] if owner_pins]
        return sanitize(dict(capsules=capsules, contract=self.contract(), owner_ontology=owner,
                             kinds=self.names.get('kinds', {})))

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
        return sanitize(self._detail(self.resolve(name)))

    def _detail(self, relative):
        pins = self.release_pins()
        try:
            return self.summary(relative, pins.get(relative, {}), detail=True)
        except ValueError:
            raise HTTPException(404, 'Capsule not found') from None

    def file(self, name, path):
        definition = self.resolve(name)
        detail = self._detail(definition)
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
            root = (self.root / definition).parent
            relative, expected = path, files[path]['expected_sha256']
        try:
            data = _read(root, relative)
        except (OSError, ValueError):
            raise HTTPException(404, 'Capsule file is unavailable') from None
        content = scrub_bytes(data).decode('utf-8', errors='replace')
        parsed, changed = _parse(relative, data.decode('utf-8', errors='replace'))
        if changed:
            # Keep the raw tab usable when redaction changes a structured value.
            content = (json.dumps(parsed, ensure_ascii=False, indent=2) if relative.endswith('.json')
                       else yaml.safe_dump(parsed, allow_unicode=True, sort_keys=False))
        return sanitize(dict(_file_row(path, len(data), sha(data), expected),
                             content=content, parsed=parsed, truncated=False))
