"""Offline original-byte joins. No execution, credentials or product authority."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

try:
    from .contracts import canonical, read_json, regular, strict_json
    from ..harbor_pilot.grade import Artifacts
except ImportError:  # Frozen standalone verifier, not a second implementation.
    from pilot_grade import canonical, read_json, strict_json, Artifacts
    def regular(path, max_bytes=16*1024*1024):
        path = Path(path)
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > max_bytes:
            raise ValueError("regular evidence file required")
        return path


class Unavailable(ValueError):
    """Supported evidence/binding is absent; no quality measurement exists."""


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def empty(task):
    return {"variant_id": task["variant_id"], "entrypoint": task["entrypoint"],
            "execution": {"launched": False, "terminal": False, "status": "unavailable"},
            "records": [], "artifacts": {}, "module_observations": {}}


def validate_receipt(root, task):
    receipt = read_json(regular(Path(root) / "suite-receipt.json"))
    require(receipt.get("schema") == "ai4r-harbor-suite-receipt:1", "wrong suite receipt")
    for key in ("task_key", "case_id", "variant_id", "repeat", "expected_model"):
        require(receipt.get(key) == task[key], "receipt scope differs: " + key)
    require(receipt.get("task_sha256") == hashlib.sha256(canonical(task)).hexdigest(), "frozen task changed")
    if receipt.get("status") == "blocked":
        require(receipt.get("launched") is False and isinstance(receipt.get("blockers"), list)
                and receipt["blockers"], "invalid preflight blockage")
        raise Unavailable("; ".join(receipt["blockers"]))
    require(receipt.get("custody") == "live", "live suite cannot adopt replay custody")
    require(receipt.get("status") == "observed", "unsupported suite receipt outcome")
    return receipt


def normalize_run(root, task):
    """Read exactly one ordinary E1 attempt using original authorized bytes."""
    from jiuwenswarm.research_records.contracts import ContractData
    root = Path(root)
    receipt = validate_receipt(root, task)
    require(task["entrypoint"] == "run", "ordinary run cannot substitute for an isolated module")
    campaign = read_json(regular(root / "campaign.json"))
    require(campaign.get("schema_version") == "sequential-campaign:1"
            and campaign.get("campaign_id") == receipt.get("campaign_id"), "campaign scope mismatch")
    scheduled = campaign.get("cases", [])
    require(len(scheduled) == 1 and scheduled[0].get("id") == task["task_key"]
            and scheduled[0].get("repeats") == 1, "attempt schedule changed")
    require(scheduled[0].get("task") == task["variant"]["task"], "public task changed")
    paths = list((root / "runs").glob("*/run_record.json"))
    require(len(paths) == 1 and paths[0].parent.name == task["task_key"]+"-r1", "attempt dropped or duplicated")
    path = regular(paths[0]); run = read_json(path); folder = path.parent
    require((run.get("campaign_id"), run.get("case_id"), run.get("run_id")) ==
            (campaign["campaign_id"], task["task_key"], task["task_key"]+"-r1"), "run scope differs")
    status = run.get("status") or {}
    terminal = {"completed", "partial", "halted", "cancelled", "failed", "blocked", "interrupted"}
    require(run.get("execution_state") in terminal and run.get("collection_state") == "complete"
            and status.get("status") == run["execution_state"] and status.get("run_id") == run.get("app_run_id")
            and status.get("client_request_id") == run.get("request_id"), "execution or collection unresolved")
    require(receipt.get("campaign_id") == run["campaign_id"] and receipt.get("launched") is True,
            "adapter did not observe this launched attempt")
    store = Artifacts(folder, run, read_json(regular(folder / "collection_manifest.json")))
    contracts = ContractData(); normalized = empty(task)
    normalized["execution"] = {"launched": True, "terminal": True, "status": run["execution_state"],
                               "request_id": run["request_id"], "app_run_id": run["app_run_id"]}
    # Filename kind is the protected producer export's type declaration; schema
    # and exact original Ref still have to validate. Never infer kind by payload.
    old = re.compile(r"^evidence/[0-9]{4,}-([a-z][a-z0-9-]*)\.json$")
    new = re.compile(r"^(?:evidence|contracts)/([a-z][a-z0-9-]*)-([a-f0-9]{64})\.json$")
    inventories = [r for r in run["artifacts"] if r.get("source") == "app_archive_inventory"]
    if len(inventories) != 1:
        raise Unavailable("original Ref inventory for individually downloaded records is unsupported")
    inventory = read_json(regular(folder / inventories[0]["path"]))
    original_refs = {}
    by_sha = {}
    for original in store.manifest["artifacts"]:
        by_sha.setdefault(original["sha256"], []).append(original)
    for item in inventory["client_retrieval"]["files"]:
        ref = item["artifact_ref"]
        for original in by_sha.get(ref["sha256"], []):
            if hashlib.sha256(canonical([original["path"], ref])).hexdigest() == original["artifact_id"]:
                if original["path"] in original_refs and original_refs[original["path"]] != ref:
                    raise ValueError("ambiguous original Ref")
                original_refs[original["path"]] = ref
    pins = read_json(regular(root / "bridge-pins.json"))
    require(pins.get("case_id") == task["task_key"] and pins.get("runner_case_id") == task["task_key"]
            and pins.get("inputs") == task["public_inputs"], "runner public input pins changed")
    require(pins.get("case") == task["runner_case_pin"]
            and campaign.get("case_file_sha256") == task["runner_case_pin"]["sha256"]
            and campaign.get("input_inventory") == task["public_inputs"]
            and campaign.get("expected_build") == pins.get("expected_build"), "runner frozen schedule/target pins changed")
    refs = {}
    ref_text = {}
    for row in store.manifest["artifacts"]:
        name = row["path"]
        if row["size"] > 4*1024*1024:
            continue  # Already byte-validated; bounded oracle access only.
        try:
            data = store.bytes(name)
            raw = data.decode("utf-8") if data is not None else None
        except UnicodeError:
            continue
        if raw is None:
            continue
        normalized["artifacts"][name] = raw
        original_ref = original_refs.get(name)
        if original_ref:
            ref_text[(original_ref["id"], original_ref["sha256"])] = raw
        match = old.fullmatch(name) or new.fullmatch(name)
        if not match:
            continue
        kind = match[1]
        if kind not in contracts.schemas:
            continue  # Unknown publication has no invented type or authority.
        record = strict_json(data)
        contracts.validate(kind, record)
        require("run_id" not in record or record["run_id"] == run["app_run_id"], "foreign protected record")
        # Artifact ids bind original path + Ref; only original archive inventory
        # can provide that Ref. Recompute rather than trusting a summary field.
        ref = original_refs.get(name)
        require(ref is not None and ref["sha256"] == row["sha256"], "protected record Ref missing/ambiguous")
        identity = (ref["id"], ref["sha256"])
        if identity in refs:
            require(refs[identity] == (kind, record), "conflicting typed original record")
            continue
        refs[identity] = (kind, record)
        normalized["records"].append({"kind": kind, "ref": ref, "record": record})
    project_declared_outputs(normalized, ref_text, contracts)
    return normalized


def project_declared_outputs(normalized, ref_text, contracts):
    """Type original outputs only through their actual protected declaration.

    Output JSON cannot select its own kind. Require an original observation,
    its exact subnode contract, a declared schema and one unambiguous match.
    """
    by_ref = {(r["ref"]["id"], r["ref"]["sha256"]): r for r in normalized["records"]}
    for row in list(normalized["records"]):
        if row["kind"] != "invocation-observation":
            continue
        observation = row["record"]
        ref = observation.get("contract_ref", {})
        source = by_ref.get((ref.get("id"), ref.get("sha256")))
        if not source or source["kind"] != "subnode-execution-contract":
            continue
        contract = source["record"]
        require(all(observation.get(k) == contract.get(k) for k in ("run_id", "node_id", "subnode_id", "attempt_id")),
                "declared output invocation scope mismatch")
        kinds = {p["contract_id"] for p in contract["outputs"] if p["contract_id"] in contracts.schemas}
        for output in observation["output_refs"]:
            key = (output["id"], output["sha256"])
            if key in by_ref or key not in ref_text:
                continue
            require(hashlib.sha256(ref_text[key].encode("utf-8")).hexdigest() == output["sha256"],
                    "declared output original bytes changed")
            try:
                value = strict_json(ref_text[key].encode("utf-8"))
            except ValueError:
                continue
            if not isinstance(value, dict):
                continue
            matches = set()
            for kind in kinds:
                try:
                    contracts.validate(kind, value)
                except ValueError:
                    continue
                aliases = [name for name, schema in contracts.schemas.items()
                           if re.fullmatch(r"[a-z][a-z0-9-]*", name) and schema == contracts.schemas[kind]]
                matches.add(aliases[0] if len(aliases) == 1 else kind)
            if len(matches) != 1:
                continue
            projected = {"kind": next(iter(matches)), "ref": output, "record": value}
            by_ref[key] = projected
            normalized["records"].append(projected)


def normalize_evaluation(archive, *, task, request_id, campaign_id, expected_request):
    """Read E2/E3 original exports for protected launcher integrations.

    This is a decoder, not an importer trusting self-described control receipts.
    Caller must supply the independently frozen request and authorized job scope.
    """
    from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords
    require(task["entrypoint"] in {"single_cc", "node_replay"}, "wrong isolated entrypoint")
    records = EvaluationRecords.from_archive(regular(archive, 128*1024*1024).read_bytes(), request_id=request_id,
        campaign_id=campaign_id, audience="researcher", expected_request=expected_request)
    records.require_complete()
    return project_evaluation(records, task)


def normalize_single_cc(root, task):
    """Join a finite runner attempt to its prelaunch frozen E3 request."""
    from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords
    root = Path(root); receipt = validate_receipt(root, task)
    binding = task.get('evaluation_binding')
    if task['entrypoint'] != 'single_cc' or not binding:
        raise Unavailable('protected finite E3 binding is absent')
    require(receipt.get('campaign_id') == binding['campaign_id'], 'evaluation receipt campaign differs')
    paths = list((root / 'runs').glob('*/run_record.json'))
    require(len(paths) == 1 and paths[0].parent.name == binding['run_id'], 'evaluation attempt dropped or duplicated')
    run = read_json(regular(paths[0])); folder = paths[0].parent
    require(run.get('schema') == 'run-record:1' and run.get('entry_mode') == 'single_cc'
            and all(type(run.get(k)) is type(v) and run[k] == v for k, v in binding['run_scope'].items()),
            'retained evaluation run differs from frozen schedule')
    request = binding['expected_request']
    require(run.get('request_id') == request['request_id'] and request['campaign_id'] == binding['campaign_id']
            and request['case_id'] == binding['case_id'], 'evaluation request scope differs')
    if run.get('launched') is False and run.get('outcome') == 'blocked':
        raise Unavailable('finite E3 runner did not launch: '+str((run.get('outcome_detail') or {}).get('reason')))
    require(run.get('launched') is True and receipt.get('launched') is True and run.get('ended_at') is not None,
            'evaluation execution unresolved')
    requests = [r for r in run['exports'] if r['path'] == 'evaluation-request.json']
    require(len(requests) == 1, 'exact retained evaluation request pin required')
    raw = regular(folder / 'evaluation-request.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == requests[0]['sha256'] and strict_json(raw) == request,
            'retained evaluation request differs from frozen request')
    records = EvaluationRecords.from_frozen(folder / 'evaluation-export', request_id=request['request_id'],
        campaign_id=binding['campaign_id'], audience='researcher', expected_request=request, inventory=run['exports'])
    records.require_complete()
    normalized = project_evaluation(records, task)
    normalized['execution'].update(request_id=request['request_id'], app_run_id=run.get('app_run_id'),
                                   campaign_id=binding['campaign_id'], run_id=binding['run_id'])
    return normalized


def project_evaluation(records, task):
    """Preserve finite typed names and original Ref pairs after full validation."""
    require(records.request["entry_point"] == ("E3" if task["entrypoint"] == "single_cc" else "E2"), "private entrypoint differs")
    normalized = empty(task)
    normalized["execution"] = {"launched": True, "terminal": True, "status": records.terminal["state"]}
    for (kind, _), item in records.by_kind.items():
        raw = records.bytes_ref(item["artifact_ref"])
        if len(raw) > 4*1024*1024:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            continue
        normalized["artifacts"][item["path"]] = text
        try:
            record = strict_json(raw)
        except ValueError:
            continue
        if isinstance(record, dict):
            normalized["records"].append({"kind": kind, "ref": item["artifact_ref"], "record": record})
    if (task.get('case_id')=='cc02-binding' and records.request['entry_point']=='E3' and records.scope is not None
            and records.rows('library-snapshot') and records.rows('evaluation-profile')):
        # Only original Ref selectors; the complete reader owns custody,
        # source eligibility and request-local journal validation above.
        require(records.source is not None and records.terminal is not None and records.events,
                'binding projection needs complete original source/terminal custody')
        # A single original object can be exported under several validated
        # native roles (e.g. source_binding/source_contract). The oracle indexes
        # original identity once. Retain all roles as metadata and prefer its
        # exact source/control role, without changing any record body or Ref.
        preferred=['request','normalized_request','runtime','source_contract','source_declaration',
                   'source_admission','source_template','library-snapshot','evaluation-profile',
                   'terminal','event','measurement','observation','actual_contract','failure',
                   'recording_action','evaluation_gate','gate-decision','activation-record']
        rank={kind:index for index,kind in enumerate(preferred)};unique={}
        for row in normalized['records']:
            key=(row['ref']['id'],row['ref']['sha256'])
            if key not in unique:
                unique[key]={**row,'original_kinds':[row['kind']]}
                continue
            previous=unique[key]
            require(previous['record']==row['record'],'conflicting original binding projection bytes')
            roles=[*previous['original_kinds'],row['kind']]
            if rank.get(row['kind'],len(rank))<rank.get(previous['kind'],len(rank)):
                unique[key]={**row,'original_kinds':roles}
            else:
                previous['original_kinds']=roles
        normalized['records']=list(unique.values())
        normalized['module_observations']['cc02_binding']={
            'request_ref':records.manifest['request_ref'],
            'baseline_ref':records.scope['source_contract_ref'],
            'snapshot_ref':records.runtime['library_snapshot_ref'],
            'terminal_ref':records.rows('terminal')[0]['artifact_ref'],
            'through_event_ref':records.manifest['through_event_ref']}
    return normalized
