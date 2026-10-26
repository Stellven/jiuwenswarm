"""Readable exact contract inventory for an already authorized run export."""
import json
from .state import json_bytes
from .metric_contract import PROTOCOL_FILE, PROTOCOL_SCHEMA


KINDS = {'research-brief', 'run-plan', 'node-execution-contract',
         'subnode-execution-contract', 'bound-check-plan', 'metric-protocol', 'run-model-selection',
         'automatic-route-decision', 'node-routing-budget'}


def contract_export_files(store, run, records, audience, restricted):
    """Called only after account/workspace authorization and audience resolution."""
    originals = {}; accepted = set()
    for row in records:
        value = row['record']
        if row['kind'] in KINDS:
            originals[row['ref']['sha256']] = (row['kind'], row['ref'], value)
        if row['kind'] == PROTOCOL_SCHEMA:
            originals[row['ref']['sha256']] = ('metric-protocol', row['ref'], value)
        if row['kind'] == 'run-model-selection' and value.get('deployment_ref'):
            ref=value['deployment_ref']
            deployment=store.read_record(ref)
            originals[ref['sha256']]=('manual-model-deployment',ref,deployment)
            endpoint_ref=deployment['endpoint_ref']
            originals[endpoint_ref['sha256']]=('manual-model-endpoint',endpoint_ref,store.read_record(endpoint_ref))
        if row['kind'] == 'run-model-selection' and value.get('mode') == 'automatic':
            for candidate in value['candidates']:
                ref = candidate['deployment_ref']
                deployment = store.read_record(ref)
                originals[ref['sha256']] = ('routing-model-deployment', ref, deployment)
                endpoint = deployment['endpoint_ref']
                originals[endpoint['sha256']] = ('routing-model-endpoint', endpoint, store.read_record(endpoint))
        if row['kind'] == 'subnode-execution-contract':
            for binding in value['bindings']:
                declaration = store.read_record(binding['declaration_ref'], contract_id='capsule-declaration')
                for item in declaration['identity']['body']:
                    if item['path'] != PROTOCOL_FILE:
                        continue
                    # Only a body Ref pinned into this owned execution is eligible.
                    # Never substitute the currently installed registry for old runs.
                    refs = [ref for ref in binding['implementation_refs'] if ref['sha256'] == item['sha256']]
                    if len(refs) != 1:
                        continue
                    ref = refs[0]
                    protocol = store.read_record(ref, contract_id=PROTOCOL_SCHEMA)
                    originals[ref['sha256']] = ('metric-protocol', ref, protocol)
        if row['kind'] == 'gate-decision':
            accepted.update(ref['sha256'] for ref in value['accepted_refs'])
        if row['kind'] == 'invocation-observation':
            for ref in value['output_refs']:
                # This is an existing candidate output already in the owned run
                # export closure, never a source-ref or arbitrary blob lookup.
                # Validate byte custody first. Non-JSON reports and ZIP outputs
                # are ordinary artifacts, while missing/substituted blobs must
                # still fail export rather than becoming an ignored parse error.
                raw = store.read_blob(ref)
                try:output = json.loads(raw)
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
