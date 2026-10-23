"""Readable exact contract inventory for an already authorized run export."""
from .state import json_bytes


KINDS = {'research-brief', 'run-plan', 'node-execution-contract',
         'subnode-execution-contract', 'bound-check-plan'}


def contract_export_files(store, run, records, audience, restricted):
    """Called only after account/workspace authorization and audience resolution."""
    originals = {}; accepted = set()
    for row in records:
        value = row['record']
        if row['kind'] in KINDS:
            originals[row['ref']['sha256']] = (row['kind'], row['ref'], value)
        if row['kind'] == 'gate-decision':
            accepted.update(ref['sha256'] for ref in value['accepted_refs'])
        if row['kind'] == 'invocation-observation':
            for ref in value['output_refs']:
                # This is an existing candidate output already in the owned run
                # export closure, never a source-ref or arbitrary blob lookup.
                try:output = store.read_record(ref)
                except (ValueError, UnicodeError):continue
                if isinstance(output, dict) and output.get('domain_lane') == 'scientific_research' and 'target_metrics' in output:
                    originals[ref['sha256']] = ('research-brief', ref, output)
    files = []; entries = []; withheld = set()
    for digest, (kind, ref, value) in sorted(originals.items()):
        if restricted.get((ref['id'], ref['sha256']), audience) != audience:
            withheld.add(kind)
            continue
        path = 'contracts/' + kind + '-' + digest + '.json'
        files.append({'path': path, 'artifact_ref': ref, 'media_type': 'application/json', 'audience': audience})
        entries.append({'kind': kind, 'path': path, 'artifact_ref': ref,
                        'schema_version': value.get('schema_version'),
                        'node_id': value.get('node_id'), 'subnode_id': value.get('subnode_id'),
                        'accepted': digest in accepted if kind == 'research-brief' else None})
    present = {entry['kind'] for entry in entries}
    index = {'schema_version': 'run-contract-export:1', 'run_id': run['id'],
             'run_state': run['state'], 'contracts': entries,
             'missing': [{'kind': kind, 'reason': 'withheld_for_audience' if kind in withheld else 'not_created_at_this_run_stage'}
                         for kind in sorted(KINDS - present)],
             'note': 'Exact original bytes and hashes; candidates are not accepted contracts. An absent plan is never fabricated.'}
    ref = store.put_blob(json_bytes(index), media_type='application/json')
    files.append({'path': 'contracts/index.json', 'artifact_ref': ref,
                  'media_type': 'application/json', 'audience': audience})
    return files
