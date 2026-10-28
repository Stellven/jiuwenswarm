"""Offline, exact-byte comparison against a product originals.zip export."""
from __future__ import annotations

import argparse
import asyncio
import difflib
import hashlib
import json
from pathlib import Path
import re
import zipfile

from . import harness
from .harness import Harness, ScriptedModel, Context
from jiuwenswarm.research.state import json_bytes
from jiuwenswarm.research.gate import SemanticVerifier


class Export:
    def __init__(self, path):
        path = Path(path)
        self.readable = path if path.is_dir() else path.parent / 'readable'
        archive = path if path.suffix == '.zip' else path.parent / 'originals.zip'
        if not archive.exists() and path.is_dir():
            archive = path / 'originals.zip'
        self.archive = zipfile.ZipFile(archive)
        self.names = self.archive.namelist()
        self.by_hash = {}
        self.embedded = {}
        self.missing_refs = {}
        for name in self.names:
            if name.endswith('/'):
                continue
            raw = self.archive.read(name)
            self.by_hash.setdefault(hashlib.sha256(raw).hexdigest(), []).append(name)
            match = re.search(r'([0-9a-f]{64})(?:\.[^/]*)?$', name)
            if match:
                self.by_hash.setdefault(match[1], []).append(name)
            if name.endswith('/prompt.txt'):
                text = raw.decode('utf-8')
                if '<subject_payload>\n' in text:
                    payload = text.split('<subject_payload>\n', 1)[1].rsplit('\n</subject_payload>', 1)[0]
                    self._embedded_values(json.loads(payload))

    def _embedded_values(self, value):
        if isinstance(value, (dict, list)):
            raw = json_bytes(value)
            self.embedded[hashlib.sha256(raw).hexdigest()] = raw
            children = value.values() if isinstance(value, dict) else value
            for child in children:
                self._embedded_values(child)
        elif isinstance(value, str):
            raw = value.encode('utf-8')
            self.embedded[hashlib.sha256(raw).hexdigest()] = raw

    def close(self):
        self.archive.close()

    def read_ref(self, ref):
        for name in self.by_hash.get(ref['sha256'], []):
            raw = self.archive.read(name)
            if hashlib.sha256(raw).hexdigest() == ref['sha256']:
                return raw
        if ref['sha256'] in self.embedded:
            return self.embedded[ref['sha256']]
        raise ValueError('Export has no exact bytes for ' + repr(ref))

    def records(self, prefix):
        for name in self.names:
            if name.startswith(prefix) and name.endswith('.json'):
                yield name, json.loads(self.archive.read(name))

    def import_ref(self, harness, ref, seen=None):
        seen = set() if seen is None else seen
        key = (ref['id'], ref['sha256'])
        if key in seen:
            return
        seen.add(key)
        raw = self.read_ref(ref)
        if harness.capture(raw, record_id=ref['id']) != ref:
            raise ValueError('Capture changed export identity')
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            return
        def walk(v):
            if isinstance(v, dict):
                if set(v) == {'id', 'sha256'}:
                    # Some unrelated historical references are deliberately absent
                    # from an export. Required reads still fail through SQLite.
                    try:
                        self.import_ref(harness, v, seen)
                    except ValueError:
                        self.missing_refs[(v['id'], v['sha256'])] = v
                else:
                    for child in v.values():
                        walk(child)
            elif isinstance(v, list):
                for child in v:
                    walk(child)
        walk(value)


def compare_bytes(expected, actual):
    equal = expected == actual
    first = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))
    diff = [] if equal else list(difflib.unified_diff(
        expected.decode('utf-8', errors='replace').splitlines(),
        actual.decode('utf-8', errors='replace').splitlines(), fromfile='product', tofile='cclib', lineterm=''))
    return dict(equal=equal, product_sha256=hashlib.sha256(expected).hexdigest(),
                harness_sha256=hashlib.sha256(actual).hexdigest(), product_bytes=len(expected), harness_bytes=len(actual),
                first_differing_byte=None if equal else first, diff_summary='\n'.join(line[:1200] for line in diff[:20]))


