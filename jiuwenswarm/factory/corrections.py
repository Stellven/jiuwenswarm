"""Project correction trails from native checks, operator notes and cited evidence."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

_UNSUCCESSFUL = {'fail', 'failed', 'error', 'blocked', 'refused'}
_ADMINISTRATIVE = ('Operator release on plan node ', 'Operator hold on plan node ', 'Operator reopen on plan node ',
                   'Operator revise of the task graph ', 'The operator paused this run and resumed it:')


def read_notes(directory, task_id):
    """Read the native append-only inbox and keep the original note identities."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        return []
    result = []
    for path in directory.glob('*.json'):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
                continue
            note = json.loads(path.read_bytes())
            if (isinstance(note, dict) and note.get('task_id') == task_id and note.get('note_id') == path.stem
                    and isinstance(note.get('text'), str) and isinstance(note.get('created'), (int, float))):
                result.append(note)
        except (OSError, ValueError):
            continue
    return sorted(result, key=lambda n: (n['created'], n['note_id']))


def _assessment(row):
    check = row['values']
    review, verifier = check.get('review') or {}, check.get('verifier') or {}
    return dict(host_passed=check.get('passed'), verifier_passed=verifier.get('passed'),
                reviewer_verdict=review.get('verdict'), verifier_stage=verifier.get('stage_reached'),
                advisory=review.get('advisory') is True or (check.get('entry') or {}).get('review') == 'advisory')


def _check_findings(row):
    value = row['values']
    review, verifier = value.get('review') or {}, value.get('verifier') or {}
    assessment = _assessment(row)
    subject = dict(source=row['obs_id'], check_id=row['obs_id'], created=row.get('created') or 0,
                   node_id=value['node_id'], output=value.get('output', 'change'))
    common = subject | assessment | dict(kind='finding', status='open')
    reported = review.get('findings') or []
    for index, finding in enumerate(reported, 1):
        if not isinstance(finding, dict):
            continue
        yield common | dict(id=f"{row['obs_id']}#reviewer-{index}", actor='reviewer',
                            text=finding.get('problem') or '', severity=finding.get('severity'),
                            file=finding.get('file'), line=finding.get('line'), reviewer=review.get('reviewer'),
                            verdict=review.get('verdict'), raw=finding,
                            evidence_ids=row.get('source_artifacts') or [])
    if not reported and review.get('verdict') in _UNSUCCESSFUL:
        yield common | dict(id=f"{row['obs_id']}#reviewer-failure", actor='reviewer', verdict=review['verdict'],
                            text=review.get('summary') or review.get('reason') or 'The independent review failed.',
                            reviewer=review.get('reviewer'), evidence_ids=row.get('source_artifacts') or [])
    for index, finding in enumerate(verifier.get('checks') or [], 1):
        if isinstance(finding, dict) and finding.get('status') in _UNSUCCESSFUL:
            name = finding.get('name') or 'Verifier check'
            yield common | dict(id=f"{row['obs_id']}#verifier-{index}", actor='verifier', advisory=False,
                                text=f"{name}: {finding['detail']}" if finding.get('detail') else name,
                                severity='blocker', verdict=finding.get('status'), raw=finding)
    if (value.get('passed') is False and not any(
            c.get('status') in _UNSUCCESSFUL for c in verifier.get('checks') or [] if isinstance(c, dict))
            and not (review.get('verdict') in _UNSUCCESSFUL and not assessment['advisory'])):
        actor = 'verifier' if verifier.get('passed') is False else 'host'
        yield common | dict(id=f"{row['obs_id']}#{actor}-failure", actor=actor, advisory=False, severity='blocker',
                            verdict='failed', text=value.get('reason') or 'Output check failed.')


def _refs(row):
    refs = row['values'].get('refs') or {}
    return set((refs.get('evidence_ids') or []) + (refs.get('artifact_ids') or []))


def _contains_id(text, key):
    return bool(re.search(r'(?<![\w:#-])' + re.escape(key) + r'(?![\w:#-])', text))


def _review_confirms(passing):
    review = passing['values'].get('review') or {}
    return str(review.get('summary') or '').casefold() if review.get('verdict') == 'pass' else ''


