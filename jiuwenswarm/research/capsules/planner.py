"""Bounded native proposals are advisory; independent checks and gates decide."""

import json
from importlib.resources import files

from ..binding import HOST_KEYS
from ..contracts import ResearchError,contract_schema
from ..native import NativePlanner
from ..planning import parse_planner_reply
from ..summary_planning import PAPER_CC_VERSION, PAPER_DELIVERY_CC, PAPER_SUMMARY_CC, is_document_summary_policy


def reachable_schema(schema):
    """The same schema with only the $defs its root can reach; validation is unchanged."""
    defs = schema.get('$defs', {})
    needed, pending = set(), [{k: v for k, v in schema.items() if k != '$defs'}]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key == '$ref' and isinstance(value, str) and value.startswith('#/$defs/'):
                    name = value.split('/')[2]
                    if name not in needed:
                        needed.add(name)
                        pending.append(defs[name])
                else:
                    pending.append(value)
        elif isinstance(node, list):
            pending.extend(node)
    return dict(schema, **{'$defs': {name: defs[name] for name in defs if name in needed}})


def _policy_hides(pin, policy):
    """Entries the protected policy can never accept: paper stages other than its one pinned release."""
    from ..unified_planning import is_integrated_policy
    return (pin['cc_name'] in (PAPER_SUMMARY_CC, PAPER_DELIVERY_CC) and pin['cc_version'] != PAPER_CC_VERSION
            and (is_integrated_policy(policy) or is_document_summary_policy(policy)))


def _pin(entry):
    return {k: entry[k] for k in ('cc_name', 'cc_version', 'declaration_sha256')}


def planner_views(catalog, snapshot, policy):
    """Reduced, planner-facing copies of the catalog and snapshot.

    The host keeps verifying and checking against the full records; the model
    only needs what it can act on: identity, purpose, typed ports, needs,
    limits, effects and check ids per exact pin, once. Nothing here is read back.
    """
    capsules = []
    for item in catalog.get('capsules', []):
        if _policy_hides(item['cc'], policy):
            continue
        d = item['declaration']
        ports = {side: [{k: p[k] for k in ('name', 'artifact_type', 'schema_ref', 'required', 'description') if k in p}
                        | ({'check_ids': p['check_ids']} if p.get('check_ids') else {}) for p in d['ports'][side]]
                 for side in ('inputs', 'outputs')}
        guarantees = d['guarantees']
        changes = d['changes']
        capsules.append({'cc': item['cc'], 'kind': d['identity']['kind'], 'purpose': d['identity']['summary'],
            'ports': ports, 'needs': d['needs'], 'limits': d['budget']['per_call'],
            'changes': {'effect_class': changes['effect_class'],
                'effects': [{k: e[k] for k in ('id', 'op', 'resource_key', 'reversibility', 'scope') if k in e} for e in changes['effects']],
                'invariants': changes['invariants'], 'provides': changes['provides']},
            'guarantees': {'check_ids': [c['id'] for c in guarantees['checks']], 'acceptance': guarantees['acceptance'],
                           'unanchored': guarantees['unanchored']},
            'coverage': d['coverage']})
    contracts = {'schema_version': catalog.get('schema_version', '1.0.0'),
        'library_snapshot_ref': catalog.get('library_snapshot_ref'), 'view': 'planner-reduced',
        'meaning': 'Reduced view of the pinned declarations; the host verifies and checks the complete declarations.',
        'capsules': capsules}
    entries = [{**_pin(e), **{k: e[k] for k in ('effect_class', 'network_mode', 'resource_needs', 'max_limits') if k in e}}
               for e in snapshot['entries'] if e.get('selectable_by_planner') and not _policy_hides(e, policy)]
    reduced = {'schema_version': snapshot['schema_version'], 'id': snapshot['id'], 'view': 'planner-reduced',
        'meaning': 'Selectable entries only; typed ports are listed once in capsule_contracts and check pins stay host-side.',
        'entries': entries}
    return contracts, reduced


