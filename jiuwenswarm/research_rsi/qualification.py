"""Finite IF015 authority checks; default absence never authorizes a new effect."""
from jiuwenswarm.research.contracts.rsi_security import RSIQualification
from jiuwenswarm.research.contracts import ResearchError


class QualificationUnavailable(ValueError):pass


def require_qualification(authority,operation,*,session_ref,worker_profile_ref=None,candidate_ref=None):
    if authority is None or not callable(getattr(authority,'require',None)):
        raise QualificationUnavailable('RSI security qualification is unavailable')
    try:result=authority.require(operation,session_ref=session_ref,worker_profile_ref=worker_profile_ref,candidate_ref=candidate_ref)
    except (ValueError,KeyError,TypeError,OSError,ResearchError) as error:
        raise QualificationUnavailable('Current independent RSI security qualification is unavailable') from error
    if not isinstance(result,dict) or set(result)!={'qualification_ref','scope_ref'}:
        raise QualificationUnavailable('RSI security qualification authority returned no exact proof')
    for ref in result.values():
        if not isinstance(ref,dict) or set(ref)!={'id','sha256'} or not isinstance(ref['id'],str) or not ref['id'] or not isinstance(ref['sha256'],str) or len(ref['sha256'])!=64 or any(c not in '0123456789abcdef' for c in ref['sha256']):
            raise QualificationUnavailable('RSI security qualification proof identity is malformed')
    return result


def captured_qualification(store,qualification_ref,*,scope_observer=None):
    if qualification_ref is None:return None
    read=getattr(store,'read_blob',None) or store.read
    kind=getattr(store,'record_kind',None)
    # An original scope document alone is not evidence of the currently
    # running image. Until the finite trusted launcher observer is composed,
    # the positive operational path remains unavailable.
    return RSIQualification(read,qualification_ref,kind_reader=kind,scope_observer=scope_observer)