def _repair_proofs(finding, failed, passing, indexed):
    """Require cited changed evidence and specific proof for each addressed finding."""
    earlier, later = _refs(failed), _refs(passing)
    confirmed = _review_confirms(passing)
    text = finding['text'].casefold()
    for aid in sorted(later - earlier):
        evidence = indexed.get(aid)
        if not evidence or not (finding['created'] < evidence['created'] <= passing['created']):
            continue
        v = evidence['values']
        if v.get('node_id') != finding['node_id']:
            continue
        if (finding['id'] in (v.get('addresses_findings') or [])
                and (finding['actor'] != 'reviewer' or (passing['values'].get('review') or {}).get('verdict') == 'pass')):
            yield evidence, v.get('summary') or v.get('message') or f"Recorded correction for {finding['output']}.", None
        elif finding['actor'] == 'reviewer' and evidence['kind'] == 'requant_recipe_production_provenance' and (
                v.get('supersedes_ambiguity_in') == failed['obs_id'] and confirmed):
            producer = str((v.get('production_quantizer') or {}).get('commit') or '')[:8]
            stock = str((v.get('recipe_engine_revision') or {}).get('revision') or '')[:8]
            raw = str(v.get('operator_receipt_raw_sha256') or '')[:8]
            canonical = str(v.get('registry_receipt_canonical_sha256') or '')[:8]
            if producer and stock and producer in text and stock in text and producer in confirmed:
                yield evidence, (f'Linked the original quantizer build at {producer} and kept {stock} as the stock '
                                 'recipe reference.'), ('producer_commit', producer)
            elif raw and canonical and raw in text and canonical in text and v.get('canonicalization'):
                yield evidence, (f'Recorded the raw receipt digest {raw} and the replay registry digest {canonical}. '
                                 f"{v['canonicalization']}"), ('receipt', 'sorted compact json', 'stored bytes')
        elif finding['actor'] == 'reviewer' and evidence['kind'] == 'nvfp4_pack_handoff' and (
                v.get('verified_pack_observation') in earlier and v.get('original_manifest_sha256')
                and (v.get('manifest') or {}).get('census_by_type') and 'census_by_type' in text and 'census' in confirmed):
            yield evidence, ('Recorded a separate handoff manifest with a tensor census and retained the pinned '
                             'production manifest digest.'), ('handoff manifest', 'census_by_type', 'immutable')
        elif finding['actor'] == 'reviewer' and evidence['kind'] == 'ingest_nvfp4_converter_runtime_evidence' and (
                'converter diff' in text and 'runtime-acceptance' in text and 'tiny runtime checks' in confirmed):
            converter = indexed.get(v.get('converter_check_id'), {}).get('values') or {}
            if (converter.get('node_id') == finding['node_id'] and converter.get('passed') is True
                    and converter.get('diff_sha256') == v.get('diff_sha256') and v.get('accepted_diff_artifact_id')):
                yield evidence, 'Cited the checked converter diff and its passing tiny runtime acceptance in the pack output.', None
        elif finding['actor'] == 'reviewer' and evidence['kind'] == 'cold_smoke_generated_row' and (
                v.get('capped_run_id') in earlier and v.get('generated_text') and v.get('rows_artifact_sha256')
                and 'generated response' in text and 'intelligible' in confirmed):
            yield evidence, 'Attached the recorded generated response and its coherence assessment from the existing capped run.', None
    # This repair has an independently reviewed replacement patch. Require the
    # changed patch digest and specific confirmation of the formerly missing measurement.
    if finding['actor'] == 'reviewer' and failed['values'].get('kind') == 'diff' and (
            failed['values'].get('diff_sha256') and passing['values'].get('diff_sha256')
            and failed['values']['diff_sha256'] != passing['values']['diff_sha256']
            and ('timer' in text or 'timing probe' in text) and 'write time' in text
            and 'times one expert' in confirmed and 'write time' in confirmed):
        patch = next((a for a in passing.get('source_artifacts') or [] if a.endswith(('-diff', '.diff'))), None)
        if patch:
            yield dict(obs_id=patch, created=passing.get('created') or 0), (
                'Recorded a replacement converter patch. The reviewer confirmed the one-expert projection includes '
                'estimated write time.'), None


def _notes_for(notes, finding, until, identifying_terms):
    for note in notes:
        text = note['text']
        if not finding['created'] < note['created'] <= until or text.startswith(_ADMINISTRATIVE):
            continue
        if (_contains_id(text, finding['id']) or (identifying_terms and all(term in text.casefold() for term in identifying_terms))):
            yield note