def fill_declared_limits(raw, snapshot, policy):
    """Carrier-owned node limits: each node gets its capsule's declared max_limits.

    A node below its declared envelope cannot hold the reviews the host reserves
    for it (live run pl3: Screening at 120 s with two 60 s reviews ended
    budget_exhausted before its worker ran). Applied only when every node names a
    selectable pin and the declared envelopes fit the policy aggregate; otherwise
    the model's limits stand and plan_checks judge them.
    """
    try:
        value = json.loads(raw)
        nodes = value['nodes']
        declared = {tuple(e[k] for k in ('cc_name', 'cc_version', 'declaration_sha256')): e.get('max_limits')
                    for e in snapshot['entries'] if e.get('selectable_by_planner')}
        envelopes = [declared.get(tuple(n['cc'][k] for k in ('cc_name', 'cc_version', 'declaration_sha256'))) for n in nodes]
        aggregate = policy['aggregate_limits']
        if not isinstance(value.get('limits'), dict) or not envelopes or not all(isinstance(e, dict) for e in envelopes):
            return raw
        total = {'time_s': sum(e['time_s'] for e in envelopes), 'model_calls': sum(e['model_calls'] for e in envelopes),
                 'memory_mb': max(e['memory_mb'] for e in envelopes)}
    except (ValueError, KeyError, TypeError):
        return raw
    if any(total[d] > aggregate[d] for d in total):
        return raw
    for node, envelope in zip(nodes, envelopes):
        node['limits'] = {d: envelope[d] for d in ('time_s', 'model_calls', 'memory_mb')}
    for d in total:
        current = value['limits'].get(d)
        value['limits'][d] = min(aggregate[d], max(total[d], current if isinstance(current, (int, float)) else 0))
    return json.dumps(value, ensure_ascii=False, indent=2)


def _instructions_once(invoke):
    """The native harness repeats the system prompt as a system message inside the
    serialized conversation while the transport already carries it as system text."""
    async def call(prompt, system=None):
        if system is not None:
            try:
                messages = json.loads(prompt)
            except ValueError:
                messages = None
            if isinstance(messages, list) and all(isinstance(m, dict) for m in messages):
                prompt = json.dumps([m for m in messages if m.get('role') != 'system'], ensure_ascii=False)
        return await invoke(prompt, system=system)
    return call


def _protected_host_bindings():
    """Describe existing Binder/Scheduler inputs, without publishing live Refs.

    These records are host bindings, not missing Capsule output ports. Producer
    receipts become available only after the exact predecessor gate commits.
    The protected Binder and Scheduler still enforce every stated condition.
    """
    descriptions = {
        'screening_rubric': {
            'producer_cc': None, 'producer_output_port': None, 'direct_predecessor_required': False,
            'condition': 'Prepared rubric must equal screening_rubric.json in the exact selected admitted research.screening body.'},
        'environment_lock': {
            'producer_cc': None, 'producer_output_port': None, 'direct_predecessor_required': False,
            'condition': 'Prepared lock must equal the unique available environment_lock resource Ref in the frozen resource inventory.'},
        'run_configuration': {
            'producer_cc': None, 'producer_output_port': None, 'direct_predecessor_required': False,
            'condition': 'Host supplies the unchanged protected configuration Ref frozen into this run plan.'},
        'build_receipt': {
            'producer_cc': 'research.builder', 'producer_output_port': None, 'direct_predecessor_required': True,
            'condition': 'Exactly one Builder predecessor must advance. Host resolves its original build_receipt proposal by joining the actual producing invocation, model-call start, accepted manifest and bundle, blueprint and environment. Receipt readiness must be READY under the selected Builder receipt schema. Legacy static builds prohibit execution/install; prediction receipt v3 records bounded development tests and frozen offline provisioning, without scientific acceptance. This is not a public Builder output port.'},
        'screening_result': {
            'producer_cc': 'research.screening', 'producer_output_port': 'screening_result', 'direct_predecessor_required': True,
            'condition': 'Exactly one Screening predecessor must advance; host supplies its committed screening_result output.'},
        'execution_receipt': {
            'producer_cc': 'research.benchmark', 'producer_output_port': 'execution_receipt', 'direct_predecessor_required': True,
            'condition': 'Exactly one Benchmark predecessor must advance; host supplies its committed execution_receipt output.'},
        'provisioning_receipt': {
            'producer_cc': 'research.benchmark', 'producer_output_port': 'provisioning_receipt', 'direct_predecessor_required': True,
            'condition': 'Exactly one Benchmark predecessor must advance; host supplies its committed provisioning_receipt output.'},
        'gate_decision_index': {
            'producer_cc': None, 'producer_output_port': None, 'direct_predecessor_required': False,
            'condition': 'Host constructs one entry per committed accepted ancestor of this consumer in frozen topological order, naming each exact node-scope gate. Consumer predecessor edges must include all producers whose evidence it requires.'},
    }
    if set(descriptions) != HOST_KEYS:
        raise ResearchError('planner_host_bindings', 'Planner metadata does not cover the canonical protected host bindings')
    return {'schema': 'ai4r-planner-host-bindings:1',
        'meaning': 'Conditional host derivations supported by the existing protected Binder/Scheduler; not current artifacts, new permissions or acceptance.',
        'records': [dict(descriptions[key], run_input_key=key, artifact_type=key,
            source_kind='host_record', accepted_ref=None, future=None) for key in sorted(HOST_KEYS)]}


