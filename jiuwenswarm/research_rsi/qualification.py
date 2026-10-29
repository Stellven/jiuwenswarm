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


def captured_qualification(store,qualification_ref,*,scope_observer=None,
        validation_profile=None,case_observer=None,public_key=None,key_id=None,
        candidate_resolver=None,kind_reader=None):
    if qualification_ref is None:return None
    read=getattr(store,'read_blob',None) or store.read
    kind=kind_reader or getattr(store,'record_kind',None)
    # An original scope document alone is not evidence of the currently
    # running image. Until the finite trusted launcher observer is composed,
    # the positive operational path remains unavailable.
    return RSIQualification(read,qualification_ref,kind_reader=kind,scope_observer=scope_observer,
        validation_profile=validation_profile,case_observer=case_observer,public_key=public_key,key_id=key_id,
        candidate_resolver=candidate_resolver)


def configured_qualification(store,qualification_ref,*,candidate_resolver=None,kind_reader=None):
    """Prefer the fixed root installation, with current live producer checks."""
    from jiuwenswarm.research.contracts.rsi_installation import installed_consumer_qualification
    authority=installed_consumer_qualification(store,candidate_resolver=candidate_resolver)
    if authority is None:
        return captured_qualification(store,qualification_ref,candidate_resolver=candidate_resolver,kind_reader=kind_reader)
    if qualification_ref!=authority.installation.qualification_ref:
        raise QualificationUnavailable('Resource binding differs from the root-installed qualification')
    return authority


def require_key_pin(authority,public_key,key_id):
    installation=getattr(authority,'installation',None)
    if installation is not None and (installation.public_key!=public_key or installation.key_id!=key_id):
        raise QualificationUnavailable('Captured custodian key differs from the root-installed qualification')
