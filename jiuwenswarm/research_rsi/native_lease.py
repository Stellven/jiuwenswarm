"""Durable native model ownership; worker cleanup never proves native stop."""
import json
import os
from datetime import datetime,timezone
from .records import encoded
from .custody import ExposureError


class ProfileInUse(ExposureError):pass


def native_completion_proof(store,starts):
    """A failed history row is not proof that an actual effect stopped."""
    ids={row['record']['call_id'] for row in starts}
    calls=[row for row in store.iter_records(kinds=('model-call',)) if row['record'].get('id') in ids]
    containments=list(store.iter_records(kinds=('model-run-contained',)))
    used=[];known=True
    for start in starts:
        value=start['record'];matched=[r for r in calls if r['record'].get('id')==value['call_id']
            and r['record'].get('invocation_id')==value['invocation_id']]
        if len(matched)!=1:known=False;continue
        outcome=matched[0]['record'].get('outcome')
        if outcome=='completed':continue
        proof=[r for r in containments if r['record'].get('contained') is True
            and value.get('run_id') is not None and r['record'].get('run_id')==value['run_id']
            and value['invocation_id'] in r['record'].get('invocation_ids',[])]
        if outcome!='failed' or not proof:known=False
        else:used.extend(r['ref'] for r in proof)
    return known,{'no_dispatch_start_observed':not starts,'known_terminal_call_refs':[row['ref'] for row in calls],
        'actual_model_containment_refs':used}


def utc():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class NativeEffectLease:
    def __init__(self,store,scope_ref):
        self.store,self.scope_ref=store,scope_ref;self.key=encoded(scope_ref).decode()
        store.db.execute('CREATE TABLE IF NOT EXISTS native_effect_leases(scope TEXT PRIMARY KEY,state TEXT,ref TEXT)')
    def current(self):
        row=self.store.db.execute('SELECT state,ref FROM native_effect_leases WHERE scope=?',(self.key,)).fetchone()
        return None if row is None else {'state':row[0],'ref':json.loads(row[1])}
    def assert_available(self):
        row=self.current()
        if row and row['state'] in {'active','uncertain'}:raise ProfileInUse('PROFILE_IN_USE: exact native effect containment remains unproved')
    def start(self,session_id,contract_ref):
        with self.store.lock:
            self.store.db.execute('BEGIN IMMEDIATE')
            try:
                self.assert_available()
                namespace=os.readlink('/proc/self/ns/pid') if os.name=='posix' else 'unavailable'
                pin=self.store.put({'record_kind':'rsi-native-effect-start:1','scope_ref':self.scope_ref,
                    'session_id':session_id,'contract_ref':contract_ref,'pid_namespace':namespace,
                    'owner_pid':os.getpid(),'recorded_at':utc()})
                self.store.db.execute('INSERT OR REPLACE INTO native_effect_leases VALUES(?,?,?)',(self.key,'active',encoded(pin).decode()))
                self.store.db.execute('COMMIT');return pin
            except BaseException:self.store.db.execute('ROLLBACK');raise
    def _finish(self,pin,state,proof):
        with self.store.lock:
            self.store.db.execute('BEGIN IMMEDIATE')
            try:
                current=self.current()
                if current is None or current['state']!='active' or current['ref']!=pin:raise ValueError('Native effect lease owner/state differs')
                receipt=self.store.put({'record_kind':'rsi-native-effect-completion:1','prior_lease_ref':pin,'scope_ref':self.scope_ref,
                    'state':state,'proof':proof,'recorded_at':utc()})
                self.store.db.execute('UPDATE native_effect_leases SET state=?,ref=? WHERE scope=?',(state,encoded(receipt).decode(),self.key))
                self.store.db.execute('COMMIT');return receipt
            except BaseException:self.store.db.execute('ROLLBACK');raise
    def complete(self,pin,proof):return self._finish(pin,'complete',proof)
    def uncertain(self,pin,proof):return self._finish(pin,'uncertain',proof)
    def release_from_receipt(self,receipt_ref,read_ref):
        current=self.current()
        if current is None or current['state']=='complete':return
        original=current['ref'];record=self.store.get(original)
        if current['state']=='uncertain':original=record['prior_lease_ref'];record=self.store.get(original)
        value=json.loads(read_ref(receipt_ref))
        fields={'schema','scope_ref','prior_lease_ref','owned_container_id','prior_pid_namespace','observed_exited','observed_no_owned_processes','evidence_refs','recorded_at'}
        if (set(value)!=fields or value['schema']!='ai4r-rsi-native-containment:1' or value['scope_ref']!=self.scope_ref
            or value['prior_lease_ref']!=original or value['prior_pid_namespace']!=record['pid_namespace']
            or value['observed_exited'] is not True or value['observed_no_owned_processes'] is not True
            or not isinstance(value['owned_container_id'],str) or len(value['owned_container_id'])!=64
            or any(c not in '0123456789abcdef' for c in value['owned_container_id']) or not value['evidence_refs']):
            raise ValueError('Exact protected host native-containment receipt required')
        import hashlib
        for pin in value['evidence_refs']:
            if hashlib.sha256(read_ref(pin)).hexdigest()!=pin['sha256']:raise ValueError('Native containment raw evidence changed')
        with self.store.lock:
            if self.current()!=current:raise ValueError('Native effect changed during containment reconciliation')
            self.store.put({'record_kind':'rsi-native-effect-release:1','scope_ref':self.scope_ref,'prior_state':current,
                'host_containment_ref':receipt_ref,'recorded_at':utc()})
            self.store.db.execute('UPDATE native_effect_leases SET state=?,ref=? WHERE scope=?',('complete',encoded(receipt_ref).decode(),self.key))
