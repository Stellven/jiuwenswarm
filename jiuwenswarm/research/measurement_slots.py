"""Finite IF011/IF012 r3 measurement slots; never a new oracle budget."""
from __future__ import annotations
import hashlib
import json
import re
from .contracts import ResearchError
from .state import json_bytes


def require(condition,reason):
    if not condition:raise ResearchError('measurement_slot',reason)


def subject_key(record):
    keys=[key for key in ('child_declaration_ref','parent_declaration_ref') if key in record]
    require(len(keys)==1,'Measurement needs exactly one actual subject')
    return keys[0]


def context_digest(record):
    keys=('session_ref','target_ref',subject_key(record),'phase','repeat_index','inputs_sha256','configuration_ref','action_id','charge_kind')
    return hashlib.sha256(json_bytes({key:record[key] for key in keys})).hexdigest()


def reservation_id(record_without_id_signature,slot):
    require(isinstance(slot,(tuple,list)) and bool(slot),'An exact finite measurement slot is required')
    kind=slot[0]
    require(kind in {'score','warmup','paired'},'Unknown measurement slot')
    if kind=='score':require(len(slot)==1,'Score has no batch indices')
    else:
        require(len(slot)==3 and all(type(v) is int and v>=0 for v in slot[1:]),'Batch indices must be canonical nonnegative integers')
        require(slot[1]<(5 if kind=='warmup' else 7),'Batch index exceeds the source population')
    return 'rsi-slot:3:'+context_digest(record_without_id_signature)+':'+':'.join(map(str,slot))


def parse_slot(record,binding,target,session):
    if record['schema'].endswith((':1',':2')):return ('score',)
    require(record['schema'] in {'ai4r-rsi-trial-reservation:3','ai4r-rsi-parent-reservation:3'}
        and binding['schema'].endswith(':2'),'Reservation3 needs an explicit external-input binding2')
    match=re.fullmatch(r'rsi-slot:3:([a-f0-9]{64}):(score|warmup:(0|[1-9][0-9]*):(0|[1-9][0-9]*)|paired:(0|[1-9][0-9]*):(0|[1-9][0-9]*))',record.get('id',''))
    require(match is not None and match[1]==context_digest(record),'Slot grammar or exact context digest differs')
    repeats=session['pass_count_repeats'];repeat=binding['repeat_index']
    require(type(repeats) is int and repeats in (1,3) and type(repeat) is int and 0<=repeat<repeats,'Slot cannot choose a different frozen repeat')
    parts=match[2].split(':');slot=(parts[0],) if parts[0]=='score' else (parts[0],int(parts[1]),int(parts[2]))
    if slot[0]!='score':
        scoring=target['scoring'];iterations=scoring['batch_iterations']
        require(scoring['warmup_batches']==5 and scoring['paired_rounds']==7 and type(iterations) is int and iterations>0,'Frozen source timing population is unavailable')
        require(slot[1]<(5 if slot[0]=='warmup' else 7) and slot[2]<iterations,'Slot exceeds the exact frozen batch population')
        require(binding['phase'] in {'platform','hidden_final'} and record['phase']==binding['phase'] and record['charge_kind']=='final','Timing requires the same sealed-final comparison authority')
    return slot


def external_inputs(store,binding):
    ports=binding['inputs'];names=[p['name'] for p in ports]
    if binding['schema'].endswith(':1'):
        require(names==['brief','candidate_set','screening_rubric'],'Historical binding has ambiguous external/rubric ports')
        rubric=ports[2]['artifact_refs'];require(len(rubric)==1,'Historical work rubric is ambiguous')
        key='child_declaration_ref' if binding['schema'].startswith('ai4r-isolated-evaluation-binding:') else 'parent_declaration_ref'
        declaration=store.read_record(binding[key])
        bodies=[p for p in declaration['identity']['body'] if p['path']=='screening_rubric.json']
        require(len(bodies)==1 and rubric[0]['sha256']==bodies[0]['sha256'],'Historical rubric is not the exact subject body')
        if key=='child_declaration_ref':require(binding['child_body_refs']['screening_rubric.json']==rubric[0],'Historical child rubric was swapped')
        store.read_blob(rubric[0]);ports=ports[:2]
    else:require(binding['schema'].endswith(':2') and names==['brief','candidate_set'],'External input identity is not canonical')
    for port in ports:
        require(set(port)=={'name','contract_id','artifact_refs'} and isinstance(port['artifact_refs'],list) and port['artifact_refs'],'Missing exact external input capture')
        for ref in port['artifact_refs']:store.read_blob(ref)
    return ports


