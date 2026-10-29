"""Protected exact-byte preparation and mandatory checks before hidden evaluation."""
import hashlib
from pathlib import Path
import uuid
from .mutation import materialize,SecurityViolation


class GuardedAssessment:
    def __init__(self,*,parent_directory,target,store,work_root,run_mandatory,make_declaration):
        self.parent=Path(parent_directory);self.target=target;self.store=store;self.work=Path(work_root)
        self.mandatory,self.make_declaration=run_mandatory,make_declaration;self.last_capture={}
    async def __call__(self,proposal):
        self.last_capture={}
        path=proposal['path'];body=proposal['body'].encode('utf8')
        child_ref=self.store.put_bytes(body)
        self.last_capture={'child_ref':child_ref,'rationale':proposal['rationale']}
        # Capture an attempted change before its authority check, without
        # reading an out-of-scope parent path. It is rejection evidence only.
        diff_ref=self.store.put({'format':'ai4r-body-diff-v1','files':[{'path':path,
            'before_ref':self.target['parent_ref'] if path in self.target['mutable_paths'] else None,'after_ref':child_ref}]})
        self.last_capture['diff_ref']=diff_ref
        if path not in self.target['mutable_paths']:raise SecurityViolation('proposal touched undeclared path')
        original=(self.parent/path).read_bytes()
        if hashlib.sha256(original).hexdigest()!=self.target['parent_ref']['sha256']:raise SecurityViolation('parent body changed after freeze')
        if child_ref['sha256']==self.target['parent_ref']['sha256']:raise ValueError('proposal is identical to parent; no child change')
        snapshot=materialize(self.parent,self.work/uuid.uuid4().hex,{path:body},self.target['mutable_paths'],[])
        declaration,child=await self.make_declaration(snapshot,child_ref,diff_ref)
        checked=await self.mandatory(snapshot,declaration)
        return {'child_ref':child_ref,'diff_ref':diff_ref,'child':child,'child_declaration_ref':self.store.put(declaration),
            'mandatory_passed':checked['passed'],'evidence_refs':checked['evidence_refs'],
            'visible_selection_time_s':checked.get('visible_selection_time_s')}
