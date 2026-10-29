"""Every declared clause is accounted for; missing capture is unavailable."""
from datetime import datetime, timezone
import json
import uuid


def declared_clauses(declaration):
    for direction in ("inputs","outputs"):
        for row in declaration["ports"][direction]: yield "port", "ports."+direction+"."+row["name"], row
    needs=declaration["needs"]
    yield "need","needs.network",needs["network"]
    for key,identity in (("resources","resource_key"),("external","identifier"),("injects","service_key")):
        for row in needs.get(key,[]): yield "need","needs."+key+"."+row[identity],row
    for row in declaration["changes"]["effects"]: yield "effect","changes.effects."+row["id"],row
    for row in declaration["guarantees"]["checks"]: yield "check","guarantees.checks."+row["id"],row
    for row in declaration["guarantees"]["failure_modes"]: yield "failure_mode","guarantees.failure_modes."+row["reason_code"],row


def build_conformance(record, declaration, records_ref, declaration_ref, observations, *, evidence_refs=()):
    if record["declaration_sha256"] != declaration_ref["sha256"]: raise ValueError("declaration observation mismatch")
    items=[]; unavailable=[]; declared=set()
    for kind,key,clause in declared_clauses(declaration):
        declared.add(key); observed=observations.get(key)
        if observed is None:
            status,value="unavailable",None;unavailable.append(key+": required raw observation missing")
        else:
            status=observed["status"];value=observed.get("observed")
            if status not in {"matched","mismatched","unused","unavailable"}: raise ValueError("invalid declared observation status")
            if status in {"unused","unavailable"}: value=None
            elif not isinstance(value,str) or not value: raise ValueError("measured observation required")
            if status=="unavailable": unavailable.append(key+": "+observed.get("reason","raw observation unavailable"))
        items.append({"clause_kind":kind,"clause_id":key,"declared":json.dumps(clause,ensure_ascii=False,sort_keys=True)[:500],"observed":value[:500] if value else None,"status":status})
    for key,observed in observations.items():
        if key not in declared:
            value=observed.get("observed")
            if not value: raise ValueError("undeclared behavior needs raw observation")
            items.append({"clause_kind":observed["clause_kind"],"clause_id":key,"declared":None,"observed":value[:500],"status":"undeclared"})
    if len(items)>200 or len(unavailable)>50: raise ValueError("conformance exceeds source representation bounds")
    observed_count=sum(x["status"] in {"matched","mismatched","undeclared"} for x in items)
    accounted=sum(x["status"] in {"matched","mismatched"} for x in items)
    return {"schema_version":"1.0.0","id":"conformance:"+uuid.uuid4().hex,
        **{k:record[k] for k in ("run_id","node_id","attempt_id","subnode_id","cc_name","cc_version","declaration_sha256")},
        "observation_id":record["id"],"records_ref":records_ref,"declaration_ref":declaration_ref,
        "built_at":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"items":items,
        "undeclared_count":sum(x["status"]=="undeclared" for x in items),
        "unused_count":sum(x["status"]=="unused" for x in items),
        "coverage":round(accounted/observed_count,6) if observed_count else None,
        "evidence_refs":list(evidence_refs),"unavailable_reasons":unavailable}