def semantic_context(store,binding,reservation):
    require(reservation['inputs_sha256']==hashlib.sha256(json_bytes(binding['inputs'])).hexdigest(),'Original signed input hash differs')
    key=subject_key(reservation)
    require(all(reservation[k]==binding[k] for k in ('session_ref','target_ref',key,'phase','repeat_index','configuration_ref')),'Reservation/binding identity differs')
    return [reservation[k] for k in ('session_ref','action_id',key,'phase','repeat_index')]+[hashlib.sha256(json_bytes(external_inputs(store,binding))).hexdigest()]


def legacy_key(reservation,owner):
    return owner+'-reservation:'+hashlib.sha256(json_bytes([reservation[k] for k in ('session_ref','action_id',subject_key(reservation),'phase','repeat_index','inputs_sha256')])).hexdigest()


def claim_reservation(store,binding,reservation,*,owner,binding_ref,target,session,references,validate_legacy):
    require(owner in {'isolated','parent'},'Unknown protected measurement owner')
    slot=parse_slot(reservation,binding,target,session);context=semantic_context(store,binding,reservation)
    key=owner+'-reservation-slot:'+hashlib.sha256(json_bytes([context,slot])).hexdigest()
    legacy=legacy_key(reservation,owner)
    with store.transaction() as db:
        require(db.execute('SELECT 1 FROM metadata WHERE key=?',(key,)).fetchone() is None,'Measurement slot already issued; reconcile without replay')
        # Legacy keys survive unchanged. Resolve their actual immutable
        # bindings before comparing normalized semantic score identities.
        for row in db.execute('SELECT key,value FROM metadata WHERE key LIKE ?',(owner+'-reservation:%',)).fetchall():
            try:
                old=json.loads(row['value']);ref=old.get('binding_ref')
                if ref is None:
                    grant=store.read_record(old['grant_ref'] if owner=='parent' else old['trial_ref']);ref=grant['binding_ref']
                bound=store.read_record(ref);prior=store.read_record(bound['reservation_ref'])
                require(row['key']==legacy_key(prior,owner),'Legacy once claim has an inconsistent original join')
                subject=subject_key(prior)
                require(all(prior[k]==bound[k] for k in ('session_ref','target_ref',subject,'phase','repeat_index','configuration_ref'))
                    and prior['inputs_sha256']==hashlib.sha256(json_bytes(bound['inputs'])).hexdigest(),'Legacy reservation/binding original joins differ')
                prior_base=[prior[k] for k in ('session_ref','action_id',subject,'phase','repeat_index')]
                # An already committed unrelated historical session grants no
                # current authority. Key rotation must not requalify it. Only
                # potentially identical scores need current-context validation.
                if prior_base!=context[:5]:continue
                validate_legacy(bound)
                prior_context=semantic_context(store,bound,prior)
            except ResearchError:raise
            except (KeyError,TypeError,ValueError) as error:
                raise ResearchError('measurement_slot','Legacy once claim is ambiguous; reconcile without replay') from error
            if slot==('score',):require(prior_context!=context,'Equivalent historical score was already issued; reconcile without replay')
        value={'binding_ref':binding_ref,**references,'slot':list(slot)}
        db.execute('INSERT INTO metadata VALUES(?,?)',(key,json_bytes(value).decode()))
        if slot==('score',):
            require(db.execute('SELECT 1 FROM metadata WHERE key=?',(legacy,)).fetchone() is None,'Historical score claim already exists')
            db.execute('INSERT INTO metadata VALUES(?,?)',(legacy,json_bytes(value).decode()))
    return store.append_record(owner+'-reservation-claim',{'id':key,**references,'binding_ref':binding_ref,
        'reservation_ref':binding['reservation_ref'],'slot':list(slot),'legacy_key':legacy if slot==('score',) else None})