def _protected_run_inputs(resources):
    """Expose Binder's finite ordinary accepted-input aliases and inventory keys."""
    records = [
        {'run_input_key': 'brief', 'artifact_type': 'research_brief', 'schema_ref': None,
         'condition': 'Binder supplies this run\'s already committed Compiler Research Brief using the supplied exact brief_ref.'},
        {'run_input_key': 'search_scope', 'artifact_type': 'search_scope', 'schema_ref': 'search-scope:field-contract:1',
         'condition': 'Binder builds and captures search_scope during freeze, from the same accepted Brief, protected Search bounds, exact selected Search declaration, effective tool/network/read authority and this inventory. For local_documents the canonical local_document_buffer must resolve to nonempty qualified original document text within the run read ceiling. Proposal topic_hints are bounded phrases only. The resulting Ref does not exist at planning time and is never generated by a selectable Capsule.'},
    ]
    for resource in resources['resources']:
        if resource['resource_key'] in {'brief', 'search_scope'}:
            continue
        records.append({'run_input_key': resource['resource_key'], 'inventory_kind': resource['kind'],
            'inventory_available': resource['available'], 'inventory_ref_present': resource['ref'] is not None,
            'artifact_type': resource.get('artifact_type'), 'schema_ref': resource.get('schema_ref'),
            'condition': 'Binder takes the exact non-null Ref from this frozen inventory entry; selected Capsule needs and effective authority must still pass. The host captured artifact_type is what these bytes really are: bind this key only to a consumer input whose declared artifact_type (and schema_ref when given) equals it. A null artifact_type is untyped data that no input can consume. Never relabel the input to match the consumer. No new resource is created.'})
    return {'schema': 'ai4r-planner-run-input-bindings:1',
        'meaning': 'Existing ordinary Binder accepted-input keys are brief, search_scope and this resource inventory\'s resource_keys. This is descriptive context, not additional input or authority.',
        'records': [dict(record, source_kind='accepted_ref', accepted_ref=None, future=None) for record in records]}


