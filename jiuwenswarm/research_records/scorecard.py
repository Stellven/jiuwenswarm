"""Source-defined reporting denominators; no release or selection authority."""
from collections import Counter
from datetime import datetime, timezone
import math
from statistics import median
import uuid


def _measured(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def build_scorecard(records, records_ref, *, conformance=(), conformance_refs=(), downstream_edges=None,gate_verdicts=None,check_results=None):
    records = list(records)
    conformance=list(conformance)
    gate_verdicts=gate_verdicts or {};check_results=check_results or {}
    if not 1 <= len(records) <= 5000: raise ValueError("scorecard population outside source bounds")
    triples = {(x["cc_name"],x["cc_version"],x["declaration_sha256"]) for x in records}
    if len(triples) != 1 or len({x["id"] for x in records}) != len(records): raise ValueError("mixed or duplicate population")
    run_ids = sorted({x["run_id"] for x in records})
    if len(run_ids) > 500: raise ValueError("too many runs")
    classes = Counter(x["failure_class"] for x in records)
    allowed_classes = ("none","capsule","input","infrastructure","scientific")
    if set(classes)-set(allowed_classes): raise ValueError("unknown captured failure class")
    counted = len(records)-classes["infrastructure"]-classes["scientific"]
    verdicts = ("PASS","PASS_WITH_KNOWN_LIMITATIONS","FAIL","ENVIRONMENT_BLOCKED","INCONCLUSIVE")
    verdict_counts = Counter(gate_verdicts.get(x['id'],x.get("gate_verdict")) for x in records if gate_verdicts.get(x['id'],x.get("gate_verdict")))
    if set(verdict_counts)-set(verdicts): raise ValueError("unknown captured gate verdict")
    check_counts = {}
    for record in records:
        for check in check_results.get(record['id'],record.get("check_results", [])):
            status=check.get('outcome',check.get('status'))
            if status == "NOT_RUN": continue
            pair=check_counts.setdefault(check["check_id"], [0,0]);pair[0]+=1;pair[1]+=status=="PASS"
    if len(check_counts)>64: raise ValueError("too many distinct declared checks")
    reasons=Counter(x["failure_reason_code"] for x in records if x.get("failure_reason_code"))
    fingerprints=Counter(x["error_fingerprint"] for x in records if x.get("error_fingerprint"))
    durations=[x["duration_s"] for x in records if _measured(x.get("duration_s"))]
    token_totals=[]
    for record in records:
        usage=record.get("usage")
        if isinstance(usage,dict) and all(_measured(usage.get(k)) for k in ("input_tokens","output_tokens")):
            token_totals.append(usage["input_tokens"]+usage["output_tokens"])
    coverages=[x["coverage"] for x in conformance if _measured(x.get("coverage"))]
    attempts={}
    for record in records: attempts.setdefault((record["run_id"],record["node_id"]),set()).add(record["attempt_id"])
    unavailable=[]
    if sum(verdict_counts.values())<len(records):unavailable.append('verdict_counts: some exact committed gate joins unavailable')
    if not durations: unavailable.append("median_duration_s: no measured execution duration")
    if not token_totals: unavailable.append("median_total_tokens: no complete attributable token observation")
    if not coverages: unavailable.append("mean_declaration_coverage: no measured conformance")
    if counted==0: unavailable.append("gate_pass_rate: no counted executions")
    next_rate=None
    if downstream_edges is None:
        unavailable.append("next_node_acceptance_rate: downstream accepted-output joins unavailable")
    else:
        ids={x["id"] for x in records}
        edges=[x for x in downstream_edges if x["producer_observation_id"] in ids]
        if edges: next_rate=round(sum(x["consumer_advanced"] is True for x in edges)/len(edges),6)
        else: unavailable.append("next_node_acceptance_rate: no consumed output in the window")
    name,version,digest=next(iter(triples))
    return {"schema_version":"1.0.0","id":"scorecard:"+uuid.uuid4().hex,
        "cc_name":name,"cc_version":version,"declaration_sha256":digest,
        "built_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"records_ref":records_ref,
        "conformance_refs":list(conformance_refs),"record_ids":[x["id"] for x in records],"run_ids":run_ids,
        "release_authority":"none","execution_count":len(records),"class_counts":{k:classes[k] for k in allowed_classes},
        "counted_count":counted,"gate_pass_rate":round(classes["none"]/counted,6) if counted else None,
        "verdict_counts":{k:verdict_counts[k] for k in verdicts},
        "check_rates":[{"check_id":k,"executed":v[0],"passed":v[1],"pass_rate":round(v[1]/v[0],6) if v[0] else None} for k,v in sorted(check_counts.items())],
        "failure_reasons":[{"reason":k,"count":v} for k,v in sorted(reasons.items(),key=lambda x:(-x[1],x[0]))[:20]],
        "error_fingerprints":[{"error_fingerprint":k,"count":v} for k,v in sorted(fingerprints.items(),key=lambda x:(-x[1],x[0]))[:20]],
        "undeclared_behavior_count":sum(x["undeclared_count"] for x in conformance),
        "mean_declaration_coverage":round(sum(coverages)/len(coverages),6) if coverages else None,
        "next_node_acceptance_rate":next_rate,"median_duration_s":median(durations) if durations else None,
        "median_total_tokens":median(token_totals) if token_totals else None,
        "median_attempts":median([len(x) for x in attempts.values()]) if attempts else None,
        "unavailable_reasons":unavailable}

