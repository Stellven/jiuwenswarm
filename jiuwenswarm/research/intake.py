"""Deterministic controlled-upload qualification and the sole text extractor."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import sys
import uuid
from pathlib import Path

from .contracts import Principal, ResearchError


_PDF_WORKER = r'''
import io,sys
if sys.platform=='linux':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
 resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
import pdfplumber
if pdfplumber.__version__!='0.11.9':raise RuntimeError('pdf_parser_pin')
raw=sys.stdin.buffer.read()
with pdfplumber.open(io.BytesIO(raw)) as pdf:
 if getattr(pdf.doc,'is_extractable',False) is not True:raise ValueError('pdf_not_extractable')
 texts=[page.extract_text(layout=False) or '' for page in pdf.pages]
 # Preserve actual PDF page boundaries in new canonical captures so consumers
 # can cite pages without reopening or guessing from flattened text.
 text='\n\f\n'.join(texts)
 if not text.strip():raise ValueError('pdf_without_text_layer')
 sys.stdout.buffer.write(text.encode('utf-8',errors='strict'))
'''


async def extract_document(filename: str, data: bytes, *, timeout_s: float) -> bytes:
    if not isinstance(data,bytes) or timeout_s<=0:raise ResearchError('validation','Extraction requires exact bytes and a positive protected deadline')
    suffix=Path(filename).suffix.lower()
    if suffix in {'.txt','.md','.markdown'}:
        try:data.decode('utf-8',errors='strict')
        except UnicodeError as exc:raise ResearchError('validation','Document is not strict UTF-8') from exc
        return data
    if suffix=='.json':
        def unique_object(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('Duplicate JSON field')
                result[key]=value
            return result
        def reject_constant(value):
            raise ValueError('Nonfinite JSON number')
        def finite_float(value):
            number=float(value)
            if not math.isfinite(number):raise ValueError('Nonfinite JSON number')
            return number
        try:
            text=data.decode('utf-8',errors='strict')
            json.loads(text,object_pairs_hook=unique_object,parse_constant=reject_constant,parse_float=finite_float)
        except (UnicodeError,ValueError,RecursionError) as exc:
            raise ResearchError('validation','Document is not strict UTF-8 JSON with unique fields and finite numbers') from exc
        # Validation never reserializes the reference document: offsets and
        # extraction hashes continue to describe the exact uploaded UTF-8.
        return data
    if suffix!='.pdf':raise ResearchError('validation','Only TXT, Markdown, JSON and text-layer PDF are supported')
    process=await asyncio.create_subprocess_exec(sys.executable,'-I','-c',_PDF_WORKER,
        stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        out,_=await asyncio.wait_for(process.communicate(data),timeout_s)
        if process.returncode!=0:raise ResearchError('validation','Pinned PDF extraction failed')
        out.decode('utf-8',errors='strict')
        return out
    except BaseException:
        if process.returncode is None:
            process.kill();await process.wait()
        raise


def qualify_intake(store,principal: Principal,text: str,upload_refs,*,workspace_id: str,
                   profile_ref,workspace_ref,input_directory_ref,prior_plan_outcome_ref=None):
    principal.require('ingest',workspace_id)
    if not isinstance(text,str) or not text.strip():raise ResearchError('validation','A nonempty original request is required')
    try:raw=text.encode('utf-8',errors='strict')
    except UnicodeError as exc:raise ResearchError('validation','Request cannot be encoded as UTF-8') from exc
    for ref in (profile_ref,workspace_ref,input_directory_ref):store.read_blob(ref)
    if prior_plan_outcome_ref is not None:
        prior=store.read_record(prior_plan_outcome_ref,contract_id='plan-outcome')
        if prior['outcome']!='plan_infeasible':raise ResearchError('validation','Prior outcome is not a plan infeasibility')
    request_ref=store.put_blob(raw,media_type='text/plain;charset=utf-8')
    store.require_product_material([request_ref])
    documents=[];resources=[];uploads=[];seen_ids=set();seen_refs={tuple(request_ref.items())}
    for offered in upload_refs:
        upload_id=store.read_record(offered,contract_id='client-upload')['id'] if isinstance(offered,dict) else offered
        if upload_id in seen_ids:raise ResearchError('validation','Duplicate uploaded input')
        seen_ids.add(upload_id)
        record=store.get_upload(upload_id,principal.account_id)
        if record['scope_id']!=workspace_id or record['status']!='uploaded':raise ResearchError('not_found','Upload is outside the live authorized workspace')
        original=store.read_upload(upload_id,principal.account_id)
        upload_ref=store.put_record('client-upload',record)
        original_ref=store.put_blob(original,provenance={'upload_ref':upload_ref,'role':'original_upload'})
        if record['kind']=='docs':
            extracted=store.read_upload(upload_id,principal.account_id,extracted=True)
            try:extracted.decode('utf-8',errors='strict')
            except UnicodeError as exc:raise ResearchError('integrity_fault','Stored extraction is not UTF-8') from exc
            qualified=store.put_blob(extracted,media_type='text/plain;charset=utf-8',provenance={'upload_ref':upload_ref,'original_ref':original_ref,'role':'canonical_upload_extraction'})
            documents.append(qualified)
        else:
            qualified=original_ref;resources.append(qualified)
        store.require_product_material([original_ref,qualified])
        key=tuple(qualified.items())
        if key in seen_refs:raise ResearchError('validation','Shared or duplicate qualified input reference')
        seen_refs.add(key);uploads.append(upload_ref)
    record={'schema_version':'2.0.0','id':'intake:'+uuid.uuid4().hex,'request_ref':request_ref,'source_refs':documents,
            'offset_basis':'Unicode code points','resource_refs':resources,'upload_refs':uploads,'rejected_inputs':[],
            'user_id':principal.account_id,'profile_ref':profile_ref,'workspace_ref':workspace_ref,'input_directory_ref':input_directory_ref}
    if prior_plan_outcome_ref is not None:record['prior_plan_outcome_ref']=prior_plan_outcome_ref
    return store.put_record('qualified-intake',record)