def project(data):
    """Return per-node counts and timeline. An unrelated or unchanged pass never resolves a finding."""
    tid = data['tasks'][0]['task_id']
    rows = [r for r in data.get('observations', []) if r.get('task_id', tid) == tid]
    indexed = {r['obs_id']: r for r in rows}
    notes = data.get('_operator_notes', [])
    timeline = {}
    checks = [r for r in rows if r['kind'] == 'node_check' and r['values'].get('node_id') and r['values'].get('state') == 'finished']
    checks.sort(key=lambda r: r.get('created') or 0)
    passes = {}
    findings = []
    for row in checks:
        v = row['values']
        key = (v['node_id'], v.get('output', 'change'))
        if v.get('reused_from') not in indexed:
            findings.extend(_check_findings(row))
        if not v.get('reused_from') and v.get('passed') is True and _assessment(row)['verifier_passed'] is not False:
            passes.setdefault(key, []).append(row)
    for row in rows:
        values = row['values']
        if row['kind'] == 'node_contract_refusal' and values.get('node_id'):
            for index, problem in enumerate(values.get('problems') or [], 1):
                findings.append(dict(id=f"{row['obs_id']}#scheduler-{index}", source=row['obs_id'], check_id=row['obs_id'],
                                     node_id=values['node_id'], kind='finding', created=row.get('created') or 0,
                                     actor='scheduler', by=values.get('by'), advisory=False, severity='blocker',
                                     status='open', verdict='refused', text=problem))

    repairs, note_rows, verified = {}, {}, {}
    findings_by_check = Counter(f['check_id'] for f in findings)
    for finding in findings:
        node, check_id = finding['node_id'], finding['check_id']
        timeline.setdefault(node, []).append(finding)
        for note in notes:
            text = note['text']
            if note['created'] <= finding['created'] or text.startswith(_ADMINISTRATIVE):
                continue
            if _contains_id(text, finding['id']) or _contains_id(text, check_id):
                linked = _contains_id(text, finding['id']) or findings_by_check[check_id] == 1
                _add_note(note_rows, note, finding, linked, 'finding_id' if _contains_id(text, finding['id']) else 'check_id')
        for passing in passes.get((node, finding.get('output')), []):
            if passing['created'] <= finding['created']:
                continue
            for evidence, explanation, anchors in _repair_proofs(finding, indexed[check_id], passing, indexed):
                matched = list(_notes_for(notes, finding, evidence['created'], anchors))
                matched.extend(n for n in notes if n['created'] <= evidence['created'] and (
                    finding['id'] in note_rows.get((node, n['note_id']), {}).get('finding_ids', [])))
                for note in matched:
                    _add_note(note_rows, note, finding, True, 'matching_repair_evidence')
                key = (node, evidence['obs_id'], passing['obs_id'])
                row = repairs.setdefault(key, dict(id=f"{evidence['obs_id']}#repair-{passing['obs_id']}", kind='repair', actor='worker',
                    created=evidence['created'], node_id=node, output=finding.get('output'), source=evidence['obs_id'],
                    check_id=check_id, passing_check_id=passing['obs_id'], finding_ids=[], note_ids=[], evidence_ids=[evidence['obs_id']],
                    text=''))
                if explanation not in row['text']:
                    row['text'] = ' '.join(filter(None, (row['text'], explanation)))
                row['finding_ids'].append(finding['id'])
                row['note_ids'] = sorted(set(row['note_ids']) | {n['note_id'] for n in matched})
                verified.setdefault(passing['obs_id'], []).append(finding['id'])
                finding.update(status='verified_repair', repair_id=row['id'], passing_check_id=passing['obs_id'])
                break
            if finding['status'] == 'verified_repair':
                break
    for event in [*note_rows.values(), *repairs.values()]:
        timeline.setdefault(event['node_id'], []).append(event)
    for (node, output), records in passes.items():
        for check in records:
            check_id = check['obs_id']
            assessment = _assessment(check)
            label = 'Host and capsule verifier passed.' if assessment['verifier_passed'] else 'Host output check passed.'
            if assessment['verifier_stage']:
                label += f" Stage: {assessment['verifier_stage']}."
            if assessment['reviewer_verdict']:
                mode = 'Advisory' if assessment['advisory'] else 'Blocking'
                label += f" {mode} reviewer verdict: {assessment['reviewer_verdict']}."
            timeline.setdefault(node, []).append(assessment | dict(id=check_id + '#pass', source=check_id,
                created=check.get('created') or 0, kind='passing_check', actor='host', check_id=check_id,
                node_id=node, output=output, text=label, finding_ids=verified.get(check_id, []),
                evidence_ids=check.get('source_artifacts') or []))
    order = {'finding': 0, 'note': 1, 'repair': 2, 'passing_check': 3}
    return {node: dict(counts={kind + 's': sum(r['kind'] == kind for r in events) for kind in ('finding', 'note', 'repair')},
                       events=sorted(events, key=lambda r: (r['created'], order[r['kind']], r['id'])))
            for node, events in timeline.items()}


def _add_note(note_rows, note, finding, linked, basis):
    source = note['note_id']
    row = note_rows.setdefault((finding['node_id'], source), dict(id=source, kind='note', actor='operator', source=source,
        by=note.get('by'), text=note['text'], created=note['created'], node_id=finding['node_id'], output=finding.get('output'),
        check_id=finding['check_id'], finding_ids=[], link_basis=basis))
    if linked and finding['id'] not in row['finding_ids']:
        row['finding_ids'].append(finding['id'])
