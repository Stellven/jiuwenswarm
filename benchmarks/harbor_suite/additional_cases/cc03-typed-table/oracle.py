"""Independent stdlib E3 checks. Parent normalizer owns original export custody."""
import json


class MissingEvidence(Exception):
    pass


def equal(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def evaluate_content(output, variant, outputref=None):
    """Shared content check usable without any CC-specific binding penalty."""
    expected = variant['expected_table']
    valid = isinstance(output, dict) and equal(output.get('data', {}).get('table'), expected)
    return {'checks': [{'id': 'deterministic-content', 'status': 'pass' if valid else 'fail',
                        'reason': 'Exact scalar values, types and ordered table projection',
                        'evidence_refs': [outputref] if outputref else []}],
            'metrics': {'deterministic_content_success': int(valid)}}


def evaluate(evidence, criteria):
    checks = []
    metrics = {'binding_success': None, 'deterministic_content_success': None,
               'productive_completion': None, 'expected_behavior_met': None}
    def check(name, status, reason):
        checks.append({'id': name, 'status': status, 'reason': reason, 'evidence_refs': []})
    def require(ok, reason):
        if not ok:
            raise ValueError(reason)
    def get(kind, ref=None):
        rows = [r for r in evidence.get('records', []) if r.get('kind') == kind
                and (ref is None or r.get('ref') == ref)]
        if not rows:
            raise MissingEvidence('Missing original ' + kind)
        require(len(rows) == 1, 'Ambiguous original ' + kind)
        return rows[0]['record'], rows[0]['ref']
    try:
        variant = criteria['variants'][evidence['variant_id']]
        require(evidence['entrypoint'] == 'single_cc' and evidence['execution']['launched'] is True
                and evidence['execution']['terminal'] is True, 'Actual terminal E3 execution required')
        request, _ = get('request')
        require(request['entry_point'] == 'E3', 'Only E3 establishes capsule execution')
        source, source_ref = get('source_contract')
        binding = source['bindings'][0]
        declared, declaration_ref = get('source_declaration', binding['declaration_ref'])
        admitted, admission_ref = get('source_admission', binding['admission_ref'])
        expected = variant['binding']
        require(len(source['bindings']) == 1 and declaration_ref == expected['declaration_ref']
                and declared['identity']['name'] == expected['name']
                and declared['identity']['version_label'] == expected['version']
                and binding['implementation_refs'] == expected['implementation_refs'], 'Exact capsule pins differ')
        require(admitted['status'] == 'admitted' and admitted['candidate_ref'] == declaration_ref,
                'Original admission differs')
        normalized, _ = get('normalized_request', request['normalized_request_ref'])
        require((normalized['capsule_id'], normalized['capsule_version'], normalized['capsule_declaration_sha256']) ==
                (expected['name'], expected['version'], declaration_ref['sha256']), 'Request targets another capsule')
        ports = {p['name']: p['artifact_refs'][0] for p in source['inputs'] if len(p['artifact_refs']) == 1}
        require(ports == variant['input_refs'] and len(ports) == len(source['inputs']), 'Frozen input pins differ')
        measured, _ = get('measurement')
        actual, actual_ref = get('actual_contract', measured['contract_ref'])
        observed, _ = get('observation', measured['observation_ref'])
        require(actual['source_subject_ref'] == source_ref and actual['role'] == 'worker', 'Wrong actual source lineage')
        require(actual['bindings'][0]['declaration_ref'] == declaration_ref
                and actual['bindings'][0]['admission_ref'] == admission_ref
                and actual['bindings'][0]['implementation_refs'] == binding['implementation_refs']
                and actual['bindings'][0]['effective_authority'] == binding['effective_authority'], 'Actual binding changed')
        require(observed['contract_ref'] == actual_ref and observed['observed_runtime'] is True,
                'Original runtime observation required')
        require(all(observed[k] == actual[k] for k in ('run_id', 'node_id', 'subnode_id', 'attempt_id')),
                'Invocation identity differs')
        require(observed['input_refs'] == actual['input_refs'] == source['input_refs'], 'Observed inputs changed')
        check('binding-and-provenance', 'pass', 'Original E3 source, declaration, admission and invocation join')
        metrics['binding_success'] = 1
        if variant['expected_behavior'] == 'halt':
            require(measured['status'] == 'failed' and measured.get('failure') == 'table_input'
                    and not measured['output_refs'], 'Expected malformed-table worker refusal was not observed')
            metrics.update(expected_behavior_met=1, productive_completion=0)
            check('expected-refusal', 'pass', 'Known malformed source refused without producing output')
        else:
            require(measured['status'] == 'completed' and measured['accepted'] is False,
                    'Private E3 worker did not complete')
            ref = measured['output_refs']['result']
            require(ref in observed['output_refs'], 'Measured output absent from original invocation')
            output, _ = get('output', ref)
            content = evaluate_content(output, variant, ref)
            checks.extend(content['checks']); metrics.update(content['metrics'])
            metrics['productive_completion'] = content['metrics']['deterministic_content_success']
            metrics['expected_behavior_met'] = metrics['productive_completion']
    except MissingEvidence as error:
        check('required-evidence', 'unavailable', str(error))
    except (KeyError, ValueError, TypeError, IndexError) as error:
        check('binding-or-behavior', 'fail', str(error))
    return {'checks': checks, 'metrics': metrics,
            'critical_violations': [c['id'] for c in checks if c['status'] == 'fail']}
