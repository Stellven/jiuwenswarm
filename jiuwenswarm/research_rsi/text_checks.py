"""Finite trusted text tests; candidate text/JSON is parsed and never executed.

Only exact target-frozen protected test definitions are interpreted. Unknown
forms are blocked; these checks never replace independent runtime checking.
"""
import copy,hashlib,json,uuid
from jiuwenswarm.research.contracts import validate


class TextParentTests:
    def __init__(self,store):self.store=store
    def _check(self,kind,binding,parent,child):
        bodies=binding['child_body_refs']
        if kind=='prompt_utf8':
            return bool(self.store.read_blob(bodies['screening_prompt.txt']).decode('utf-8',errors='strict').strip())
        if kind=='rubric_dimensions':
            rubric=self.store.read_record(bodies['screening_rubric.json']);validate('screening-rubric',rubric)
            dims=rubric['dimensions']
            return (len(dims)==3 and {r['name'] for r in dims}=={'novelty','feasibility','compute_alignment'}
                and all(r['scale_min']==1 and r['scale_max']==5 and [a['score'] for a in r['anchors']]==[1,2,3,4,5] for r in dims)
                and rubric['total_rule']=='sum' and rubric['tie_rule']=='ascending_idea_id' and rubric['selection_rule']=='top_1')
        if kind=='ports_and_authority':
            values=[]
            for original in (parent,child):
                value=copy.deepcopy(original)
                for key in ('version_label','carrier','body','lineage'):value['identity'].pop(key,None)
                values.append(value)
            return values[0]==values[1]
        if kind=='body_closure':
            expected={row['path']:row['sha256'] for row in child['identity']['body']}
            return set(expected)==set(bodies) and all(bodies[name]['sha256']==digest and hashlib.sha256(self.store.read_blob(bodies[name])).hexdigest()==digest for name,digest in expected.items())
        return None
    async def run(self,binding_ref,required_test_refs):
        binding=self.store.read_record(binding_ref);parent=self.store.read_record(binding['parent_declaration_ref']);child=self.store.read_record(binding['child_declaration_ref'])
        receipts=[]
        for test_ref in required_test_refs:
            definition=self.store.read_record(test_ref)
            outcome='ENVIRONMENT_BLOCKED';measured=None
            if (self.store.record_kind(test_ref)=='rsi-parent-test' and set(definition)=={'schema','id','kind','parent_declaration_ref'}
                    and definition['schema']=='ai4r-screening-parent-test:1' and definition['parent_declaration_ref']==binding['parent_declaration_ref']):
                try:passed=self._check(definition['kind'],binding,parent,child)
                except (ValueError,KeyError,UnicodeError):passed=False
                if passed is not None:
                    outcome='PASS' if passed else 'FAIL'
                    plan=self.store.append_record('isolated-evaluation-check-plan',{'id':'parent-test-plan:'+uuid.uuid4().hex,
                        'schema':'ai4r-isolated-evaluation-check-plan:1','runner_refs':[test_ref],'mandatory_deterministic':['parent_test']})
                    measured=self.store.put_record('deterministic-check-result',{'schema_version':'1.0.0','subject_ref':binding['child_declaration_ref'],
                        'check_plan_ref':plan,'results':[{'check_id':'parent_test','outcome':outcome,
                        'reason':'Protected finite text parent test evaluated exact captured child bytes',
                        'evidence_refs':[test_ref,binding['child_declaration_ref'],*binding['child_body_refs'].values()]}]})
            receipts.append(self.store.append_record('isolated-required-test',{'id':'parent-test:'+uuid.uuid4().hex,'test_ref':test_ref,
                'child_declaration_ref':binding['child_declaration_ref'],'configuration_ref':binding['configuration_ref'],'outcome':outcome,
                'deterministic_result_ref':measured,'execution_receipt_ref':None,'observation_refs':[],
                'evidence_refs':[test_ref,binding['child_declaration_ref'],*([measured] if measured else [])]}))
        return receipts
    async def contain(self,trial_ref):
        # This installed owner starts no process, model call or asynchronous
        # external effect. All its parsing above completed on the calling task.
        return {'contained':True,'trial_ref':trial_ref,'scope':'trusted deterministic text parsing only'}
