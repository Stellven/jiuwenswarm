"""Protected, bounded decision transaction. Never dispatches a model."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import uuid

from .catalog import QualifiedCatalog, CatalogError
from .claims import ClaimConflict, ClaimStore
from .policy import NoRoute, choose, budget_compatible
from .profiles import validate_profile
from .request_validation import IntegrityFault, json_bytes, validate_request


def utc(now=None):
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _shared_audit_directory(path,group=None):
    path=Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
        raise IntegrityFault('audit_directory_scope')
    path.mkdir(parents=True,exist_ok=True,mode=0o2750)
    if os.name=='posix':
        descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            metadata=os.fstat(descriptor)
            if metadata.st_uid!=os.geteuid() or metadata.st_mode&0o022 or group is not None and metadata.st_gid!=group:
                raise IntegrityFault('audit_directory_custody')
            os.fchmod(descriptor,0o2750)
            return metadata.st_gid
        finally:os.close(descriptor)
    return None


class DecisionEngine:
    def __init__(self, *, data, validate, audit_root, catalog_ref, profile_refs,
                 development_profiles_ref, adapter_revision, preflight=None):
        self.data, self.validate = data, validate
        self.audit_root = Path(audit_root)
        self.audit_group=_shared_audit_directory(self.audit_root)
        self.store = ClaimStore(self.audit_root / "audit.sqlite")
        self.catalog_ref = catalog_ref
        self.profile_refs = profile_refs
        self.development_profiles_ref = development_profiles_ref
        self.adapter_revision = adapter_revision
        self.preflight = preflight or (lambda request, candidate: True)

    def capture(self, value):
        encoded = json_bytes(value); digest = hashlib.sha256(encoded).hexdigest()
        target = self.audit_root / "artifacts" / (digest + ".json")
        _shared_audit_directory(target.parent,self.audit_group)
        try:
            with target.open("xb") as stream:
                if os.name=='posix':os.fchmod(stream.fileno(),0o640)
                stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
            if hasattr(os, "O_DIRECTORY"):
                fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
                try: os.fsync(fd)
                finally: os.close(fd)
        except FileExistsError:
            metadata=target.lstat()
            if (target.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink!=1
                or os.name=='posix' and (metadata.st_uid!=os.geteuid() or metadata.st_gid!=self.audit_group or metadata.st_mode&0o022)
                or target.read_bytes()!=encoded):raise IntegrityFault("immutable_audit_collision")
        return {"id": "artifacts/" + target.name, "sha256": digest}

    @staticmethod
    def no_route(execution_id, code, exclusions=()):
        return {"kind": "no_route", "no_route": {"execution_id": execution_id,
            "phase": "routing", "halt_code": code, "retryable": False,
            "candidate_reasons": list(exclusions)}}

    def route(self, request):
        execution_id = request.get("execution_id", "") if isinstance(request, dict) else ""
        try:
            context = validate_request(request, self.data, self.validate)
            state, prior = self.store.claim(execution_id, request["user_id"], request)
            if state != "claimed":
                if state == "ready":
                    if self.store.lookup(execution_id)["state"] == "expired":
                        return self.no_route(execution_id, "ROUTING_DEADLINE_EXCEEDED")
                    return {"kind": "decision", "decision": prior["decision"]}
                if state == "failed" and prior.get("decision"): return prior["decision"]
                return self.no_route(execution_id, "ROUTING_IN_PROGRESS" if state == "in_progress" else "ROUTING_OUTCOME_UNKNOWN")
            profile_ref = request["model_selection_profile_ref"]
            if profile_ref not in self.profile_refs: raise NoRoute("PROFILE_UNAVAILABLE")
            try:
                profile = self.data.read_json(profile_ref)
                self.validate("model-selection-profile", profile)
            except (IntegrityFault,OSError): raise NoRoute("PROFILE_UNAVAILABLE") from None
            validate_profile(profile)
            if profile["policy_ref"] != context["policy_ref"]: raise IntegrityFault("profile_policy_mismatch")
            policy = self.data.read_json(profile["policy_ref"])
            selection_policy = policy.get("routing", policy)
            try:
                snapshot = self.data.read_json(self.catalog_ref)
                catalog = QualifiedCatalog(snapshot["entries"])
                aggregates = self.data.read_json(self.development_profiles_ref)
                if isinstance(aggregates, dict): aggregates = aggregates["entries"]
            except (IntegrityFault, CatalogError, KeyError,OSError): raise NoRoute("SERVICE_STALE") from None
            candidates, excluded = catalog.candidates()
            selected, eligible, reasons, method = choose(request, candidates, profile,
                selection_policy, aggregates, selection_policy.get("scope_key"))
            excluded.extend(reasons)
            initial = selected["model_id"]
            self.store.note(execution_id, "initial_choice", {"model_id": initial,
                "eligible": [x["model_id"] for x in eligible], "reason": method})
            alternate_used = False
            if not self.preflight(request, selected):
                alternate = next((x for x in eligible if x["model_id"] == profile.get("alternate_model_id")), None)
                if alternate is None or not self.preflight(request, alternate): raise NoRoute("ALTERNATE_UNAVAILABLE", excluded)
                self.store.alternate(execution_id, alternate["model_id"], {x["model_id"] for x in eligible})
                selected, method, alternate_used = alternate, "router_alternate_model", True
            limits = budget_compatible(request, selected)
            now = datetime.now(timezone.utc)
            request_ref=self.capture(request);selected_ref=self.capture(request['selected_capsule'])
            derived={'id':'routing-context:'+uuid.uuid4().hex,'selected_capsule_ref':selected_ref,
                'model_selection_profile_ref':profile_ref,'adapter_revision':self.adapter_revision,
                'required_model':request['selected_capsule']['declaration'].get('needs',{}).get('model',{}),
                'requirements':request['requirements'],'capsule_budget':request['selected_capsule']['declaration']['budget'],
                'effective_limits':limits,'bound_context':context,'observed_runtime':True}
            decision = {"schema_version": "2.0.0", "id": "route:" + uuid.uuid4().hex,
                "request_ref": request_ref, "selected_capsule_ref": selected_ref,
                "runtime": context["runtime"], "execution_id": execution_id, "binding_id": context["binding_id"],
                "role": context["role"], "model_selection_profile_ref": profile_ref,
                "registry_snapshot_ref": self.catalog_ref, "eligible_endpoints": [x["model_id"] for x in eligible],
                "excluded_reasons": excluded, "selected_endpoint": selected["model_id"],
                "deployment_ref": selected["deployment_ref"],
                "identity": {"requested": selected["model_id"], "effective": None,
                             "basis": "selection metadata only; provider has not executed"},
                "limits": limits, "selection_method": method, "alternate_used": alternate_used,
                "ready_at": utc(now), "valid_until": utc(now + timedelta(seconds=30)),
                "routing_context_ref": self.capture(derived), "adapter_revision": self.adapter_revision}
            self.validate("model-route", decision)
            self.capture(decision)
            self.store.ready(execution_id, decision)
            return {"kind": "decision", "decision": decision}
        except IntegrityFault as exc:
            return {"kind": "integrity_fault", "integrity_fault": {"execution_id": execution_id,
                "reason": "platform_integrity_fault", "failed_checks": [exc.check]}}
        except ClaimConflict:
            return {"kind": "integrity_fault", "integrity_fault": {"execution_id": execution_id,
                "reason": "platform_integrity_fault", "failed_checks": ["execution_identity_conflict"]}}
        except NoRoute as exc:
            reply = self.no_route(execution_id, exc.code, exc.exclusions)
            try: self.store.reject(execution_id, reply)
            except (sqlite3.Error, OSError, ClaimConflict): return self.no_route(execution_id, "AUDIT_UNAVAILABLE")
            return reply
        except (sqlite3.Error, OSError):
            return self.no_route(execution_id, "AUDIT_UNAVAILABLE")

