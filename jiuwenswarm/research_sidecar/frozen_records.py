"""Read original authorized export bytes, without a product client or state store.

The filename identifies the protected export record kind; schema validation and
exact Ref joins establish its meaning. Neither a producer verdict nor a manifest
entry establishes that another artifact was accepted.
"""
import json
import re
from pathlib import Path
from jiuwenswarm.research_records.contracts import ContractData
from .evidence import read_verified,relative


RECORD_PATH=re.compile(r'^evidence/[0-9]{4,}-([a-z][a-z0-9-]*)\.json$')
CONTRACTS={k:k for k in ('gate-decision','deterministic-check-result','verifier-assessment',
    'invocation-observation','dispatch-record','plan-outcome','route-record','model-call','bound-check-plan','review-context')}


def strict_json(raw):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('duplicate JSON field')
            value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def ref_key(ref):
    if not isinstance(ref,dict) or set(ref)!={'id','sha256'} or not isinstance(ref['id'],str) or not ref['id'] or not re.fullmatch('[a-f0-9]{64}',ref['sha256']):raise ValueError('invalid exact artifact Ref')
    return ref['id'],ref['sha256']


class FrozenRecords:
    def __init__(self,root,*,validate=None):
        self.root=Path(root).resolve(strict=True)
        self.validate=validate or ContractData().validate
        self.manifest=strict_json((self.root/'client_retrieval.json').read_bytes())
        self.validate('client-retrieval',self.manifest)
        self.run_id=self.manifest['run_id'];self.records=[];self.artifacts={};paths=set()
        refs={ref_key(r) for r in self.manifest['artifact_refs']}
        for row in self.manifest['files']:
            path=str(relative(row['path']));key=ref_key(row['artifact_ref'])
            if path in paths or key not in refs:raise ValueError('duplicate or unbound exported file')
            paths.add(path)
            raw=read_verified(self.root,{'path':path,'sha256':key[1]})
            if key in self.artifacts and self.artifacts[key]!=raw:raise ValueError('one Ref has conflicting bytes')
            self.artifacts[key]=raw
            match=RECORD_PATH.fullmatch(path)
            if not match:continue
            kind=match[1];record=strict_json(raw)
            if not isinstance(record,dict):raise ValueError('protected record must be an object')
            if kind in CONTRACTS:self.validate(CONTRACTS[kind],record)
            if 'run_id' in record and record['run_id']!=self.run_id:raise ValueError('foreign run record')
            self.records.append({'kind':kind,'ref':row['artifact_ref'],'record':record,'path':path})
        self.by_ref={ref_key(e['ref']):e for e in self.records}
        if len(self.by_ref)!=len(self.records):raise ValueError('duplicate protected record identity')

    def of_kind(self,kind):return [e for e in self.records if e['kind']==kind]

    def resolve(self,ref,kind=None):
        row=self.by_ref.get(ref_key(ref))
        if row is None or kind is not None and row['kind']!=kind:raise ValueError('required exact protected record is unavailable')
        return row['record']

    def json_artifact(self,ref):
        raw=self.artifacts.get(ref_key(ref))
        if raw is None:raise ValueError('required exact output bytes are unavailable')
        return strict_json(raw)

    def gate_rows(self):
        rows=[]
        for envelope in self.of_kind('gate-decision'):
            gate=envelope['record']
            check=self.resolve(gate['deterministic_result_ref'],'deterministic-check-result')
            if check['check_plan_ref']!=gate['check_plan_ref']:raise ValueError('gate check plan identity mismatch')
            plan=self.resolve(gate['check_plan_ref'],'bound-check-plan')
            checks={x['check_id']:x for x in check['results']}
            mandatory=plan['mandatory_deterministic']
            if len(checks)!=len(check['results']) or len(set(mandatory))!=len(mandatory):raise ValueError('duplicate deterministic check identity')
            observations=[self.resolve(r,'invocation-observation') for r in gate['invocation_refs']]
            if any(o['node_id']!=gate['node_id'] or o['attempt_id']!=gate['attempt_id'] for o in observations):raise ValueError('gate invocation scope mismatch')
            assessment=self.resolve(gate['assessment_ref'],'verifier-assessment') if gate['assessment_ref'] else None
            rows.append({'node_id':gate['node_id'],'output_port':gate['output_port'],
                'tier1_verdict':'PASS' if all(k in checks and checks[k]['outcome']=='PASS' for k in mandatory) else 'FAIL',
                'tier2_verdict':assessment['verdict'] if assessment else 'NOT_RUN','gate_decision':gate['verdict'],
                'advanced':gate['action']=='advance','persisted_at':gate['recorded_at'],'ref':envelope['ref']})
        return rows

    def model_call_rows(self):
        from datetime import datetime
        rows=[]
        for envelope in self.of_kind('model-call'):
            call=envelope['record'];duration=None
            if call['started_at'] and call['ended_at']:
                duration=(datetime.fromisoformat(call['ended_at'].replace('Z','+00:00'))-datetime.fromisoformat(call['started_at'].replace('Z','+00:00'))).total_seconds()
                if duration<0:raise ValueError('model-call clock order is inconsistent')
            role=call['call_function'] if call['call_function'] in {'worker','verifier','planner'} else 'other'
            rows.append({'call_ref':envelope['ref'],'role':role,'requested_model':call['identity']['requested'],
                'effective_model':call['identity']['effective'],'identity_basis':call['identity']['basis'],
                'duration_s':duration,'outcome':call['outcome'],'input_tokens':call['usage']['input_tokens'],
                'output_tokens':call['usage']['output_tokens'],'cost':call['usage']['cost_amount']})
        return rows

    def downstream_rows(self):
        return [{'node_id':e['record']['node_id'],'action':'started','at':e['record']['recorded_at']}
                for e in self.of_kind('dispatch-start')]
