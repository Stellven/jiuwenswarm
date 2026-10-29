"""Measured opportunity qualification, independent of proposer optimism."""
import math


def decide(*,attribution,symptom_reproduced,mandatory_passed,headroom,headroom_minimum,diagnosis,resource_ready=True):
    if not resource_ready:return {'decision':None,'readiness':'BLOCKED','reason':'required target resource unavailable'}
    if attribution=='uncertain':return {'decision':'NEEDS_REVIEW','reason':'implementation attribution uncertain'}
    if attribution!='implementation' or not symptom_reproduced or not mandatory_passed:return {'decision':'NO_ATTEMPT','reason':'implementation opportunity prerequisites failed'}
    if isinstance(headroom,bool) or not isinstance(headroom,(int,float)) or not math.isfinite(headroom) or not 0<=headroom<=1 or not 0<=headroom_minimum<=1:return {'decision':'NO_ATTEMPT','reason':'measured headroom unavailable'}
    if headroom<headroom_minimum:return {'decision':'NO_ATTEMPT','reason':'measured headroom below profile minimum'}
    if not isinstance(diagnosis,dict) or not all(diagnosis.get(k) for k in ('cause','alternatives','falsification')):return {'decision':'NEEDS_REVIEW','reason':'structured diagnosis incomplete'}
    return {'decision':'START','reason':'reproduced implementation opportunity with measured headroom'}
