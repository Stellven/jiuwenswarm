"""Exact-byte protected references and source-backed request validation."""
import hashlib
import json
import math
import os
import stat
from pathlib import Path, PurePosixPath


CATEGORIES = frozenset(("ml_methods_and_inference", "retrieval_and_knowledge_systems",
    "algorithms_optimization_and_formal", "software_systems_and_performance",
    "databases_and_data_processing", "networking_and_distributed_algorithms",
    "security_and_reliability", "experimental_evaluation_and_technical_data"))


class IntegrityFault(ValueError):
    def __init__(self, check="invalid_protected_context"):
        self.check = check
        super().__init__(check)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json(data):
    def duplicate(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise IntegrityFault("duplicate_json_key")
            result[k] = v
        return result
    try:
        return json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=duplicate,
                          parse_constant=lambda _: (_ for _ in ()).throw(IntegrityFault("nonfinite_json")))
    except (ValueError, UnicodeError, TypeError) as exc:
        if isinstance(exc, IntegrityFault): raise
        raise IntegrityFault("invalid_json") from None


class ProtectedData:
    def __init__(self, roots, max_bytes=4 * 1024 * 1024, ref_index=None,ref_index_path=None):
        self.roots = [Path(x).resolve(strict=True) for x in roots]
        self.max_bytes = max_bytes
        self.ref_index = dict(ref_index or {})
        self.ref_index_path=Path(ref_index_path) if ref_index_path is not None else None

    def read_ref(self, ref):
        if not isinstance(ref, dict) or set(ref) != {"id", "sha256"}:
            raise IntegrityFault("invalid_ref")
        name, digest = ref["id"], ref["sha256"]
        index=self.ref_index
        if self.ref_index_path is not None:
            p=self.ref_index_path
            if not p.is_absolute() or any(v.is_symlink() for v in (p,*p.parents)):raise IntegrityFault('ref_index_scope')
            fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
            try:
                info=os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size>self.max_bytes or info.st_mode&0o022:raise IntegrityFault('ref_index_custody')
                with os.fdopen(fd,'rb',closefd=False) as stream:value=strict_json(stream.read(self.max_bytes+1))
            finally:os.close(fd)
            if not isinstance(value,dict) or set(value)!={'schema','refs'} or value['schema']!='ai4r-router-public-index:1' or not isinstance(value['refs'],dict):raise IntegrityFault('ref_index_structure')
            index={**index,**value['refs']}
        if name in index:
            location = index[name]
            if location.get("sha256") != digest: raise IntegrityFault("indexed_ref_digest")
            name = location["path"]
        if not isinstance(name, str) or not name or "\\" in name or ":" in name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            raise IntegrityFault("ref_scope")
        if not isinstance(digest, str) or len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
            raise IntegrityFault("invalid_ref_digest")
        for root in self.roots:
            candidate = root / name
            if not candidate.exists(): continue
            if any(x.is_symlink() for x in [candidate, *list(candidate.parents)[:len(candidate.parts)-len(root.parts)]]):
                raise IntegrityFault("ref_symlink")
            target = candidate.resolve(strict=True)
            if not target.is_relative_to(root) or not target.is_file(): raise IntegrityFault("ref_scope")
            fd=os.open(target,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
            try:
                info=os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>self.max_bytes:raise IntegrityFault('ref_size')
                with os.fdopen(fd,'rb',closefd=False) as stream:data=stream.read(self.max_bytes+1)
            finally:os.close(fd)
            if len(data) > self.max_bytes or hashlib.sha256(data).hexdigest() != digest:
                raise IntegrityFault("ref_digest_mismatch")
            return data
        raise IntegrityFault("ref_missing")

    def read_json(self, ref):
        return strict_json(self.read_ref(ref))


def validate_request(request, data, validate):
    try:
        validate("route-request", request)
        selected = request["selected_capsule"]
        validate("selected-capsule-input", selected)
        declaration = data.read_json(selected["declaration_ref"])
        validate("capsule-declaration", declaration)
        if declaration != selected["declaration"]: raise IntegrityFault("declaration_bytes")
        if request["domain"] != "cs_ml" or request["task_category"] not in CATEGORIES:
            raise IntegrityFault("unsupported_category")
        if request["call_function"] not in {"worker", "verifier", "planner"} or "role" in request:
            raise IntegrityFault("unsupported_call_function")
        context = selected["bound_context"]
        if context["eligibility"] != "eligible": raise IntegrityFault("frozen_binding_ineligible")
        for key in ("policy_ref",):
            if request[key] != context[key]: raise IntegrityFault("bound_policy_mismatch")
        bound_inputs = [ref for item in context["inputs"] for ref in item["artifact_refs"]]
        if request["input_refs"] != bound_inputs: raise IntegrityFault("bound_inputs_mismatch")
        for ref in bound_inputs:data.read_ref(ref)
        for item in context["inputs"]:
            if item["required"] and not item["artifact_refs"]: raise IntegrityFault("missing_bound_input")
        for key in ("implementation_refs", "overlay_refs", "dependency_refs"):
            for ref in context[key]: data.read_ref(ref)
        body_hashes = {x["sha256"] for x in declaration["identity"]["body"]}
        if not body_hashes <= {x["sha256"] for x in context["implementation_refs"]}:
            raise IntegrityFault("implementation_closure")
        for key in ("node_contract_ref", "subnode_contract_ref"):
            contract = data.read_json(selected[key])
            validate("node-execution-contract" if key == "node_contract_ref" else "subnode-execution-contract", contract)
            runtime = context["runtime"]
            for identity in ("run_id", "node_id", "subnode_id", "attempt_id"):
                if identity in contract and contract[identity] != runtime[identity]: raise IntegrityFault("contract_runtime_mismatch")
            if key == "node_contract_ref":
                for source, captured in (("node_limits", "node_limits"), ("policy_ref", "policy_ref"), ("configuration_ref", "configuration_ref")):
                    if contract[source] != context[captured]: raise IntegrityFault("node_context_mismatch")
            else:
                if contract["node_contract_ref"] != selected["node_contract_ref"] or contract["subnode_limits"] != context["subnode_limits"]:
                    raise IntegrityFault("subnode_parent_mismatch")
                for key in ('inputs','outputs','policy_ref','configuration_ref'):
                    if contract[key]!=context[key]:raise IntegrityFault('subnode_context_mismatch')
                bindings = [x for x in contract["bindings"] if x["id"] == context["binding_id"]]
                if len(bindings) != 1: raise IntegrityFault("binding_identity")
                bound = bindings[0]
                for source, captured in (("role", "role"), ("implementation_refs", "implementation_refs"),
                    ("dependency_refs", "dependency_refs"), ("admission_ref", "admission_ref"),
                    ("effective_authority", "effective_authority"), ("limits", "invocation_limits")):
                    if bound[source] != context[captured]: raise IntegrityFault("binding_context_mismatch")
                if bound["declaration_ref"] != selected["declaration_ref"]: raise IntegrityFault("binding_declaration")
        admission = data.read_json(context["admission_ref"])
        validate("library-admission", admission)
        if admission.get("status") != "admitted":
            raise IntegrityFault("admission_not_admitted")
        expected_cc={'cc_name':declaration['identity']['name'],'cc_version':declaration['identity']['version_label'],
            'declaration_sha256':selected['declaration_ref']['sha256']}
        if admission['cc']!=expected_cc or admission['candidate_ref']!=selected['declaration_ref'] or not admission['check_pins'] or not admission['memory_mb']:
            raise IntegrityFault('admission_identity_mismatch')
        if context['invocation_limits']['memory_mb']>admission['memory_mb']:raise IntegrityFault('admission_memory_exceeded')
        # Standing is captured by the frozen library snapshot (M1-I002), not reread from mutable live state.
        for item in context["prerequisite_results"]:
            if item["status"] not in {"pass", "deferred"}: raise IntegrityFault("invalid_prerequisite")
        return context
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, IntegrityFault): raise
        raise IntegrityFault("invalid_protected_context") from None

