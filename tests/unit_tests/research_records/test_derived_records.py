from copy import deepcopy

import pytest

from jiuwenswarm.research_records.scorecard import build_scorecard
from jiuwenswarm.research_records.conformance import build_conformance
from jiuwenswarm.research_records.export import export_label, content_hash


def record(ident="obs:a", failure="none"):
    return {"id": ident, "run_id": "run:a", "node_id": "n", "attempt_id": "a1", "subnode_id": None,
            "cc_name": "research.screening", "cc_version": "v1", "declaration_sha256": "a" * 64,
            "failure_class": failure, "duration_s": None, "model_calls": [], "check_results": [],
            "failure_reason_code": None, "error_fingerprint": None,
            "gate_verdict": "PASS" if failure == "none" else "FAIL"}


def test_scorecard_denominator_excludes_infrastructure_and_scientific_not_capsule():
    rows = [record("obs:1"), record("obs:2", "infrastructure"), record("obs:3", "scientific"), record("obs:4", "capsule")]
    out = build_scorecard(rows, {"id": "records.jsonl", "sha256": "b" * 64})
    assert out["execution_count"] == 4 and out["counted_count"] == 2
    assert out["gate_pass_rate"] == .5 and out["median_duration_s"] is None
    assert out["release_authority"] == "none" and out["median_total_tokens"] is None
    assert out["unavailable_reasons"]


def test_mixed_versions_and_duplicate_observations_are_refused():
    a, b = record(), record("obs:b"); b["cc_version"] = "v2"
    with pytest.raises(ValueError): build_scorecard([a,b], {"id": "r", "sha256": "a" * 64})
    with pytest.raises(ValueError): build_scorecard([a,a], {"id": "r", "sha256": "a" * 64})


def test_missing_effect_observation_is_unavailable_not_unused():
    r = record(); d = {"ports": {"inputs": [], "outputs": []},
       "needs": {"network": {"mode": "none"}, "resources": [], "external": [], "injects": []},
       "changes": {"effects": [{"id": "write", "scope": "workspace"}]},
       "guarantees": {"checks": [], "failure_modes": []}}
    out = build_conformance(r, d, {"id":"records.jsonl","sha256":"b"*64}, {"id":"decl","sha256":"a"*64}, {})
    effect = next(x for x in out["items"] if x["clause_kind"] == "effect")
    assert effect["status"] == "unavailable" and effect["observed"] is None
    assert out["coverage"] is None


def test_export_split_null_is_dash_and_content_order_is_byte_order():
    assert export_label("r", "n", "a", None) == export_label("r", "n", "a", "-")
    files=[{"path":"b", "sha256":"b"*64},{"path":"a", "sha256":"a"*64}]
    assert content_hash(files) == content_hash(list(reversed(files)))
    with pytest.raises(ValueError): content_hash([{"path":"../escape", "sha256":"a"*64}])


def test_builder_requires_completed_snapshot_and_exact_original_gate_join(tmp_path):
    import hashlib
    import json
    from jiuwenswarm.research_records.builder import DerivedBuilder
    blobs={};rows=[]
    def capture(kind,value):
        raw=json.dumps(value,sort_keys=True).encode();digest=hashlib.sha256(raw).hexdigest()
        pin={'id':kind+':'+str(len(rows)),'sha256':digest};blobs[pin['id']]=raw
        rows.append({'kind':kind,'record':value,'ref':pin});return pin
    original=record();original['failure_class']=None
    raw_ref=capture('invocation-observation',original)
    completed={**original,'failure_class':'none','check_result_refs':[]}
    completed_ref=capture('capsule-run-record',completed)
    gate_ref=capture('gate-decision',{'invocation_refs':[raw_ref],'scope_kind':'subnode','verdict':'PASS'})
    snapshot=json.dumps(completed,sort_keys=True).encode()+b'\n'
    records_ref={'id':'snapshots/current/records.jsonl','sha256':hashlib.sha256(snapshot).hexdigest()};blobs[records_ref['id']]=snapshot
    capture('capsule-run-record-link',{'observation_ref':raw_ref,'completed_ref':completed_ref,
        'decision_refs':[gate_ref],'assessment_refs':[],'records_snapshot_ref':records_ref})
    class Source:
        def iter_records(self):return iter(rows)
        def read_blob(self,pin):
            raw=blobs[pin['id']]
            assert hashlib.sha256(raw).hexdigest()==pin['sha256'];return raw
    source=Source();builder=DerivedBuilder(tmp_path,lambda *_:None)
    built=builder.scorecards(source,records_ref)
    assert built[0]['status']=='built'
    out=json.loads(__import__('pathlib').Path(built[0]['path']).read_bytes())
    assert out['execution_count']==1 and out['verdict_counts']['PASS']==1
    rows[2]['record']['invocation_refs']=[completed_ref]
    assert builder.scorecards(source,records_ref)[0]['status']=='unavailable'


def test_builder_never_counts_a_pre_gate_raw_capture(tmp_path):
    import hashlib
    from jiuwenswarm.research_records.builder import DerivedBuilder
    raw=b'';pin={'id':'records.jsonl','sha256':hashlib.sha256(raw).hexdigest()}
    class Source:
        def iter_records(self):return iter([{'kind':'invocation-observation','ref':pin,'record':record()}])
        def read_blob(self,_):return raw
    assert DerivedBuilder(tmp_path,lambda *_:None).scorecards(Source(),pin)==[]