async def execute(ctx,inputs):
    # The complete catalog is verified here, before the model sees only its reduced view.
    from ..planner_catalog import verify_catalog
    verify_catalog(inputs['capsule_contracts'], inputs['library_snapshot'], ctx.input_ref('library_snapshot'))
    contracts_view, snapshot_view = planner_views(inputs['capsule_contracts'], inputs['library_snapshot'], inputs['plan_policy'])
    payload=dict(inputs,capsule_contracts=contracts_view,library_snapshot=snapshot_view,brief_ref=ctx.input_ref('brief'),library_snapshot_ref=ctx.input_ref('library_snapshot'),
                 resource_inventory_ref=ctx.input_ref('resource_inventory'),policy_ref=ctx.input_ref('plan_policy'),
                 protected_host_bindings=_protected_host_bindings(),
                 protected_run_input_bindings=_protected_run_inputs(inputs['resource_inventory']))
    instructions=files('jiuwenswarm.research_assets').joinpath('planner','planner.txt').read_text('utf-8')
    from ..unified_planning import is_integrated_policy, integrated_planner_instructions
    if is_integrated_policy(inputs['plan_policy']):
        instructions += '\n' + integrated_planner_instructions(inputs['plan_policy'])
    from ..capability_planning import is_capability_policy, INSTRUCTIONS
    if is_capability_policy(inputs['plan_policy']):
        instructions += '\n' + INSTRUCTIONS
    instructions+='\nPinned output schema:\n'+json.dumps(reachable_schema(contract_schema('plan-proposal')),ensure_ascii=False,separators=(',',':'))
    from ..binding import plan_checks
    from ..state import json_bytes
    expected = {key: payload[key] for key in ('brief_ref', 'library_snapshot_ref', 'resource_inventory_ref', 'policy_ref')}
    # Two generations inside one work invocation. This is not a retry of an
    # executed DAG, a dispatch retry, a verifier waiver or an unbounded loop.
    for ordinal in (1, 2):
        raw = await NativePlanner().propose(payload, invoke=_instructions_once(ctx.model), instructions=instructions)
        if isinstance(raw, str) and not raw.startswith('INFEASIBLE:'):
            raw = fill_declared_limits(raw, inputs['library_snapshot'], inputs['plan_policy'])
        candidate_ref = ctx.store.put_blob(raw.encode('utf-8'), media_type='text/plain')
        try:
            kind, candidate = parse_planner_reply(raw)
            diagnostics = [] if kind == 'infeasible' else plan_checks(
                candidate, inputs['brief'], inputs['library_snapshot'], inputs['resource_inventory'],
                inputs['plan_policy'], plan_source='planned', expected_refs=expected)[1]
        except ResearchError as error:
            if error.code not in {'planner_output_invalid', 'contract_invalid', 'invalid_json'}:
                raise
            kind = 'proposal'
            diagnostics = [{'check_id': 'plan_proposal_schema', 'outcome': 'FAIL', 'reason': str(error), 'evidence_refs': []}]
        failed = [result for result in diagnostics if result['outcome'] == 'FAIL' and result['check_id'] != 'suggested_checks_known']
        diagnostic_ref = ctx.store.put_blob(json_bytes({'advisory': True, 'results': diagnostics}), media_type='application/json')
        ctx.store.append_record('planner_attempt', {'ordinal': ordinal, 'candidate_ref': candidate_ref,
            'diagnostics_ref': diagnostic_ref, 'advisory': True, 'repair_requested': bool(failed and ordinal == 1)})
        if not failed or ordinal == 2:
            break
        payload = dict(payload, repair={'previous_candidate': raw, 'validation_errors': failed,
            'instruction': 'Return one corrected complete proposal against the unchanged frozen inputs. These are advisory diagnostics, not authority or acceptance.'})
    try:
        kind,_=parse_planner_reply(raw)
    except ResearchError as error:
        # A completed text response that fails proposal structure is still a
        # candidate. The Runner captures its original bytes before checking;
        # missing schemas and actual model/runtime/budget faults still fail.
        if not isinstance(raw,str) or error.code not in {'planner_output_invalid','contract_invalid','invalid_json'}:
            raise
        kind='proposal'
    if kind=='infeasible':
        ref=ctx.store.put_blob(raw.encode('utf-8'),media_type='text/plain')
        ctx.record_host('planner_infeasible',ref)
        raise ResearchError('planner_reported_infeasible','The frozen capability set cannot cover this request',{'reason_ref':ref})
    from ..runner import ProducedArtifact
    return {'plan_proposal':ProducedArtifact(raw.encode('utf-8'),'plan-proposal',name='plan_proposal.json')}
