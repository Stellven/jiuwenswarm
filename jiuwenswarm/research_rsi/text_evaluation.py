"""Custodian-owned finite Screening measurements over IF011 and IF012.

Expected data is interpreted only here. Neither labels nor scoring programs
are placed in a worker binding, prompt, public subject or general export.
"""
from __future__ import annotations
import copy,hashlib,json,math,uuid
from .records import encoded
from .fixed_resources import FixtureEvaluator,closed


def valid_expectation(expected):
    if (not isinstance(expected,dict) or set(expected)!={'schema','tests'}
            or expected['schema']!='ai4r-rsi-json-expectation:1' or not isinstance(expected['tests'],list)
            or not 1<=len(expected['tests'])<=64):return False
    for test in expected['tests']:
        if not isinstance(test,dict) or set(test)!={'output','pointer','value'}:return False
        if test['output'] not in {'screening_result','opportunity_card'} or not isinstance(test['pointer'],str):return False
        pointer=test['pointer']
        if pointer and not pointer.startswith('/'):return False
        if any(pointer[i:i+2] not in {'~0','~1'} for i in range(len(pointer)) if pointer[i]=='~'):return False
        try:encoded(test['value'])
        except (TypeError,ValueError):return False
    return True


def evaluate_expectation(outputs,expected):
    if not valid_expectation(expected):return False
    for test in expected['tests']:
        pointer=test['pointer']
        try:
            value=outputs[test['output']]
            for token in pointer.split('/')[1:] if pointer else []:
                if any(token[i:i+2] not in {'~0','~1'} for i in range(len(token)) if token[i]=='~'):return False
                key=token.replace('~1','/').replace('~0','~')
                if isinstance(value,list):
                    if not key.isdigit() or str(int(key))!=key:return False
                    value=value[int(key)]
                else:value=value[key]
            if encoded(value)!=encoded(test['value']):return False
        except (KeyError,IndexError,TypeError,ValueError):return False
    return True


def mandatory_pass(capture,deterministic_ref):
    checked=json.loads(capture.read(deterministic_ref));plan=json.loads(capture.read(checked['check_plan_ref']))
    required=plan['mandatory_deterministic'];rows=checked['results']
    if not isinstance(required,list) or not required or len(required)!=len(set(required)):raise ValueError('Exact mandatory check inventory unavailable')
    return all(len(found:=[r for r in rows if r['check_id']==key])==1 and found[0]['outcome']=='PASS' for key in required)


def child_subject(store,parent,child,target,context,*,parent_declaration_ref,child_declaration_ref,body_refs,dependency_refs,attempt_ref=None):
    expected={row['path']:row['sha256'] for row in child['identity']['body']}
    if set(body_refs)!=set(expected) or any(body_refs[p]['sha256']!=h or hashlib.sha256(store.read(body_refs[p])).hexdigest()!=h for p,h in expected.items()):
        raise ValueError('Proposed child implementation closure differs')
    selected=[row['path'] for row in parent['identity']['body'] if row['sha256']==target['parent_ref']['sha256']]
    if len(selected)!=1 or selected[0] not in target['mutable_paths']:raise ValueError('One exact mutable parent body is required')
    path=selected[0]
    if path not in {'screening_prompt.txt','screening_rubric.json'} or expected[path]==target['parent_ref']['sha256']:
        raise ValueError('A real changed authorized Screening text body is required')
    return {'schema':'ai4r-rsi-text-subject:1','id':'text-subject:'+uuid.uuid4().hex,
        **{k:copy.deepcopy(context[k]) for k in ('session_ref','target_ref','configuration_ref')},
        'parent_declaration_ref':parent_declaration_ref,'child_declaration_ref':child_declaration_ref,
        'candidate_ref':body_refs[path],'child_body_refs':copy.deepcopy(body_refs),'dependency_refs':copy.deepcopy(dependency_refs),
        'attempt_ref':attempt_ref}


