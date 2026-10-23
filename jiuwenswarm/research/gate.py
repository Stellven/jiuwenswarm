"""Protected checking, isolated semantic review and durable gate records."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import uuid
import zipfile
from typing import Mapping

from .contracts import Ref, ResearchError, validate
from .state import json_bytes, utc_now


ADVANCING = {"PASS", "PASS_WITH_KNOWN_LIMITATIONS"}
OUTCOMES = {"PASS", "FAIL", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE"}


def zip_projection(data: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(set(names)) != len(names):
                raise ValueError("duplicate entries")
            blocks = []
            for entry in sorted(entries, key=lambda e: e.filename.encode("utf-8")):
                if (entry.is_dir() or entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16)
                        or entry.file_size > 256 * 1024):
                    raise ValueError("unsupported archive entry")
                raw = archive.read(entry)
                text = raw.decode("utf-8", errors="strict")
                blocks.append(f"path: {entry.filename}\nsha256: {hashlib.sha256(raw).hexdigest()}\nsize: {len(raw)}\n---\n{text}\n===\n")
            return "".join(blocks).encode("utf-8")
    except (ValueError, UnicodeError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ResearchError("projection_failed", "Captured zip cannot be projected under the pinned rule") from exc


def assemble_assessment(reply: Mapping, criteria: list[dict], declaration_ref: Ref,
                        subject_ref: Ref, review_context_ref: Ref) -> dict:
    if not isinstance(reply, dict) or set(reply) != {"findings", "uncertainties", "limitations", "required_correction"}:
        raise ResearchError("assessment_invalid", "Verifier reply must contain only untrusted finding bodies")
    expected = [c["criterion_id"] for c in criteria]
    findings = reply["findings"]
    if (not expected or len(set(expected)) != len(expected) or not isinstance(findings, list)
            or len(findings) != len(expected)):
        raise ResearchError("criterion_coverage_exact", "Missing or duplicate verifier criterion")
    ids = []
    bodies = []
    for finding in findings:
        if (not isinstance(finding, dict) or set(finding) != {"criterion_id", "outcome", "reason"}
                or finding.get("outcome") not in OUTCOMES or not isinstance(finding.get("reason"), str)
                or not finding["reason"].strip()):
            raise ResearchError("assessment_invalid", "Malformed criterion finding")
        ids.append(finding["criterion_id"])
        bodies.append(dict(finding, evidence_refs=[declaration_ref, subject_ref]))
    if set(ids) != set(expected) or len(set(ids)) != len(ids):
        raise ResearchError("criterion_coverage_exact", "Missing, duplicate or unknown verifier criterion")
    for key in ("uncertainties", "limitations"):
        if not isinstance(reply[key], list) or any(not isinstance(x, str) for x in reply[key]):
            raise ResearchError("assessment_invalid", "Malformed review limitations")
    blocking = {c["criterion_id"] for c in criteria if c["blocking"]}
    failed = [f["outcome"] for f in bodies if f["criterion_id"] in blocking and f["outcome"] != "PASS"]
    if failed:
        verdict = next(kind for kind in ("FAIL", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE") if kind in failed)
    elif all(f["outcome"] == "PASS" for f in bodies) and not reply["uncertainties"] and not reply["limitations"]:
        verdict = "PASS"
    else:
        verdict = "PASS_WITH_KNOWN_LIMITATIONS"
    if verdict in ADVANCING and reply["required_correction"] is not None:
        raise ResearchError("verdict_follows_findings", "An advancing review cannot require correction")
    record = {"schema_version": "1.0.0", "subject_ref": subject_ref,
              "review_context_ref": review_context_ref, "verdict": verdict, "findings": bodies,
              "uncertainties": reply["uncertainties"], "limitations": reply["limitations"],
              "required_correction": reply["required_correction"]}
    validate("verifier-assessment", record)
    return record


class SemanticVerifier:
    def __init__(self, store):
        self.store = store

    async def review(self, declaration_ref: Ref, output_ref: Ref, profile_ref: Ref,
                     review_context_ref: Ref, port: str, invoke, *, zip_output: bool = False) -> Ref:
        declaration = self.store.read_blob(declaration_ref)
        output = self.store.read_blob(output_ref)
        profile = self.store.read_record(profile_ref, contract_id="checking-profile")
        if profile["model_call_limit"] != 1:
            raise ResearchError("verifier_budget", "M1 semantic review uses exactly one call")
        criteria = [c for c in profile["criteria"] if c["target_port"] in (None, port)]
        instructions = self.store.read_blob(profile["instruction_ref"]).decode("utf-8")
        # Criteria are independently pinned instruction material, never a worker input.
        instructions += "\nCriteria for this output:\n" + json.dumps(criteria, ensure_ascii=False)
        subject_ref = output_ref
        if zip_output:
            output = zip_projection(output)
            subject_ref = self.store.put_blob(output, media_type="text/plain;charset=utf-8")
        payload = {"subject_declaration": declaration.decode("utf-8"), "subject_output": output.decode("utf-8")}
        raw = await invoke(json.dumps(payload, ensure_ascii=False), system=instructions)
        try:
            reply = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ResearchError("assessment_invalid", "Verifier returned malformed JSON") from exc
        assessment = assemble_assessment(reply, criteria, declaration_ref, subject_ref, review_context_ref)
        return self.store.put_record("verifier-assessment", assessment,
                                     record_id="assessment:" + uuid.uuid4().hex)


class ProtectedGate:
    def __init__(self, store):
        self.store = store

    def decide(self, contract_ref: Ref, check_plan_ref: Ref, deterministic_ref: Ref,
               assessment_ref: Ref | None, output_refs: list[Ref], invocation_refs: list[Ref], *,
               output_port: str | None = None, scope_kind: str = "subnode",
               internal_decision_refs: list[Ref] | None = None, halt_reason: str | None = None,verifier_check_ref: Ref | None = None,persist: bool = True) -> Ref | dict:
        contract = self.store.read_record(contract_ref)
        plan = self.store.read_record(check_plan_ref, contract_id="bound-check-plan")
        deterministic = self.store.read_record(deterministic_ref, contract_id="deterministic-check-result")
        if plan["contract_ref"] != contract_ref or deterministic["check_plan_ref"] != check_plan_ref:
            raise ResearchError("integrity_fault", "Check evidence belongs to another frozen subject")
        expected = plan["mandatory_deterministic"]
        results = deterministic["results"]
        ids = [r["check_id"] for r in results]
        valid_checks = len(ids) == len(set(ids)) and set(expected).issubset(ids) and all(
            r["outcome"] == "PASS" for r in results if r["check_id"] in expected)
        verdict = "FAIL"
        reasons = []
        if not valid_checks:
            reasons.append("Mandatory deterministic checks did not all pass")
        if halt_reason:
            reasons.append(halt_reason)
        if valid_checks and assessment_ref and output_refs and invocation_refs and not halt_reason:
            if scope_kind=='subnode':
                if verifier_check_ref is None:raise ResearchError('verifier_check_binding','Advancing review needs independently captured verifier mechanical checks')
                checked=self.store.read_record(verifier_check_ref,contract_id='deterministic-check-result')
                checkedplan=self.store.read_record(checked['check_plan_ref'],contract_id='bound-check-plan')
                checkedcontract=self.store.read_record(checkedplan['contract_ref'],contract_id='subnode-execution-contract')
                keys=[row['check_id'] for row in checked['results']]
                if (checked['subject_ref']!=assessment_ref or checkedcontract['node_contract_ref']!=contract['node_contract_ref']
                    or checkedcontract['bindings'][0]['role']!='verifier' or len(keys)!=len(set(keys))
                    or set(keys)!=set(checkedplan['mandatory_deterministic']) or any(row['outcome']!='PASS' for row in checked['results'])):
                    raise ResearchError('verifier_check_binding','Verifier checks do not match the independently budgeted invocation and assessment')
            assessment = self.store.read_record(assessment_ref, contract_id="verifier-assessment")
            manifest = self.store.read_record(assessment["review_context_ref"], contract_id="review-context")
            allowed_plans=[check_plan_ref]
            if scope_kind=='node':
                allowed_plans.extend(self.store.read_record(r,contract_id='gate-decision')['check_plan_ref'] for r in (internal_decision_refs or []))
            if manifest.get("check_plan_ref") not in allowed_plans:
                raise ResearchError("integrity_fault", "Assessment manifest names another bound check plan")
            reviewed=list(output_refs)
            if scope_kind=='node':
                reviewed.extend(o for r in (internal_decision_refs or []) for o in self.store.read_record(r)['output_refs'])
            if assessment["subject_ref"] not in reviewed:
                projection_matches=False
                for original in reviewed:
                    try:
                        projected=zip_projection(self.store.read_blob(original))
                        projection_matches=projection_matches or hashlib.sha256(projected).hexdigest()==assessment['subject_ref']['sha256']
                    except ResearchError:
                        continue
                if not projection_matches:raise ResearchError("integrity_fault", "Assessment reviews different bytes")
                self.store.read_blob(assessment['subject_ref'])
            subject_contract=contract
            if scope_kind=='node':
                matches=[self.store.read_record(r) for r in (internal_decision_refs or []) if self.store.read_record(r)['assessment_ref']==assessment_ref]
                if not matches:raise ResearchError('integrity_fault','Aggregate assessment is not an internal accepted review')
                subject_contract=self.store.read_record(matches[0]['contract_ref']);reviewed_port=matches[0]['output_port']
            declaration_ref=subject_contract['bindings'][0]['declaration_ref']
            profile=self.store.read_record(subject_contract['checking_profile_ref'],contract_id='checking-profile')
            criteria=[c for c in profile['criteria'] if c['target_port'] in (None,output_port if scope_kind=='subnode' else reviewed_port)]
            reply={key:assessment[key] for key in ('uncertainties','limitations','required_correction')}
            reply['findings']=[{key:f[key] for key in ('criterion_id','outcome','reason')} for f in assessment['findings']]
            rebuilt=assemble_assessment(reply,criteria,declaration_ref,assessment['subject_ref'],assessment['review_context_ref'])
            if rebuilt!=assessment:raise ResearchError('integrity_fault','Assessment identities, evidence or verdict do not follow the exact pinned profile')
            verdict = assessment["verdict"]
            if verdict not in ADVANCING:
                reasons.extend(f["criterion_id"] + ': ' + f["reason"] for f in assessment["findings"]
                               if f["outcome"] != 'PASS')
                if assessment.get('required_correction'):
                    reasons.append('Required correction: ' + assessment['required_correction'])
                if not reasons:
                    reasons.append('Semantic assessment did not authorize advancement: ' + verdict)
        internal_decision_refs = internal_decision_refs or []
        if scope_kind == "node":
            if not internal_decision_refs:
                reasons.append("No internal acceptance decisions")
                verdict = "FAIL"
            for ref in internal_decision_refs:
                child = self.store.read_record(ref, contract_id="gate-decision")
                if child["node_contract_ref"] != contract_ref or child["action"] != "advance":
                    reasons.append("Internal subnode did not advance")
                    verdict = "FAIL"
        if not output_refs or not invocation_refs:
            verdict = "FAIL"
            reasons.append("Required output or invocation evidence is missing")
        action = "advance" if verdict in ADVANCING and not reasons else "halt"
        if action == "halt" and verdict in ADVANCING:
            verdict = "FAIL"
        reasons = reasons or (["All mandatory checks and semantic criteria passed"] if action == 'advance'
                              else ["No advancing semantic assessment is available"])
        for ref in [*output_refs, *invocation_refs]:
            self.store.read_blob(ref)
        record = {"schema_version": "2.0.0", "id": "gate:" + uuid.uuid4().hex,
                  "recorded_at": utc_now(), "run_id": contract["run_id"], "node_id": contract["node_id"],
                  "attempt_id": contract["attempt_id"], "contract_ref": contract_ref,
                  "node_contract_ref": contract_ref if scope_kind == "node" else contract["node_contract_ref"],
                  "scope_kind": scope_kind, "subnode_id": None if scope_kind == "node" else contract["subnode_id"],
                  "output_port": output_port, "internal_decision_refs": internal_decision_refs,
                  "invocation_refs": invocation_refs, "policy_ref": contract["policy_ref"],
                  "check_plan_ref": check_plan_ref, "input_refs": contract["input_refs"],
                  "output_refs": output_refs, "deterministic_result_ref": deterministic_ref,
                  "assessment_ref": assessment_ref, "verdict": verdict,
                  "reasons": [{"code": "gate_" + action, "message": message, "criterion_ids": [],
                               "evidence_refs": [deterministic_ref,*([verifier_check_ref] if verifier_check_ref else [])]} for message in reasons],
                  "action": action, "accepted_refs": output_refs if action == "advance" else []}
        validate('gate-decision',record)
        return self.store.put_record("gate-decision", record) if persist else record
