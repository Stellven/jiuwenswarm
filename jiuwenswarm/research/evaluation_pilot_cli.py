"""Docker-only authoring CLI for frozen, invalid-for-product E2/E3 pilots.

This command captures references and request templates only. It does not call
models, run capsules, or emit product acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import stat
import uuid

from .contracts import ResearchError, validate
from .evaluation_pilot import capture_evaluation_pilot_profile, capture_evaluation_pilot_scope
from .operator_config import OperatorConfiguration
from .state import SQLiteRunStore, json_bytes


def _fail(message):
    raise ResearchError("evaluation_pilot_cli", message)


def _read_json(path, *, max_bytes=4 * 1024 * 1024):
    path = Path(path)
    if not path.is_absolute() or any(parent.is_symlink() for parent in (path, *path.parents)):
        _fail("Input file must be an absolute regular path")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
        _fail("Input file is not one bounded regular file")
    return json.loads(path.read_bytes())


def _write_once(path, raw):
    path = Path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _fresh_output(path, state_root):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=False) != path:
        _fail("Output directory must be an absolute canonical path")
    operator_root = (Path(state_root) / "operator").resolve()
    if not path.is_relative_to(operator_root):
        _fail("Pilot output must remain under the app-owned operator directory")
    for parent in (path, *path.parents):
        if parent.exists() and parent.is_symlink():
            _fail("Pilot output paths may not contain symlinks")
    if path.exists():
        _fail("Pilot output directory already exists; use a fresh profile identity")
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    metadata = path.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        _fail("Pilot output directory custody is invalid")
    return path


def _load_active(store, config_path, bootstrap_path):
    config_path = Path(config_path)
    settings = OperatorConfiguration.load(config_path, resolve_profile=store.read_record).snapshot()
    locator = _read_json(bootstrap_path)
    if type(locator) is not dict or set(locator) != {"binding_ref"}:
        _fail("Bootstrap locator must contain exactly one protected binding Ref")
    validate("Ref", locator["binding_ref"])
    binding = store.read_record(locator["binding_ref"])
    if (type(binding) is not dict or not {"configuration_ref", "model_selection_profile_ref",
            "deployment_ref", "workspace_id", "protected_options"} <= set(binding)):
        _fail("Captured startup binding is incomplete")
    if store.read_blob(binding["configuration_ref"]) != json_bytes(settings):
        _fail("Active configuration bytes differ from the exact bound configuration Ref")
    return settings, binding, locator["binding_ref"]


def _current_snapshot(store, current_binding_ref):
    refs = []
    for row in store.iter_records(kinds=("catalog-initialization",)):
        record = row["record"]
        if (record.get("binding_ref") == current_binding_ref and record.get("status") == "initialized"
                and record.get("library_snapshot_ref") is not None):
            refs.append(record["library_snapshot_ref"])
    unique = {json_bytes(ref): ref for ref in refs}
    if len(unique) != 1:
        _fail("Current binding has no unique successful catalog snapshot; initialize exact catalog first")
    ref = next(iter(unique.values()))
    store.read_record(ref, contract_id="library-snapshot")
    return ref


def _declaration_ref(store, digest, *, preferred_ref=None):
    refs = [row["ref"] for row in store.iter_records(kinds=("capsule-declaration",))
            if row["ref"]["sha256"] == digest]
    if preferred_ref is not None:
        validate('Ref',preferred_ref)
        if preferred_ref['sha256'] != digest:
            _fail('Installed declaration Ref differs from the captured digest')
        # Compiler declarations may be captured as validated JSON blobs without
        # a record-kind index. Exact protected membership supplies that identity.
        store.read_record(preferred_ref,contract_id='capsule-declaration')
        if preferred_ref not in refs:refs.append(preferred_ref)
    if not refs:
        _fail("Exact capsule declaration Ref is not captured")
    # Capturing the same immutable declaration under another artifact identity
    # does not introduce another capsule version. Verify bytes before collapsing
    # aliases, and preserve the exact installed membership Ref when supplied.
    raws = [store.read_blob(ref) for ref in refs]
    if any(raw != raws[0] for raw in raws[1:]):
        _fail("Captured declaration digest aliases differ in bytes")
    if preferred_ref is not None:
        return preferred_ref
    return min(refs, key=lambda ref: (ref['id'] != 'blob:' + digest, ref['id']))


def _select_verifier_entry(snapshot, verifier_identity=None):
    rows = [row for row in snapshot["entries"] if row["cc_name"] == "research.verifier"]
    if verifier_identity is not None:
        if not isinstance(verifier_identity, str) or verifier_identity.count("@") != 1:
            _fail("Verifier must use exact cc_name@cc_version identity")
        name, version = verifier_identity.rsplit("@", 1)
        rows = [row for row in rows if row["cc_name"] == name and row["cc_version"] == version]
    if len(rows) != 1:
        _fail("Installed verifier is ambiguous; pass --verifier with an exact installed identity")
    return rows[0]


def _snapshot_verifier_ref(store, snapshot_ref, verifier_row):
    """Resolve exact membership from the protected snapshot budget capture.

    Development Library membership is intentionally in memory; constructing a
    new LibraryService cannot recover it from library_versions. Its captured
    snapshot association retains the exact admitted verifier identity instead.
    """
    choices={}
    for row in store.iter_records(kinds=('library-budget-binding',)):
        record=row['record']
        if record.get('library_snapshot_ref') != snapshot_ref:
            continue
        verifier=record.get('verifier')
        pin={key:verifier_row[key] for key in ('cc_name','cc_version','declaration_sha256')}
        if not verifier or verifier.get('cc') != pin:
            _fail('Snapshot verifier membership differs from the selected identity')
        ref=verifier['declaration_ref']
        admission=store.read_record(verifier['admission_ref'],contract_id='library-admission')
        if admission['status'] != 'admitted' or admission['cc'] != pin or admission['candidate_ref'] != ref:
            _fail('Snapshot verifier declaration differs from its admitted membership')
        choices[json_bytes(ref)]=ref
    if len(choices) != 1:
        _fail('Snapshot has no unique protected verifier membership')
    return _declaration_ref(store,verifier_row['declaration_sha256'],preferred_ref=next(iter(choices.values())))


def author_profile(*, store, config_path, bootstrap_path, output_dir, profile_id, candidates,
                   verifier_identity=None):
    settings, binding, current_binding_ref = _load_active(store, config_path, bootstrap_path)
    output = _fresh_output(output_dir, store.root)
    snapshot_ref = _current_snapshot(store, current_binding_ref)
    snapshot = store.read_record(snapshot_ref, contract_id="library-snapshot")
    pins = []
    for identity in candidates:
        if not isinstance(identity, str) or identity.count("@") != 1:
            _fail("Candidate must use exact cc_name@cc_version identity")
        name, version = identity.rsplit("@", 1)
        rows = [row for row in snapshot["entries"]
                if row["cc_name"] == name and row["cc_version"] == version]
        if len(rows) != 1:
            _fail("Candidate identity is absent or ambiguous in the current installed snapshot")
        pins.append({"cc_name": name, "cc_version": version,
                     "declaration_sha256": rows[0]["declaration_sha256"]})
    verifier_row = _select_verifier_entry(snapshot, verifier_identity)
    verifier_ref = _snapshot_verifier_ref(store,snapshot_ref,verifier_row)
    verifier = store.read_record(verifier_ref, contract_id="capsule-declaration")
    if verifier["identity"]["name"] != verifier_row["cc_name"] or verifier["identity"]["version_label"] != verifier_row["cc_version"]:
        _fail("Selected verifier identity differs from its immutable declaration")
    result = capture_evaluation_pilot_profile(store, current_operator=settings,
        current_binding=binding, profile_id=profile_id, candidate_pins=pins,
        verifier_cc_ref=verifier_ref, library_snapshot_ref=snapshot_ref)
    _write_once(output / "config.json", json_bytes(result["operator_config"]))
    _write_once(output / "bootstrap.json", json_bytes({"binding_ref": result["bootstrap_binding_ref"]}))
    _write_once(output / "pilot.json", json_bytes({"schema": "ai4r-evaluation-pilot-phase1:1",
        "profile_id": profile_id, "profile_ref": result["profile_ref"],
        "configuration_ref": result["configuration_ref"], "binding_ref": result["bootstrap_binding_ref"],
        "library_snapshot_ref": snapshot_ref, "invalid_for_product": True}))
    return {"output_dir": str(output), "profile_ref": result["profile_ref"],
        "configuration_ref": result["configuration_ref"], "bootstrap_binding_ref": result["bootstrap_binding_ref"],
        "library_snapshot_ref": snapshot_ref, "invalid_for_product": True}


def source_candidates(store, *, configuration_ref, candidate_pins=None):
    """List exact source contracts and successful observations under one config."""
    validate("Ref", configuration_ref)
    result = []
    for row in store.iter_records(kinds=("subnode-execution-contract",)):
        ref, contract = row["ref"], row["record"]
        if contract.get("configuration_ref") != configuration_ref:
            continue
        if (len(contract.get("bindings", [])) != 1
                or contract["bindings"][0].get("role") != "work"):
            continue
        declaration_ref = contract["bindings"][0]["declaration_ref"]
        declaration = store.read_record(declaration_ref, contract_id="capsule-declaration")
        pin = {"cc_name": declaration["identity"]["name"],
               "cc_version": declaration["identity"]["version_label"],
               "declaration_sha256": declaration_ref["sha256"]}
        if candidate_pins is not None and pin not in candidate_pins:
            continue
        check_plans = [entry["ref"] for entry in store.iter_records(kinds=("bound-check-plan",))
                       if entry["record"].get("contract_ref") == ref]
        if len(check_plans) != 1:
            continue
        observations = []
        for item in store.iter_records(run_id=contract["run_id"], kinds=("invocation-observation",)):
            observed = item["record"]
            if (observed.get("contract_ref") == ref and observed.get("outcome") == "success"
                    and observed.get("output_refs")):
                observations.append({"ref": item["ref"], "output_refs": observed["output_refs"],
                    "measurement_status": observed.get("measurement_status"),
                    "model_calls": observed.get("model_calls")})
        result.append({"source_contract_ref": ref, "check_plan_ref": check_plans[0],
            "run_id": contract["run_id"], "node_id": contract["node_id"],
            "subnode_id": contract["subnode_id"], "capsule": declaration["identity"],
            "inputs": [{"port": port["name"], "artifact_refs": port["artifact_refs"]}
                       for port in contract["inputs"]],
            "outputs": [port["name"] for port in contract["outputs"]],
            "observations": observations})
    return result


def _source_ref(store, record_id, kind):
    try:
        ref = store.record_ref(record_id)
    except ResearchError as error:
        raise ResearchError("evaluation_pilot_cli", "Selected source record identity is unavailable") from error
    if store.record_kind(ref) != kind:
        _fail("Selected source record has another protected kind")
    return ref


def _source_observation(store, contract_ref, record_id=None):
    contract = store.read_record(contract_ref, contract_id="subnode-execution-contract")
    if record_id:
        candidates = [{"ref": _source_ref(store, record_id, "invocation-observation")}]
    else:
        candidates = [row for row in store.iter_records(run_id=contract["run_id"],
            kinds=("invocation-observation",)) if row["record"].get("contract_ref") == contract_ref
            and row["record"].get("outcome") == "success" and row["record"].get("output_refs")]
    if len(candidates) != 1:
        _fail("Source needs one exact successful observation; specify its record identity if ambiguous")
    ref = candidates[0]["ref"]
    observed = store.read_record(ref, contract_id="invocation-observation")
    if observed.get("contract_ref") != contract_ref or observed.get("outcome") != "success":
        _fail("Selected observation is not the exact successful source invocation")
    return ref, observed


def _check_source_verifier(store, contract, profile):
    parent = store.read_record(contract["node_contract_ref"], contract_id="node-execution-contract")
    verifier = store.read_record(profile["verifier_cc_ref"], contract_id="capsule-declaration")
    pin = {"cc_name": verifier["identity"]["name"], "cc_version": verifier["identity"]["version_label"],
           "declaration_sha256": profile["verifier_cc_ref"]["sha256"]}
    matches = []
    for assignment in parent["subnodes"]:
        if assignment.get("role") != "verifier":
            continue
        template = store.read_record(assignment["template_ref"])
        if template.get("subject_subnode_id") == contract["subnode_id"]:
            matches.append((assignment, template))
    if not matches or any(row[0]["capsule_ref"] != profile["verifier_cc_ref"] or row[1]["cc"] != pin
                          for row in matches):
        _fail("Source does not preserve the exact independently pinned verifier assignment")
    return verifier["identity"]["name"] + "@" + verifier["identity"]["version_label"]


def _host_records(store, path, run_id):
    if path is None:
        return []
    rows = _read_json(path, max_bytes=64 * 1024)
    allowed = {"runtime_observation", "identity_record", "budget_record", "tool_observation"}
    if type(rows) is not list or len(rows) > 4:
        _fail("Host record input must be a finite list of at most four records")
    result = []
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"record_type", "record_ref_id"}:
            _fail("Host record requires record_type and exact invocation-observation record_ref_id")
        if row["record_type"] not in allowed or row["record_type"] in seen:
            _fail("Host record class is unsupported or duplicated")
        seen.add(row["record_type"])
        ref = _source_ref(store, row["record_ref_id"], "invocation-observation")
        observed = store.read_record(ref, contract_id="invocation-observation")
        if observed["run_id"] != run_id or observed.get("outcome") != "success":
            _fail("Host record is not a successful observation from the same source run")
        result.append({"record_type": row["record_type"], "ref": ref})
    return result


def scope_from_source(*, store, profile_dir, source_contract_id, output_port,
                      campaign_id, output_dir, observation_id=None,
                      host_records_path=None, account_id=None, time_s=600,
                      model_calls=4, memory_mb=4096):
    profile_dir = Path(profile_dir)
    config = OperatorConfiguration.load(profile_dir / "config.json", resolve_profile=store.read_record)
    locator = _read_json(profile_dir / "bootstrap.json")
    if type(locator) is not dict or set(locator) != {"binding_ref"}:
        _fail("Phase-one bootstrap locator is invalid")
    binding_ref = locator["binding_ref"]
    binding = store.read_record(binding_ref)
    settings = config.snapshot()
    if store.read_blob(binding["configuration_ref"]) != json_bytes(settings):
        _fail("Phase-one configuration differs from its exact immutable binding")
    pilot_meta = _read_json(profile_dir / "pilot.json")
    if (pilot_meta.get("schema") != "ai4r-evaluation-pilot-phase1:1"
            or pilot_meta.get("configuration_ref") != binding["configuration_ref"]):
        _fail("Phase-one profile metadata does not match active configuration")
    profile_ref = settings["cc"]["evaluation_profile_ref"]
    profile = store.read_record(profile_ref, contract_id="evaluation-profile")
    if profile["invalid_for_product"] is not True:
        _fail("Phase-one evaluation profile is not explicitly invalid for product use")
    snapshot_ref = pilot_meta["library_snapshot_ref"]
    snapshot = store.read_record(snapshot_ref, contract_id="library-snapshot")
    if snapshot_ref["sha256"] != profile["library_snapshot_sha256"]:
        _fail("Pinned profile snapshot Ref does not match its profile commitment")

    contract_ref = _source_ref(store, source_contract_id, "subnode-execution-contract")
    contract = store.read_record(contract_ref, contract_id="subnode-execution-contract")
    if contract["configuration_ref"] != binding["configuration_ref"]:
        _fail("Source contract was not captured under the exact phase-one configuration")
    if len(contract["bindings"]) != 1:
        _fail("E2/E3 source must contain exactly one capsule")
    declaration_ref = contract["bindings"][0]["declaration_ref"]
    declaration = store.read_record(declaration_ref, contract_id="capsule-declaration")
    pin = {"cc_name": declaration["identity"]["name"], "cc_version": declaration["identity"]["version_label"],
           "declaration_sha256": declaration_ref["sha256"]}
    if pin not in profile["candidate_pins"] or pin not in [
            {key: row[key] for key in ("cc_name", "cc_version", "declaration_sha256")}
            for row in snapshot["entries"]]:
        _fail("Source capsule is outside exact candidate and snapshot pins")
    plans = [row["ref"] for row in store.iter_records(kinds=("bound-check-plan",))
             if row["record"].get("contract_ref") == contract_ref]
    if len(plans) != 1:
        _fail("Source needs one exact captured checking plan")
    observed_ref, observed = _source_observation(store, contract_ref, observation_id)
    output_ports = [port["name"] for port in contract["outputs"]]
    if len(observed["output_refs"]) != len(output_ports):
        _fail("Source observation output inventory differs from its exact contract")
    output_refs = dict(zip(output_ports, observed["output_refs"], strict=True))
    if output_port is None:
        if len(output_ports) != 1:
            _fail("Multi-output source needs explicit --output-port for E2 exact replay")
        output_port = output_ports[0]
    if output_port not in output_refs:
        _fail("Selected E2 replay output port is absent from the actual source observation")
    verifier_id = _check_source_verifier(store, contract, profile)
    hosts = _host_records(store, host_records_path, contract["run_id"])
    check_plan_ref = plans[0]

    output = _fresh_output(output_dir, store.root)
    replay_ref = store.append_record("evaluation-case-binding", {
        "schema": "ai4r-node-replay-binding:2", "id": "pilot-replay:" + uuid.uuid4().hex,
        "contract_ref": contract_ref, "check_plan_ref": check_plan_ref,
        "output_refs": output_refs, "original_observation_ref": observed_ref,
        "verifier_cc_id": verifier_id, "host_records": hosts,
        "selected_output_port": output_port})

    e3_id, e2_id = "fresh-e3-" + uuid.uuid4().hex[:10], "exact-e2-" + uuid.uuid4().hex[:10]
    e3_entries, e2_entries = [], []
    e3_prefix, e2_prefix = "fresh-e3", "exact-e2"
    e3_binding_path = e3_prefix + "/binding.json"
    e3_entries.append({"path": e3_binding_path, "role": "binding", "artifact_ref": contract_ref})
    e3_decl_path = e3_prefix + "/declaration.json"
    e3_entries.append({"path": e3_decl_path, "role": "declaration", "artifact_ref": declaration_ref})
    e3_inputs = []
    for port_index, port in enumerate(contract["inputs"]):
        for input_index, ref in enumerate(port["artifact_refs"]):
            path = f"{e3_prefix}/input-{port_index}-{input_index}.json"
            e3_entries.append({"path": path, "role": "input", "artifact_ref": ref})
            e3_inputs.append({"port": port["name"], "path": path, "sha256": ref["sha256"]})

    e2_decl_path = e2_prefix + "/declaration.json"
    e2_output_path = e2_prefix + "/output.json"
    e2_entries.extend([
        {"path": e2_decl_path, "role": "declaration", "artifact_ref": declaration_ref},
        {"path": e2_output_path, "role": "output", "artifact_ref": output_refs[output_port]},
    ])
    e2_hosts = []
    for index, item in enumerate(hosts):
        path = f"{e2_prefix}/host-{index}.json"
        role = "host_" + item["record_type"]
        e2_entries.append({"path": path, "role": role, "artifact_ref": item["ref"]})
        e2_hosts.append({"record_type": item["record_type"], "path": path, "sha256": item["ref"]["sha256"]})

    cases = [
        {"case_id": e3_id, "entry_point": "E3", "binding_ref": contract_ref, "assets": e3_entries},
        {"case_id": e2_id, "entry_point": "E2", "binding_ref": replay_ref, "assets": e2_entries},
    ]
    base = {"campaign_id": campaign_id, "evaluation_profile_id": profile["profile_id"]}
    e3_request = {**base, "request_id": "pilot-e3:" + uuid.uuid4().hex, "case_id": e3_id,
        "capsule_id": declaration["identity"]["name"], "capsule_version": declaration["identity"]["version_label"],
        "capsule_declaration_sha256": declaration_ref["sha256"],
        "binding": {"path": e3_binding_path, "sha256": contract_ref["sha256"]},
        "inputs": e3_inputs, "model_route": profile["model_route"]}
    e2_request = {**base, "request_id": "pilot-e2:" + uuid.uuid4().hex, "case_id": e2_id,
        "verifier_cc_id": verifier_id,
        "declaration": {"path": e2_decl_path, "sha256": declaration_ref["sha256"]},
        "output": {"path": e2_output_path, "sha256": output_refs[output_port]["sha256"]},
        "node_id": contract["node_id"], "host_records": e2_hosts}
    limits = {}
    for key, requested in (("time_s", time_s), ("model_calls", model_calls), ("memory_mb", memory_mb)):
        if type(requested) not in (int, float) or requested <= 0 or (key != "time_s" and type(requested) is not int):
            _fail("Requested pilot limits must be positive finite numeric values")
        limits[key] = min(requested, contract["subnode_limits"][key], contract["bindings"][0]["limits"][key])
    requests = [{"entry_point": "E3", "request": e3_request, "limits": limits},
                {"entry_point": "E2", "request": e2_request, "limits": limits}]
    result = capture_evaluation_pilot_scope(store, current_operator=settings,
        current_binding=binding, profile_id=profile["profile_id"],
        account_id=account_id or _primary_account(Path(os.environ.get("JIUWENSWARM_M1_ACCOUNTS", "/var/lib/ai4r-accounts"))),
        campaign_id=campaign_id, library_snapshot_ref=snapshot_ref,
        cases=cases, requests=requests)
    _write_once(output / "config.json", json_bytes(result["operator_config"]))
    _write_once(output / "bootstrap.json", json_bytes({"binding_ref": result["bootstrap_binding_ref"]}))
    _write_once(output / "requests.json", json_bytes(result["requests"]))
    _write_once(output / "pilot.json", json_bytes({"schema": "ai4r-evaluation-pilot-phase2:1",
        "profile_ref": result["profile_ref"], "configuration_ref": result["configuration_ref"],
        "assets_ref": result["assets_ref"], "runtime_ref": result["runtime_ref"],
        "schedule_ref": result["schedule_ref"], "bootstrap_binding_ref": result["bootstrap_binding_ref"],
        "source_contract_ref": contract_ref, "source_observation_ref": observed_ref,
        "source_replay_binding_ref": replay_ref, "invalid_for_product": True}))
    return {"output_dir": str(output), "profile_ref": result["profile_ref"],
        "assets_ref": result["assets_ref"], "runtime_ref": result["runtime_ref"],
        "schedule_ref": result["schedule_ref"], "bootstrap_binding_ref": result["bootstrap_binding_ref"],
        "requests_path": str(output / "requests.json"), "invalid_for_product": True}


def _primary_account(account_root, *, required=False):
    root = Path(account_root)
    path = root / "accounts.sqlite3"
    if (root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.geteuid()
            or stat.S_IMODE(root.stat().st_mode) != 0o700 or not path.is_file() or path.is_symlink()):
        _fail("Local account identity is not initialized")
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        _fail("Local account identity custody is invalid")
    db = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True)
    try:
        row = db.execute("SELECT account_id FROM accounts WHERE slot='primary'").fetchone()
    finally:
        db.close()
    if not row:
        _fail("Local account identity is not initialized")
    return row[0]


def _docker_context():
    if (os.name != "posix" or os.geteuid() != 10001 or not Path("/.dockerenv").exists()
            or os.environ.get("JIUWENSWARM_M1_PROFILE") != "1"):
        _fail("Pilot authoring runs only in the configured Docker app as UID 10001")


def main(argv=None):
    _docker_context()
    parser = argparse.ArgumentParser(prog="evaluation-pilot")
    parser.add_argument("--state-root", type=Path, default=Path(os.environ.get("JIUWENSWARM_M1_STATE", "/var/lib/ai4r")))
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("JIUWENSWARM_M1_CONFIG",
        "/var/lib/ai4r/operator/local-research-unified-v5/config.json")))
    parser.add_argument("--bootstrap", type=Path, default=None)
    sub = parser.add_subparsers(dest="action", required=True)
    phase1 = sub.add_parser("profile", help="Capture a profile-only E1/E2/E3 evaluation startup")
    phase1.add_argument("--profile-id", required=True)
    phase1.add_argument("--candidate", action="append", required=True, help="Exact installed capsule cc_name@cc_version; repeatable")
    phase1.add_argument("--verifier", default=None, help="Exact installed research.verifier cc_name@cc_version when multiple are present")
    phase1.add_argument("--output-dir", type=Path, required=True)
    inspect = sub.add_parser("sources", help="List actual captured subnode/observation refs under the phase-one configuration")
    inspect.add_argument("--profile-dir", type=Path, required=True)
    scope = sub.add_parser("scope", help="Capture fresh E3 and exact-output E2 requests from one real source invocation")
    scope.add_argument("--profile-dir", type=Path, required=True)
    scope.add_argument("--source-contract-id", required=True)
    scope.add_argument("--observation-id", default=None)
    scope.add_argument("--output-port", default=None)
    scope.add_argument("--host-records", type=Path, default=None,
        help="Optional JSON list of exact same-run host observation refs; defaults to the empty closure")
    scope.add_argument("--campaign-id", required=True)
    scope.add_argument("--output-dir", type=Path, required=True)
    scope.add_argument("--time-s", type=float, default=600)
    scope.add_argument("--model-calls", type=int, default=4)
    scope.add_argument("--memory-mb", type=int, default=4096)
    args = parser.parse_args(argv)
    state_root = args.state_root.resolve()
    bootstrap_env = os.environ.get("JIUWENSWARM_M1_BOOTSTRAP_BINDINGS", "").strip()
    bootstrap_path = args.bootstrap or (Path(bootstrap_env) if bootstrap_env else args.config.parent / "bootstrap.json")
    store = SQLiteRunStore(state_root, input_root="/workspace/input", recover=False)
    try:
        if args.action == "profile":
            result = author_profile(store=store, config_path=args.config, bootstrap_path=bootstrap_path,
                output_dir=args.output_dir, profile_id=args.profile_id, candidates=args.candidate,
                verifier_identity=args.verifier)
        elif args.action == "sources":
            config = OperatorConfiguration.load(args.profile_dir / "config.json", resolve_profile=store.read_record)
            locator = _read_json(args.profile_dir / "bootstrap.json")
            binding = store.read_record(locator["binding_ref"])
            profile = store.read_record(config.snapshot()["cc"]["evaluation_profile_ref"],
                                        contract_id="evaluation-profile")
            result = {"configuration_ref": binding["configuration_ref"],
                      "sources": source_candidates(store, configuration_ref=binding["configuration_ref"],
                          candidate_pins=profile["candidate_pins"])}
        else:
            result = scope_from_source(store=store, profile_dir=args.profile_dir,
                source_contract_id=args.source_contract_id, output_port=args.output_port,
                observation_id=args.observation_id, host_records_path=args.host_records,
                account_id=_primary_account(Path(os.environ.get("JIUWENSWARM_M1_ACCOUNTS", "/var/lib/ai4r-accounts"))),
                campaign_id=args.campaign_id, output_dir=args.output_dir,
                time_s=args.time_s, model_calls=args.model_calls, memory_mb=args.memory_mb)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ResearchError, ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        print(json.dumps({"status": "blocked", "diagnostic": "Protected pilot authoring prerequisites are unavailable or invalid"}))
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