class TextFixtureEvaluator(FixtureEvaluator):
    """No selector/model client/custodian callback is chosen by a job."""
    def __init__(self,*,manifest,store,session_ref,target,repeats,profile,child_client,parent_client,issuer,publication,subjects,ledger):
        # Reuse the complete source partition/independence/byte validation.
        FixtureEvaluator.__init__(self,manifest=manifest,store=store,worker=None,session_ref=session_ref,target=target,repeats=repeats)
        self.version=2 if profile.get('schema')=='ai4r-rsi-screening-text-profile:2' else 1
        closed(profile,{'session_ref','target_ref','parent_admission_ref','parent_contract_ref','parent_check_plan_ref',
            'model_selection_profile_ref','deployment_ref','check_bundle_ref','checking_profile_ref','limits'},'ai4r-rsi-screening-text-profile:'+str(self.version))
        if profile['session_ref']!=session_ref or profile['target_ref']!=manifest['target_ref'] or repeats!=3:
            raise ValueError('Actual model-backed Screening requires the frozen mean-of-three policy')
        from .profiles import freeze_profile
        from jiuwenswarm.research_records.contracts import ContractData
        contracts=ContractData();parent_declaration=store.get(target['parent_declaration_ref'])
        freeze_profile(target,parent_declaration,contracts.validate)
        if parent_declaration['identity']['name']!='research.screening':raise ValueError('Unknown fixed Screening text carrier')
        contracts.validate('Limits',profile['limits'])
        session=store.get(session_ref)
        if (target['mutable_paths'][0] not in {'screening_prompt.txt','screening_rubric.json'}
                or self.version==1 and target['mutable_paths'][0]!='screening_prompt.txt'
                or any(not 0<profile['limits'][k]<=target['limits'][k] for k in profile['limits'])
                or profile['limits']['time_s']>session['limits']['per_call_s']):
            raise ValueError('Frozen text body or resource scope is unavailable')
        self.profile=profile;self.child,self.parent=child_client,parent_client
        self.issuer,self.publication,self.subjects,self.ledger=issuer,publication,subjects,ledger
        self.comparison=None;self.last_evidence=[];self.all_evidence=[]
        for rows in manifest['partitions'].values():
            for row in rows:
                if not valid_expectation(store.get(row['expected_ref'])):raise ValueError('Frozen expected test form is unavailable')
    def _action(self,candidate,phase):
        sid=self.store.get(self.session_ref)['session_id']
        if phase=='development':return 'development:'+uuid.uuid4().hex,'development'
        if phase in {'hidden_final','platform'}:
            if self.comparison is None:raise ValueError('The exact sealed final comparison is unavailable')
            return 'original-parent-final','final'
        fingerprint=hashlib.sha256(encoded(candidate)).hexdigest()
        rows=self.ledger.db.execute("SELECT id FROM actions WHERE session=? AND kind='loop' AND state='evaluating' AND fingerprint=?",(sid,fingerprint)).fetchall()
        if len(rows)!=1:raise ValueError('The exact already charged candidate operation is unavailable')
        return rows[0]['id'],'loop'
    async def one(self,candidate,row,phase,operation,repeat,*,timing=False):
        from .trial_port import validate_private,validate_parent
        legitimate=self.store.get(row['input_ref'])
        if set(legitimate)!={'schema','inputs'} or legitimate['schema']!='ai4r-rsi-legitimate-inputs:'+str(self.version):raise ValueError('Unknown explicit frozen legitimate input version')
        inputs=copy.deepcopy(legitimate['inputs'])
        action,kind=self._action(candidate,phase)
        is_parent=candidate==self.target['parent_ref']
        common={'id':'text-measurement:'+uuid.uuid4().hex,'session_ref':self.session_ref,'target_ref':self.manifest['target_ref'],
            'parent_admission_ref':self.profile['parent_admission_ref'],'parent_declaration_ref':self.target['parent_declaration_ref'],
            'parent_contract_ref':self.profile['parent_contract_ref'],'configuration_ref':self.target['configuration_ref'],
            'model_selection_profile_ref':self.profile['model_selection_profile_ref'],'deployment_ref':self.profile['deployment_ref'],
            'inputs':inputs,'limits':self.profile['limits'],'phase':phase,'repeat_index':repeat}
        if is_parent:
            binding={'schema':'ai4r-admitted-measurement-binding:'+str(self.version),**common,'parent_check_plan_ref':self.profile['parent_check_plan_ref']}
        else:
            subject=self.subjects(candidate,self.comparison)
            binding={'schema':'ai4r-isolated-evaluation-binding:'+str(self.version),**common,
                **{k:subject[k] for k in ('child_declaration_ref','child_body_refs','dependency_refs')},
                'check_bundle_ref':self.profile['check_bundle_ref'],'checking_profile_ref':self.profile['checking_profile_ref']}
            # v1 supports prompt mutation with an unchanged rubric. The separate
            # I022 versioned implementation-derived rubric binding is required
            # before rubric mutations may execute.
            parent=self.store.get(self.target['parent_declaration_ref']);rubric=next(x['sha256'] for x in parent['identity']['body'] if x['path']=='screening_rubric.json')
            if self.version==1 and binding['child_body_refs']['screening_rubric.json']['sha256']!=rubric:raise ValueError('Changed rubric requires explicit I022 version2 semantics')
        iterations=self.target['scoring']['batch_iterations'] if timing else 1
        if type(iterations) is not int or iterations<=0:raise ValueError('Frozen positive source batch iteration count required')
        duration=0;passed=True
        for iteration in range(iterations):
            current=copy.deepcopy(binding);current['id']='text-measurement:'+uuid.uuid4().hex
            issue=self.issuer.issue_parent if is_parent else self.issuer.issue
            slot=None
            if self.version==2:
                slot=('score',)
                if timing:
                    fields=operation.split(':')
                    if len(fields)!=3 or fields[0]!='timing' or not fields[1].isdigit() or fields[2] not in {'parent','child'}:
                        raise ValueError('Unknown finite frozen timing operation')
                    round_index=int(fields[1])
                    if not 0<=round_index<12:raise ValueError('Frozen source timing round exceeded')
                    slot=('warmup',round_index,iteration) if round_index<5 else ('paired',round_index-5,iteration)
            elif timing:raise ValueError('Historical binding1 has no timing slot authorization')
            current['reservation_ref']=issue(current,action_id=action,charge_kind=kind,candidate_ref=candidate,comparison=self.comparison,slot=slot)
            (validate_parent if is_parent else validate_private)('binding',current)
            pin=self.store.put(current)
            refs=[pin,current['reservation_ref'],*[r for p in inputs for r in p['artifact_refs']]]
            if not is_parent:refs += [current['child_declaration_ref'],*current['child_body_refs'].values(),*current['dependency_refs']]
            for ref in refs:self.publication.put_ref(ref,self.store.read(ref))
            client=self.parent if is_parent else self.child
            result,result_ref=await client.execute(pin)
            self.last_evidence.append(result_ref)
            if is_parent:
                measured=json.loads(client.capture.read(result['measurement_ref']));outputs=measured['output_refs']
                assessments=measured['assessment_refs'];status=measured['status']
                observations=[json.loads(client.capture.read(ref)) for ref in [measured['observation_ref'],*measured['observation_refs']]]
                elapsed=sum(r['duration_s'] for r in observations)
                mandatory=mandatory_pass(client.capture,measured['deterministic_ref'])
                failure=measured['failure']
            else:
                outputs={p['name']:p['artifact_ref'] for p in result['outputs']};assessments=result['assessment_refs'];status=result['status']
                observations=[json.loads(client.capture.read(p)) for p in result['observation_refs']]
                elapsed=sum(r['duration_s'] for r in observations)
                mandatory=result['mandatory_tests_passed'] and result['deterministic_result_ref'] is not None and mandatory_pass(client.capture,result['deterministic_result_ref'])
                failure=result['failure']['code'] if result['failure'] else None
            if failure and failure!='deterministic_check_failed':
                self.all_evidence.append(self.store.put({'schema':'ai4r-rsi-text-measurement-blocked:1','session_ref':self.session_ref,
                    'action_id':action,'binding_ref':pin,'result_ref':result_ref,'failure':failure,
                    'reason':'Unavailable or unclassified actual measurement is not a zero scientific score'}))
                raise ValueError('Actual parent/child model or checking measurement is unavailable; charged exposure retained')
            if status!='completed' or not mandatory:passed=False
            for ref in assessments:
                if json.loads(client.capture.read(ref))['verdict'] not in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'}:passed=False
            values={name:json.loads(client.capture.read(ref)) for name,ref in outputs.items()}
            passed=passed and evaluate_expectation(values,self.store.get(row['expected_ref']))
            if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0 or timing and elapsed<=0:raise ValueError('Actual captured duration is unavailable')
            duration+=elapsed
            raw_capture=self.store.put({'schema':'ai4r-rsi-text-fixture-capture:1','session_ref':self.session_ref,
                'target_ref':self.manifest['target_ref'],'candidate_ref':candidate,'phase':phase,'repeat_index':repeat,
                'action_id':action,'binding_ref':pin,'reservation_ref':current['reservation_ref'],'result_ref':result_ref,
                'fixture_id':row['id'],'expected_ref':row['expected_ref'],'passed':bool(passed),'duration_s':elapsed})
            self.all_evidence.append(raw_capture)
        return int(passed),duration
    async def mandatory(self,candidate):
        scores=await self.scores(candidate,'development','visible-parent-tests')
        return bool(scores) and all(all(v==1 for v in values) for values in scores)
    async def paired(self,parent,child,split,repeats,configuration_ref):
        before=len(self.all_evidence)
        capture=await super().paired(parent,child,split,repeats,configuration_ref)
        capture['raw_measurement_ref']=self.store.put({'schema':'ai4r-rsi-paired-measurement:1','session_ref':self.session_ref,
            'target_ref':self.manifest['target_ref'],'comparison':self.comparison,'configuration_ref':configuration_ref,
            'parent_ref':parent,'child_ref':child,'split':split,'repeats':repeats,'capture':copy.deepcopy(capture),
            'fixture_capture_refs':self.all_evidence[before:]})
        return capture
