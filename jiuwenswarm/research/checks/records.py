"""Gate-host record completion; no model or derived builder owns these facts."""
from __future__ import annotations

import copy
import hashlib
import re


def body_files_sha256(body):
    rows=sorted(body,key=lambda item:item['path'].encode('utf-8'))
    raw=''.join(item['path']+'\t'+item['sha256']+'\n' for item in rows).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def error_fingerprint(text):
    if not text:return None
    value=re.sub(r'\b\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?Z?','<time>',text)
    value=re.sub(r'(?i)\b(?:pid|process[_ -]?id)\s*[:=]?\s*\d+','<pid>',value)
    value=re.sub(r'\b0x[0-9A-Fa-f]+\b','<address>',value)
    value=re.sub(r'(?i)\brun[:=_-][a-z0-9_.:-]+','<run>',value)
    value=re.sub(r'(?:[A-Za-z]:[\\/]|/)[^\s]+','<path>',value)
    value=re.sub(r'\b(?:tmp|temp)[-_][a-zA-Z0-9_-]+\b','<temporary>',value)
    value=re.sub(r'\b\d{4,}\b','<number>',value)
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def complete_observation(observation,*,decisions,check_refs,assessment_ref=None,human_ref=None,
                         platform_error=False,input_invalid=False,scientific_negative=False,error_text=None):
    result=copy.deepcopy(observation)
    advance=bool(decisions) and all(item['action']=='advance' for item in decisions)
    if observation['outcome']=='success' and advance and not scientific_negative:failure_class='none'
    elif observation['outcome']=='interrupted' or any(item['verdict']=='ENVIRONMENT_BLOCKED' for item in decisions) or platform_error:failure_class='infrastructure'
    elif input_invalid:failure_class='input'
    elif observation['cc_name']=='research.evaluation' and scientific_negative and advance:failure_class='scientific'
    else:failure_class='capsule'
    result.update(failure_class=failure_class,error_fingerprint=error_fingerprint(error_text) if failure_class!='none' else None,
                  check_result_refs=copy.deepcopy(check_refs),verifier_assessment_ref=copy.deepcopy(assessment_ref),human_answer_ref=copy.deepcopy(human_ref))
    return result
