"""Once-only custodian collection of actual Target 1 calibration captures.

This module never runs candidate code directly, signs evidence, grants IF015
authority, or supplies fake ExposureLedger calibration counts. Uncalibrated
fixture exposure has a separate durable ledger; unknown runs cannot be replayed.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import time
from fractions import Fraction

from .fixed_resources import FixtureEvaluator
from .qualification import require_qualification
from .records import encoded
from .session_policy import validate_private, _contracts
from .statistics import qualify
from .targets.ranking_preparation import (
    _read_preparation, calibration_contexts, calibration_inventory, draft_target,
    require_custodian_store, REVIEW_SCHEMA, preparation_kind,
)
from .worker import WorkerClient, validate_profile

PLAN_SCHEMA = 'urn:ai4r:private:rsi-calibration-plan:1'
MAX_POPULATION = 256
MAX_INVOCATIONS = 100000


class CalibrationOutcomeUnknown(ValueError):
    pass


class CalibrationNotEstablished(ValueError):
    pass


def _scope(store, *, preparation_ref, review_ref, target_ref, fixture_manifest_ref,
           session_ref, worker_profile_ref):
    prep = _read_preparation(store, preparation_ref)
    review = store.get(review_ref); validate_private(REVIEW_SCHEMA, review)
    target = store.get(target_ref); manifest = store.get(fixture_manifest_ref)
    expected_target, expected_manifest = draft_target(store, preparation_ref, target,
        review_ref=review_ref, validate=_contracts().validate)
    session = store.get(session_ref); _contracts().validate('rsi-session', session)
    profile = validate_profile(store.get(worker_profile_ref))
    declaration = store.get(prep['parent_declaration_ref'])
    if (review['independent'] is not True or expected_target != target
            or manifest != dict(expected_manifest, target_ref=target_ref)
            or session['target_profile_ref'] != target_ref or session['configuration_ref'] != target['configuration_ref']
            or session['parent_declaration_ref'] != prep['parent_declaration_ref']
            or session['parent'] != dict(cc_name=declaration['identity']['name'],
                cc_version=declaration['identity']['version_label'],declaration_sha256=prep['parent_declaration_ref']['sha256'])
            or any(session[key] != target[key] for key in ('improver_ref','scoring_adapter_ref'))
            or session['qualification']['min_timing_gain'] != target['scoring']['min_relative_gain']
            or session['qualification']['noise_multiplier'] != target['scoring']['noise_multiplier']
            or profile['target_kind'] != preparation_kind(prep) or profile['session_ref'] != session_ref
            or profile['target_ref'] != target_ref or profile['parent_ref'] != prep['parent_ref']
            or profile['memory_mb'] > target['limits']['memory_mb']
            or profile['timeout_s'] > min(target['limits']['time_s'], session['limits']['per_call_s'])
            or any(not 1 <= len(rows) <= MAX_POPULATION for rows in manifest['partitions'].values())):
        raise ValueError('Independent frozen helper calibration scope unavailable')
    children = prep['children']
    if (len(children) != 13 or sum(row['kind'] == 'bad' for row in children) != 10
            or sum(row['kind'] == 'good' for row in children) != 3):
        raise ValueError('Exact planted ranking calibration population required')
    return prep, target, manifest, session, profile


def prepare_calibration_plan(store, *, preparation_ref, review_ref, target_ref,
                             fixture_manifest_ref, session_ref, worker_profile_ref,
                             invocation_wall_s, evidence_wall_s=30, wall_s=3600):
    """Freeze a private collection plan; host approval and qualification follow."""
    require_custodian_store(store)
    refs = dict(preparation_ref=preparation_ref, review_ref=review_ref, target_ref=target_ref,
                fixture_manifest_ref=fixture_manifest_ref, session_ref=session_ref,
                worker_profile_ref=worker_profile_ref)
    prep, target, manifest, session, profile = _scope(store, **refs)
    numeric = (invocation_wall_s, evidence_wall_s, wall_s)
    if (any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in numeric)
            or invocation_wall_s > 300 or profile['timeout_s'] > invocation_wall_s
            or type(wall_s) is not int or wall_s > min(3600, session['limits']['wall_s'])):
        raise ValueError('Bounded calibration wall allocation required')
    repeats = session['pass_count_repeats']
    inventory = calibration_inventory(manifest, repeats)
    total = inventory['total_captures']
    reserved = math.ceil(total * Fraction(str(invocation_wall_s)) + Fraction(str(evidence_wall_s)))
    if total > MAX_INVOCATIONS or reserved > wall_s:
        raise ValueError('Frozen calibration inventory exceeds its bounded allocation')
    collector_ref = store.put_bytes(Path(__file__).read_bytes())
    plan = dict(schema='ai4r-rsi-calibration-plan:1', **refs, collector_ref=collector_ref, **calibration_contexts(target, manifest),
                fixture_identity=prep['fixture_identity'], pass_count_repeats=repeats,
                invocation_wall_s=invocation_wall_s, evidence_wall_s=evidence_wall_s,
                wall_s=wall_s, reserved_wall_s=reserved, expected_invocations=total)
    validate_private(PLAN_SCHEMA, plan)
    return store.put(plan)


class CalibrationLedger:
    """Private calibration exposure, separate from already-calibrated loop sets."""
    def __init__(self, store):
        require_custodian_store(store)
        self.store = store; self.lock = threading.RLock()
        path = store.root / 'calibration.sqlite'
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        os.chmod(path, 0o600)
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
CREATE TABLE IF NOT EXISTS calibration_runs(
 fixture TEXT PRIMARY KEY,plan_ref TEXT NOT NULL,authorization_ref TEXT NOT NULL,
 state TEXT NOT NULL,expected INTEGER NOT NULL,started INTEGER NOT NULL DEFAULT 0,result_ref TEXT);
CREATE TABLE IF NOT EXISTS calibration_slots(
 fixture TEXT NOT NULL,ordinal INTEGER NOT NULL,slot_ref TEXT NOT NULL,
 capture_ref TEXT,PRIMARY KEY(fixture,ordinal));
''')

    def lookup(self, fixture, plan_ref):
        row = self.db.execute('SELECT plan_ref,state,result_ref,started,expected FROM calibration_runs WHERE fixture=?', (fixture,)).fetchone()
        if row is None: return None
        if json.loads(row[0]) != plan_ref:
            raise CalibrationOutcomeUnknown('Calibration lineage already claimed; a changed plan cannot reset exposure')
        return dict(state=row[1], result_ref=json.loads(row[2]) if row[2] else None, started=row[3], expected=row[4])

    def claim(self, fixture, plan_ref, authorization_ref, expected):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                old = self.lookup(fixture, plan_ref)
                if old is None:
                    self.db.execute('INSERT INTO calibration_runs(fixture,plan_ref,authorization_ref,state,expected) VALUES(?,?,?,?,?)',
                        (fixture, encoded(plan_ref).decode(), encoded(authorization_ref).decode(), 'claimed', expected))
                self.db.execute('COMMIT')
                return old is None
            except BaseException:
                self.db.execute('ROLLBACK'); raise

    def reserve(self, fixture, plan_ref, ordinal, slot_ref):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                state = self.lookup(fixture, plan_ref)
                if (state is None or state['state'] not in {'claimed', 'running'}
                        or ordinal != state['started'] + 1 or ordinal > state['expected']):
                    raise CalibrationOutcomeUnknown('Calibration invocation is stale, duplicated or outside the frozen inventory')
                self.db.execute('INSERT INTO calibration_slots VALUES(?,?,?,NULL)', (fixture, ordinal, encoded(slot_ref).decode()))
                self.db.execute('UPDATE calibration_runs SET state=?,started=? WHERE fixture=?', ('running', ordinal, fixture))
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK'); raise

    def complete(self, fixture, ordinal, capture_ref):
        changed = self.db.execute('UPDATE calibration_slots SET capture_ref=? WHERE fixture=? AND ordinal=? AND capture_ref IS NULL',
            (encoded(capture_ref).decode(), fixture, ordinal)).rowcount
        if changed != 1: raise CalibrationOutcomeUnknown('Calibration slot completion is immutable')

    def exposure(self, fixture, plan_ref):
        state = self.lookup(fixture, plan_ref)
        rows = self.db.execute('SELECT ordinal,slot_ref,capture_ref FROM calibration_slots WHERE fixture=? ORDER BY ordinal', (fixture,)).fetchall()
        return {'schema':'ai4r-rsi-calibration-exposure:1', 'plan_ref':plan_ref, 'fixture_identity':fixture,
                'state':state['state'], 'expected_invocations':state['expected'], 'started_invocations':state['started'],
                'slots':[dict(ordinal=row[0],slot_ref=json.loads(row[1]),capture_ref=json.loads(row[2]) if row[2] else None) for row in rows]}

    def finish(self, fixture, plan_ref, result_ref, *, complete):
        state = self.lookup(fixture, plan_ref)
        missing = self.db.execute('SELECT COUNT(*) FROM calibration_slots WHERE fixture=? AND capture_ref IS NULL', (fixture,)).fetchone()[0]
        if state is None or state['state'] not in {'claimed', 'running'}:
            raise CalibrationOutcomeUnknown('Calibration terminal state is immutable')
        if complete and (state['started'] != state['expected'] or missing):
            raise CalibrationOutcomeUnknown('Complete original calibration inventory is unavailable')
        changed = self.db.execute('UPDATE calibration_runs SET state=?,result_ref=? WHERE fixture=? AND result_ref IS NULL',
            ('complete' if complete else 'closed', encoded(result_ref).decode(), fixture)).rowcount
        if changed != 1: raise CalibrationOutcomeUnknown('Calibration terminal state changed concurrently')

    def close(self): self.db.close()


class RankingCalibrationCollector:
    """Host-pinned plan execution. No config flag substitutes for authority."""
    def __init__(self, store, *, ledger, evaluator, qualification, approved_plan_refs):
        require_custodian_store(store)
        if type(ledger) is not CalibrationLedger or ledger.store is not store:
            raise ValueError('Actual protected calibration exposure ledger required')
        if type(evaluator) is not FixtureEvaluator or evaluator.store is not store or type(evaluator.worker) is not WorkerClient:
            raise ValueError('Actual fixture evaluator and authenticated worker client required')
        self.store,self.ledger,self.evaluator,self.qualification = store,ledger,evaluator,qualification
        self.approved = frozenset(encoded(pin) for pin in approved_plan_refs)
        self._lock = asyncio.Lock()

    async def collect(self, plan_ref):
        async with self._lock:
            return await self._collect(plan_ref)

    async def _collect(self, plan_ref):
        require_custodian_store(self.store)
        if encoded(plan_ref) not in self.approved:
            raise ValueError('Root-pinned independent calibration plan approval required')
        plan = self.store.get(plan_ref); validate_private(PLAN_SCHEMA, plan)
        refs = {key:plan[key] for key in ('preparation_ref','review_ref','target_ref','fixture_manifest_ref','session_ref','worker_profile_ref')}
        prep,target,manifest,session,profile = _scope(self.store, **refs)
        expected_plan = prepare_calibration_plan(self.store, **refs, invocation_wall_s=plan['invocation_wall_s'],
            evidence_wall_s=plan['evidence_wall_s'], wall_s=plan['wall_s'])
        if expected_plan != plan_ref: raise ValueError('Frozen calibration plan changed')
        evaluator = self.evaluator; worker = evaluator.worker
        if (evaluator.session_ref != plan['session_ref'] or evaluator.target != target or evaluator.manifest != manifest
                or evaluator.repeats != plan['pass_count_repeats'] or worker.profile_ref != plan['worker_profile_ref']
                or worker.session_ref != plan['session_ref'] or worker.target_kind != profile['target_kind'] or worker.hidden is not True
                or worker.batch_iterations != target['scoring']['batch_iterations']
                or getattr(worker,'process_policy',None)!=profile.get('process_policy')
                or not profile['timeout_s'] <= worker.timeout_s <= plan['invocation_wall_s']):
            raise ValueError('Actual calibration execution owner differs from approved scope')
        fixture = plan['fixture_identity']
        old = self.ledger.lookup(fixture, plan_ref)
        if old is not None:
            if old['result_ref'] is not None: return old['result_ref']
            raise CalibrationOutcomeUnknown('Started calibration has no terminal outcome; automatic replay forbidden')
        candidates = [target['parent_ref'], *[row['body_ref'] for row in prep['children']]]
        proofs = {candidate['sha256']:require_qualification(self.qualification, 'trial', session_ref=plan['session_ref'],
            worker_profile_ref=plan['worker_profile_ref'], candidate_ref=candidate) for candidate in candidates}
        authorization = self.store.put({'schema':'ai4r-rsi-calibration-authorization:1','plan_ref':plan_ref,'proofs':proofs})
        if not self.ledger.claim(fixture, plan_ref, authorization, plan['expected_invocations']):
            raise CalibrationOutcomeUnknown('Calibration was claimed concurrently; automatic replay forbidden')
        evaluator.last_evidence = []
        self._plan,self._plan_ref,self._proofs,self._ordinal = plan,plan_ref,proofs,0
        self._deadline = time.monotonic() + plan['wall_s']
        try:
            async with asyncio.timeout(plan['wall_s']):
                proposal = await self._run(prep,target,manifest)
            exposure = self.store.put(self.ledger.exposure(fixture, plan_ref))
            proposal['evidence_refs'] = [plan_ref,authorization,exposure,plan['review_ref']]
            proposal_ref = self.store.put(proposal)
            result = self.store.put({'schema':'ai4r-rsi-calibration-collection-result:1','status':'UNSIGNED_REVIEW_REQUIRED',
                'plan_ref':plan_ref,'proposal_ref':proposal_ref,'exposure_ref':exposure,'capture_refs':list(evaluator.last_evidence)})
            self.ledger.finish(fixture, plan_ref, result, complete=True)
            return result
        except BaseException as error:
            exposure = self.store.put(self.ledger.exposure(fixture, plan_ref))
            result = self.store.put({'schema':'ai4r-rsi-calibration-collection-result:1',
                'status':'BLOCKED' if isinstance(error,CalibrationNotEstablished) else 'OUTCOME_UNKNOWN',
                'reason':'MEASURED_CALIBRATION_NOT_ESTABLISHED' if isinstance(error,CalibrationNotEstablished) else 'COLLECTION_UNAVAILABLE_RECONCILE',
                'plan_ref':plan_ref,'proposal_ref':None,'exposure_ref':exposure,'capture_refs':list(evaluator.last_evidence)})
            self.ledger.finish(fixture, plan_ref, result, complete=False)
            if isinstance(error,(asyncio.CancelledError,KeyboardInterrupt,SystemExit)): raise
            return result

    async def _batch(self, candidate, split, stage, *, timing=False):
        plan = self._plan; values=[]; elapsed=0; start=len(self.evaluator.last_evidence)
        operation=('timing:' if timing else 'calibration:')+self._plan_ref['sha256']+':'+stage
        for row in self.evaluator.manifest['partitions'][split]:
            scores=[]
            for repeat in range(plan['pass_count_repeats']):
                proof=require_qualification(self.qualification,'trial',session_ref=plan['session_ref'],
                    worker_profile_ref=plan['worker_profile_ref'],candidate_ref=candidate)
                if proof != self._proofs[candidate['sha256']]: raise ValueError('Frozen qualification changed during calibration')
                if time.monotonic()+plan['invocation_wall_s'] > self._deadline-plan['evidence_wall_s']:
                    raise TimeoutError('Reserved calibration execution wall exhausted')
                self._ordinal += 1
                reservation=self.store.put({'schema':'ai4r-rsi-worker-reservation:1','session_ref':plan['session_ref'],
                    'candidate_ref':candidate,'phase':split,'operation':operation,'fixture_id':row['id']})
                slot=self.store.put({'schema':'ai4r-rsi-calibration-slot:1','plan_ref':self._plan_ref,'ordinal':self._ordinal,
                    'stage':stage,'candidate_ref':candidate,'phase':split,'fixture_id':row['id'],'input_ref':row['input_ref'],
                    'reservation_ref':reservation,'repeat_index':repeat,'timing':timing})
                self.ledger.reserve(plan['fixture_identity'],self._plan_ref,self._ordinal,slot)
                before=len(self.evaluator.last_evidence)
                passed,duration=await asyncio.wait_for(self.evaluator.one(candidate,row,split,operation,repeat,timing=timing),
                                                     timeout=plan['invocation_wall_s'])
                if type(passed) is not int or passed not in (0,1) or type(duration) not in (int,float) or not math.isfinite(duration) or duration<=0:
                    raise ValueError('Finite actual calibration score and wall observation required')
                if len(self.evaluator.last_evidence)!=before+1: raise ValueError('Complete unique fixture capture unavailable')
                capture_ref=self.evaluator.last_evidence[-1];capture=self.store.get(capture_ref)
                if (capture['schema']!='ai4r-rsi-fixture-capture:2' or capture['reservation_ref']!=reservation
                        or capture['worker_profile_ref']!=plan['worker_profile_ref'] or capture['input_ref']!=row['input_ref']):
                    raise ValueError('Calibration actual capture differs from reserved slot')
                self.ledger.complete(plan['fixture_identity'],self._ordinal,capture_ref)
                scores.append(passed);elapsed+=duration
            values.append(scores)
        return values,elapsed,list(self.evaluator.last_evidence[start:])

    async def _timing(self,parent,child,stage,expected_parent,expected_child):
        refs=[];times={'parent':[],'child':[]}
        for round_index in range(12):
            order=('parent','child') if round_index%2==0 else ('child','parent')
            for name in order:
                candidate=parent if name=='parent' else child
                values,elapsed,captures=await self._batch(candidate,'hidden_final',f'{stage}:{round_index}:{name}',timing=True)
                if values!=(expected_parent if name=='parent' else expected_child):
                    raise CalibrationNotEstablished('Timed quality differs from the frozen scoring comparison')
                refs.extend(captures)
                if round_index>=5:times[name].append(elapsed)
        return refs,times

    async def _run(self,prep,target,manifest):
        repeats=self._plan['pass_count_repeats'];parent=target['parent_ref']
        expected=[[1]*repeats for _ in manifest['partitions']['hidden_final']]
        noise_refs,noise=await self._timing(parent,parent,'noise',expected,expected)
        observed=max(abs(a-b)/a for a,b in zip(noise['parent'],noise['child']))
        if observed>target['scoring']['calibrated_relative_noise']:
            raise CalibrationNotEstablished('Observed noise exceeds the frozen conservative floor')
        controls=[];rejected=qualified=0
        for control in sorted(prep['children'],key=lambda row:(row['kind']!='bad',row['id'])):
            candidate=control['body_ref'];stage='control:'+control['id']
            mandatory,_,mandatory_refs=await self._batch(candidate,'platform',stage+':mandatory')
            passed=all(all(row) for row in mandatory)
            final_refs=[];timing_refs=[]
            if control['kind']=='bad':
                if passed:raise CalibrationNotEstablished('Planted bad child was not rejected by mandatory checks')
                rejected+=1
            else:
                if not passed:raise CalibrationNotEstablished('Preservation child failed mandatory checks')
                p,_,p_refs=await self._batch(parent,'hidden_final',stage+':parent')
                c,_,c_refs=await self._batch(candidate,'hidden_final',stage+':child')
                final_refs=p_refs+c_refs
                timing_refs,times=await self._timing(parent,candidate,stage,p,c)
                result=qualify(p,c,repeats=repeats,independent=True,parent_times=times['parent'],child_times=times['child'],
                    warmups=5,calibrated_noise=target['scoring']['calibrated_relative_noise'],
                    min_timing_gain=target['scoring']['min_relative_gain'],noise_multiplier=target['scoring']['noise_multiplier'])
                if result['outcome']!='QUALIFIED':raise CalibrationNotEstablished('Measured preservation-child headroom unavailable')
                qualified+=1
            controls.append(self.store.put({'schema':'ai4r-rsi-calibration-control:1','preparation_ref':self._plan['preparation_ref'],
                'candidate_ref':candidate,'mandatory_capture_refs':mandatory_refs,'final_capture_refs':final_refs,'timing_capture_refs':timing_refs}))
        if self._ordinal!=self._plan['expected_invocations']:raise ValueError('Calibration inventory differs from frozen plan')
        return dict(schema='ai4r-rsi-calibration:2',**calibration_contexts(target,manifest),
            preparation_ref=self._plan['preparation_ref'],review_ref=self._plan['review_ref'],pass_count_repeats=repeats,
            noise_capture_refs=noise_refs,control_refs=controls,known_bad_rejected=rejected,known_good_qualified=qualified,
            measurable_headroom=True,evidence_refs=[])