async def compare_export(path):
    export = Export(path)
    report = {'label': 'offline CC logic, prompts reconstructed', 'prompts': [], 'stages': []}
    try:
        contracts = [v for _, v in export.records('contracts/subnode-execution-contract-')]
        assessments = [v for _, v in export.records('evidence/verifier-assessment-')]
        gates = [v for _, v in export.records('evidence/gate-decision-')]
        for contract in contracts:
            declaration = json.loads(export.read_ref(contract['bindings'][0]['declaration_ref']))
            cc = declaration['identity']['name']
            if cc not in ('intent.compiler', 'requirements.compiler'):
                continue
            stage = 'intent' if cc == 'intent.compiler' else 'requirements'
            h = Harness()
            try:
                inrefs = {p['name']: p['artifact_refs'][0] for p in contract['inputs']}
                export.missing_refs.clear()
                for ref in inrefs.values():
                    export.import_ref(h, ref)
                inputs = {p: json.loads(export.read_ref(ref)) for p, ref in inrefs.items()}
                related = [v for v in contracts if v['bindings'][0]['role'] == 'verifier'
                           and any(p['name'] == 'subject_declaration' and p['artifact_refs'] == [contract['bindings'][0]['declaration_ref']]
                                   for p in v['inputs'])]
                if len(related) != 1:
                    raise ValueError('Expected exactly one matching compiler verifier contract')
                output_ref = next(p['artifact_refs'][0] for p in related[0]['inputs'] if p['name'] == 'subject_output')
                assessment = next(v for v in assessments if v['subject_ref'] == output_ref)
                reply = {k: assessment[k] for k in ('uncertainties', 'limitations', 'required_correction')}
                reply['findings'] = [{k: f[k] for k in ('criterion_id', 'outcome', 'reason')} for f in assessment['findings']]
                result = await h.run_stage(stage, inputs, model=ScriptedModel([export.read_ref(output_ref).decode('utf-8'), reply]), input_refs=inrefs)
                independent_verifier = []
                if not any(p['role'].startswith('verifier:') for p in result['prompts']):
                    # Compare the actual current verifier on the captured product
                    # output even when absent source bytes prevent work eligibility.
                    # This is prompt-only replay and grants no advancing decision.
                    export.import_ref(h, output_ref)
                    rref = assessment['review_context_ref']
                    h.capture(export.read_ref(rref), record_id=rref['id'])
                    asset = await h.assets(stage)
                    ctx = Context(h.store, contract, ScriptedModel([reply]), independent_verifier, [])
                    ctx.role = 'verifier:captured_product_output'
                    await SemanticVerifier(h.store).review(asset['declaration_ref'], output_ref, asset['profile_ref'],
                                                           rref, 'intent' if stage == 'intent' else 'brief', ctx.model)
                expected_gates = [g for g in gates if g['scope_kind'] == 'subnode' and g['subnode_id'] == contract['subnode_id']]
                expected = [g['action'] for g in expected_gates]
                observed = [g['action'] for g in result['gate_decisions']]
                missing_output_refs = {}
                def missing_in_output(value):
                    if isinstance(value, dict):
                        if set(value) == {'id', 'sha256'}:
                            try:
                                export.read_ref(value)
                            except ValueError:
                                missing_output_refs[value['id']] = value
                        else:
                            for child in value.values():
                                missing_in_output(child)
                    elif isinstance(value, list):
                        for child in value:
                            missing_in_output(child)
                missing_in_output(json.loads(export.read_ref(output_ref)))
                report['stages'].append(dict(stage=stage, status=result['status'], reasons=result['reasons'],
                    missing_output_refs=list(missing_output_refs.values()),
                    missing_export_refs=list(export.missing_refs.values()),
                    product_gate_actions=expected, harness_gate_actions=observed, gate_equal=bool(expected) and expected == observed))
                for subnode, role in ((contract['subnode_id'], 'worker'), (related[0]['subnode_id'], 'verifier:')):
                    candidates = [n for n in export.names if n.endswith('/' + subnode + '/prompt.txt')]
                    actuals = [p for p in [*result['prompts'], *independent_verifier] if p['role'] == role or role == 'verifier:' and p['role'].startswith(role)]
                    if len(candidates) != 1 or len(actuals) != 1:
                        report['prompts'].append(dict(stage=stage, role=role, equal=False,
                            reason='Missing or ambiguous original/reconstructed prompt', originals=candidates, captured=len(actuals)))
                        continue
                    name = candidates[0]
                    comparison = compare_bytes(export.archive.read(name), actuals[0]['text'].encode('utf-8'))
                    comparison.update(stage=stage, role=role, original=name)
                    comparison['replay_mode'] = 'captured product output; gate eligibility not granted' if independent_verifier and role == 'verifier:' else 'full harness stage'
                    if not comparison['equal']:
                        comparison['reason'] = ('Current source assets, schema serialization, declaration port ordering or release differs; '
                            'see exact first byte and unified diff. No identity or text normalization applied.')
                    # Readable projections are compared separately, never used as originals.
                    mirrors = []
                    if export.readable.is_dir():
                        original_hash = comparison['product_sha256']
                        for candidate in export.readable.glob('*.txt'):
                            if hashlib.sha256(candidate.read_bytes()).hexdigest() == original_hash:
                                mirrors.append(candidate.name)
                    comparison['byte_identical_readable_files'] = mirrors
                    report['prompts'].append(comparison)
            except Exception as exc:
                report['stages'].append(dict(stage=stage, error=str(exc), gate_equal=False))
            finally:
                h.close()
        report['all_equal'] = len(report['prompts']) >= 4 and all(p['equal'] for p in report['prompts'])
        report['all_gates_equal'] = bool(report['stages']) and all(s['gate_equal'] for s in report['stages'])
        if report['all_equal']:
            report['label'] = 'offline CC logic; compiler prompt byte equality verified for this export only'
        return report
    finally:
        export.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path, help='readable directory, artifacts directory, or originals.zip')
    parser.add_argument('--out', type=Path, required=True, help='directory for prompt-comparison.json and scratch stores')
    args = parser.parse_args()
    harness.SCRATCH_ROOT = args.out / '.scratch'
    comparison = asyncio.run(compare_export(args.export))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'prompt-comparison.json').write_bytes((json.dumps(comparison, ensure_ascii=False, indent=2) + chr(10)).encode('utf-8'))
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
