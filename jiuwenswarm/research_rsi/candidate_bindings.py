"""Protected original-byte joins for pure-helper subjects, never qualification.

The trusted assessment publishes a binding before mandatory execution. A broker
resolves only its deterministic alias in approved original-byte indexes; it never
searches arbitrary JSON or lets a request nominate a declaration or callback.
The independent IF015 verifier still validates the declaration and all13 cases.
"""
import hashlib
import json

from .records import encoded
from .session_policy import validate_private

SCHEMA='urn:ai4r:private:rsi-candidate-binding:1'


def binding_id(session_ref,candidate_ref):
    from .worker import ref
    ref(session_ref);ref(candidate_ref)
    return 'rsi-candidate-binding:'+hashlib.sha256(encoded([session_ref,candidate_ref])).hexdigest()


def validate_binding(value,read):
    validate_private(SCHEMA,value)
    from jiuwenswarm.research.contracts.rsi_security import RSIQualification
    from jiuwenswarm.research.contracts import ResearchError
    # This only checks the subject join. It does not execute require(), issue
    # an authority receipt, or substitute for operational qualification.
    guard=RSIQualification(read,None,candidate_resolver=lambda *_:value['declaration_ref'])
    try:
        guard._subject('trial',value['session_ref'],value['declaration_ref'])
        session=guard._subject('trial',value['session_ref'],value['candidate_ref'])
    except ResearchError as error:raise ValueError('Candidate binding subject violates the frozen contract') from error
    target=guard.get(session['target_profile_ref'])
    declaration=guard.get(value['declaration_ref'])
    if (value['target_ref']!=session['target_profile_ref']
            or value['parent_declaration_ref']!=session['parent_declaration_ref']
            or target['mutable_paths']!=[value['body_path']]
            or declaration['identity']['lineage']['build_trigger']!=session['session_id']
            or [row['sha256'] for row in declaration['identity']['body'] if row['path']==value['body_path']]!=[value['candidate_ref']['sha256']]):
        raise ValueError('Candidate binding differs from original target scope')
    return value


def bind_candidate(store,*,session_ref,candidate_ref,declaration_ref):
    session=store.get(session_ref);target=store.get(session['target_profile_ref'])
    if len(target['mutable_paths'])!=1:raise ValueError('One exact helper body is required')
    value={'schema':'ai4r-rsi-candidate-binding:1','session_ref':session_ref,
        'candidate_ref':candidate_ref,'declaration_ref':declaration_ref,
        'target_ref':session['target_profile_ref'],'parent_declaration_ref':session['parent_declaration_ref'],
        'body_path':target['mutable_paths'][0]}
    validate_binding(value,store.read)
    return store.record_candidate_binding(value)


class CandidateResolver:
    def __init__(self,*,read,locate):self.read,self.locate=read,locate
    def __call__(self,session_ref,candidate_ref):
        pin=self.locate(session_ref,candidate_ref)
        if pin is None:return None
        raw=self.read(pin)
        if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=pin['sha256']:
            raise ValueError('Original candidate binding bytes changed')
        value=json.loads(raw)
        if value.get('session_ref')!=session_ref or value.get('candidate_ref')!=candidate_ref:
            raise ValueError('Indexed candidate binding has another subject')
        validate_binding(value,self.read)
        return value['declaration_ref']


def public_candidate_resolver(public):
    """Use only fixed aliases; never inspect fixture stores or raw blob contents."""
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    def locate(session_ref,candidate_ref):
        alias=binding_id(session_ref,candidate_ref);found=[]
        for root in public.roots:
            if not (root/'original-byte-index.json').exists():continue
            digest=OriginalBytes(root).index().get(alias)
            if digest is not None:
                pin={'id':alias,'sha256':digest}
                if pin not in found:found.append(pin)
        if len(found)>1:raise ValueError('Ambiguous approved candidate binding')
        return found[0] if found else None
    return CandidateResolver(read=public.read,locate=locate)
