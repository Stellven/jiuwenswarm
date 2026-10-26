"""Finite routing benchmark authority; it grants no product admission or gate."""
import copy
import json
import time
import uuid

PROTOCOL = 'ai4r-routing-component:1'


class ComponentAuthority:
    """Host-owned finite claims for this component protocol, not app authority."""
    def __init__(self, store, owner, snapshot, job, plan, contract_ref):
        self.store, self.owner, self.snapshot = store, owner, snapshot
        self.job, self.plan, self.contract_ref = job, plan, contract_ref
        self.contexts = {}; self.claims = {}
        self.run_id = snapshot['run_id']
        self.policy = store.put_blob(json.dumps({'protocol': PROTOCOL, 'role': 'isolated_controller'}).encode())
        self.profile = store.put_record('model-selection-profile', {'schema_version': '1.0.0',
            'id': 'local-component-profile', 'policy_mode': 'development_profile',
            'approved_model_ids': [c['model_id'] for c in snapshot['candidates']],
            'extra_requirements': {}, 'selection_allowance': {'enabled': False, 'deployment_ref': None,
                'model_calls': 0, 'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []},
            'alternate_model_id': None, 'policy_ref': self.policy})

    def open(self, function='worker'):
        limit = self.plan['limits']['verifier_time_s' if function == 'verifier' else 'worker_time_s']
        execution = 'component-execution:'+uuid.uuid4().hex
        self.contexts[execution] = {'run_id': self.run_id, 'node_id': self.job['variant_id'],
            'subnode_id': function, 'attempt_id': self.job['variant_id']+'-a1',
            'invocation_id': 'component-invocation:'+uuid.uuid4().hex, 'execution_id': execution,
            'call_function': function, 'cc_name': 'benchmark.bounded-json', 'cc_version': 'local-1',
            'contract_ref': self.contract_ref, 'model_selection_profile_ref': self.profile,
            'deployment_ref': next(c['deployment_ref'] for c in self.snapshot['candidates'] if c['preset_id']=='qwen'),
            'router': {'enabled': False}, 'limits': {'time_s': limit, 'model_calls': 1, 'memory_mb': 1024},
            'execution_deadline_monotonic_s': time.monotonic()+limit,
            'approved_model_ids': [c['model_id'] for c in self.snapshot['candidates']]}
        return {'execution_id': execution, 'call_ordinal': 1}

    def _claim(self, context):
        # One worker, at most one selector and one independent reviewer.
        # A fourth call, replay or switched executor cannot obtain authority.
        reserve = 1 if context['call_function'] != 'verifier' else 0
        used=self.store.connection.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=?',(self.run_id,)).fetchone()[0]
        context=dict(context,routing_budget={'schema':'local-component-budget:1',
            'calls_remaining':max(0,3-used),'verifier_calls_reserved':reserve,
            'time_remaining_s':max(0,context['execution_deadline_monotonic_s']-time.monotonic()),
            'tokens_remaining':None,'cost_remaining':None})
        call, ref = self.store.claim_model_call(context, invocation_limit=1,
            node_limit=3, run_limit=3, reserved_node_calls=reserve, reserved_run_calls=reserve)
        result = dict(context, call_id=call, call_claim_ref=ref)
        self.claims[call] = copy.deepcopy(result)
        return result

    def authorize(self, request):
        if set(request) != {'execution_id', 'call_ordinal'} or request['call_ordinal'] != 1:
            raise ValueError('Invalid component call')
        return self._claim(dict(self.contexts[request['execution_id']], call_ordinal=1))

    def revalidate(self, payload):
        from jiuwenswarm.research.contracts import ResearchError
        value = self.claims[payload['call_id']]
        if any(value[k] != payload[k] for k in payload) or value['execution_id'] not in self.contexts:
            raise ResearchError('invalid_request', 'Component claim changed')
        if time.monotonic() >= value['execution_deadline_monotonic_s']:
            raise ResearchError('budget_exhausted', 'Component deadline elapsed')
        return copy.deepcopy(value)

    def selection(self, payload):
        value = self.revalidate({k:v for k,v in payload.items() if k != 'prompt_sha256'})
        if value['call_function'] != 'worker':
            raise ValueError('A verifier or selector cannot request selection')
        candidate = next(c for c in self.snapshot['candidates'] if c['id']==self.snapshot['selector_id'])
        value.update(purpose='routing_selection', call_function='routing_selection',
            subject_call_id=value['call_id'], subject_invocation_id=value['invocation_id'],
            invocation_id=value['invocation_id']+':routing', routing_selection_candidate=candidate,
            expected_prompt_sha256=payload['prompt_sha256'], deployment_ref=candidate['deployment_ref'],
            execution_deadline_monotonic_s=min(value['execution_deadline_monotonic_s'], time.monotonic()+self.snapshot['routing_policy']['selection_time_s']),
            limits=dict(value['limits'], time_s=self.snapshot['routing_policy']['selection_time_s']))
        value.pop('call_id'); value.pop('call_claim_ref')
        return self._claim(value)

