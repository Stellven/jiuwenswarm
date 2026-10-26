"""Harbor above the existing Docker/SSH operator; credentials stay in its runner.

Preparation/staging/doctor use stdlib only. Harbor itself is loaded only by the
selected Harbor runtime. Protected bundle files never become deployment inputs.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import uuid

from .contracts import canonical, pin, read_json, regular, relative, require, validate_bundle

REPO = Path(__file__).resolve().parents[2]
TARGET_FIELDS = ("deployment_id", "project", "root", "output", "platform", "docker_context", "app_image", "runner_image", "build_id", "local_model")
CONTROL_SOURCES = ("deploy/m1/ai4r.py", "deploy/m1/operator_host.py", "deploy/m1/local_model_operator.py", "deploy/m1/harbor_transport.py",
                   "benchmarks/harbor_suite/deployment.py", "benchmarks/harbor_suite/adapter.py",
                   "benchmarks/harbor_suite/contracts.py", "benchmarks/harbor_pilot/bridge.py")


def operator():
    folder = str(REPO / "deploy/m1")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return importlib.import_module("ai4r")


def target_identity(config):
    return {"ssh": config.get("ssh"), "wsl_distro": config.get("wsl_distro"),
            "deployment": {key: config["deployment"].get(key) for key in TARGET_FIELDS}}


def publish(path, value):
    operator().host.publish(path, canonical(value))


def workspace_config(folder):
    folder = operator().host.checked(folder)
    value = read_json(folder / "deployment.json")
    require(value.get("schema") == "ai4r-harbor-deployment:1", "unsupported Harbor deployment workspace")
    require(Path(value["workspace"]) == folder, "workspace moved; prepare a new hardware-specific workspace")
    source = operator().load(value["operator_profile"])
    require(target_identity(source) == value["target"], "deployment target/images/build changed; prepare a new workspace")
    source["ssh_executable"] = value.get("ssh_executable")
    if value.get("ssh_executable"):
        # An explicit bridge (e.g. Windows OpenSSH from WSL) uses verified stdin
        # transfer: its SCP may not understand the Harbor host's local paths.
        source["scp_executable"] = False
    return value, source


def prepare(profile, bundle, workspace, *, mode="preflight", cases=(), ssh_executable=None):
    api = operator(); bundle = api.host.checked(bundle).resolve(strict=True)
    workspace = api.host.checked(workspace)
    require(not workspace.exists() and workspace.parent.is_dir(), "new workspace with existing parent required")
    require(not workspace.is_relative_to(bundle) and not bundle.is_relative_to(workspace), "workspace and protected bundle must be separate")
    require(mode in {"preflight", "live"}, "explicit preflight/live mode required")
    config = api.load(profile)
    index = validate_bundle(bundle)
    selected = [t for t in index["tasks"] if not cases or t["case_id"] in cases]
    require(bool(selected) and set(cases) <= {t["case_id"] for t in selected}, "unknown or empty case selection")
    if mode == "live":
        require(bool(config["deployment"].get("build_id")), "start/authenticate deployment before live preparation")
        require(all(config["deployment"].get(k) for k in ("deployment_id", "app_image", "runner_image")), "pinned deployment/images required")
    if ssh_executable:
        require(config.get("ssh") and Path(ssh_executable).is_absolute(), "absolute SSH executable override requires an SSH deployment")
        regular(ssh_executable)
    supported = [t for t in selected if t["case_id"] == "pipeline01-experiment"]
    require(mode != "live" or supported, "selected cases have no installed live deployment binding")
    # Assemble a dedicated public-only stage. Do not pass bundle/ or tests/ to
    # selected_files(), which deliberately transfers an entire selected root.
    payloads = {}; aggregate = []
    for task in supported:
        source = regular(bundle / "cases" / (task["task_key"]+".json"))
        require(pin(source) == task["runner_case_pin"], "runner case differs from frozen task")
        payloads["public/cases/"+source.name] = source.read_bytes()
        aggregate.extend(read_json(source)["cases"])
        for name, expected in task["public_inputs"].items():
            source = regular(bundle / "inputs" / relative(name))
            require(pin(source) == expected, "public input differs from frozen task")
            payloads["public/inputs/"+name] = source.read_bytes()
    if aggregate:
        payloads["public/selected.json"] = canonical({"schema_version":"sequential-cases:1", "policy":"stop", "cases":aggregate})
    value = {"schema":"ai4r-harbor-deployment:1", "workspace":str(workspace),
             "bundle_root":str(bundle), "operator_profile":str(Path(profile).absolute()), "mode":mode,
             "target":target_identity(config), "ssh_executable":str(ssh_executable) if ssh_executable else None,
             "selected_tasks":[t["task_key"] for t in selected],
             "control_sources":{name:pin(REPO/name) for name in CONTROL_SOURCES},
             "public_files":{name:{"sha256":hashlib.sha256(raw).hexdigest(),"size":len(raw)} for name,raw in payloads.items()}}
    workspace.mkdir(mode=0o700)
    (workspace/"evidence").mkdir(mode=0o700)
    (workspace/"snapshots").mkdir(mode=0o700)
    for name, raw in payloads.items():
        api.host.publish(workspace/name, raw)
    publish(workspace/"deployment.json", value)
    publish(workspace/"selected-index.json", {"schema":index["schema"], "tasks":selected})
    suite = {"schema":"ai4r-harbor-suite-config:1", "bundle_root":str(bundle),
             "output_root":str(workspace/"evidence"), "mode":mode}
    if mode == "live":
        suite["operator_config"] = str(workspace/"deployment.json")
    publish(workspace/"suite-config.json", suite)
    job = read_json(bundle/"job.json")
    job.update(job_name="ai4r-deployment-"+mode, jobs_dir=str(workspace/"jobs"),
               tasks=[{"path":str(bundle/"tasks"/t["task_key"])} for t in selected])
    require(job["n_attempts"] == job["n_concurrent_trials"] == 1 and job["retry"]["max_retries"] == 0,
            "sequential one-attempt job required")
    publish(workspace/"job.json", job)
    frozen = {name:pin(workspace/name) for name in ["deployment.json","selected-index.json","suite-config.json","job.json",*payloads]}
    publish(workspace/"workspace-pins.json", frozen)
    return {"workspace":str(workspace), "mode":mode, "tasks":len(selected), "supported_live_tasks":len(supported),
            "target_contacted":False, "next":"harbor doctor; for live: harbor stage, start, harbor doctor, harbor run"}


def validate_workspace(folder):
    value, config = workspace_config(folder)
    for name, expected in read_json(Path(folder)/"workspace-pins.json").items():
        require(pin(Path(folder)/relative(name)) == expected, "frozen deployment workspace changed")
    for name, expected in value["control_sources"].items():
        require(pin(REPO/relative(name)) == expected, "Harbor/operator source changed; prepare a new workspace")
    validate_bundle(Path(value["bundle_root"]), index_only=True)
    return value, config


def stage(folder):
    api = operator(); value, config = validate_workspace(folder); folder = Path(folder)
    require(value["mode"] == "live", "preflight workspaces never stage or dispatch product inputs")
    with api.host.lock(Path(value["operator_profile"]+".lock")):
        transport = api.Transport(config)
        readiness = transport.request("doctor")
        require(not readiness.get("prerequisite_error"), "deployment Docker prerequisites unavailable; run operator doctor")
        args = argparse.Namespace(cases=folder/"public/selected.json",inputs=folder/"public/inputs")
        result = api.stage(config,args)
        for source in sorted((folder/"public/cases").glob("*.json")):
            transport.transfer(source,kind="cases",name=result["stage"]+"/"+source.name)
        api.save(value["operator_profile"],config)
        receipt = {"schema":"ai4r-harbor-stage:1", "target":value["target"], "input_stage":result["stage"],
                   "public_files":value["public_files"], "case_directory":"/cases/"+result["stage"],
                   "status":"staged", "next":"start the deployment to adopt the staged runner mount, then harbor doctor"}
        receipt_path = folder/"stage-receipt.json"
        if receipt_path.exists():
            require(read_json(receipt_path) == receipt, "existing stage receipt changed")
        else:
            publish(receipt_path,receipt)
    return receipt


def staged(folder):
    value, config = validate_workspace(folder)
    receipt = read_json(Path(folder)/"stage-receipt.json")
    require(receipt.get("schema") == "ai4r-harbor-stage:1" and receipt.get("target") == value["target"]
            and receipt.get("public_files") == value["public_files"]
            and receipt.get("input_stage") == config["deployment"].get("input_stage")
            and receipt.get("case_directory") == "/cases/"+receipt.get("input_stage", ""), "staged deployment identity changed")
    return value,config,receipt


def doctor(folder, *, python=sys.executable):
    value,config = validate_workspace(folder); blockers = []
    probe = subprocess.run([python,"-c","from importlib.metadata import version; import json; print(json.dumps({n:version(n) for n in ['harbor','httpx','jsonschema']}))"],
                           capture_output=True,text=True)
    runtime = {}
    if probe.returncode:
        blockers.append("selected Python lacks Harbor/httpx/jsonschema")
    else:
        runtime = json.loads(probe.stdout)
        if runtime.get("harbor") != "0.24.0": blockers.append("Harbor 0.24.0 required for this pinned integration")
    # Harbor's local Docker daemon is separate from the deployment's SSH daemon.
    try:
        result = subprocess.run(["docker","info","--format","{{.OSType}}"],capture_output=True,text=True,timeout=15)
        if result.returncode or result.stdout.strip() != "linux": blockers.append("Harbor host Linux Docker engine unavailable")
    except (OSError,subprocess.TimeoutExpired):
        blockers.append("Harbor host Docker CLI/engine unavailable")
    local_blockers = list(blockers)
    remote = None
    try:
        remote = operator().Transport(config).request("doctor")
        if remote.get("prerequisite_error"): blockers.append("deployment host Docker access/readiness unavailable")
        architecture = (remote.get("docker") or {}).get("Architecture")
        if architecture:
            actual = {"aarch64":"linux/arm64","arm64":"linux/arm64","x86_64":"linux/amd64","amd64":"linux/amd64"}.get(architecture)
            if actual != config["deployment"]["platform"]:
                blockers.append("deployment Docker architecture differs from the pinned target platform")
    except (OSError,ValueError,subprocess.SubprocessError):
        blockers.append("deployment transport/owned profile unavailable")
    if value["mode"] == "live":
        try:
            _,config,receipt = staged(folder)
            first = next((Path(folder)/"public/cases").glob("*.json"))
            answer = operator().Transport(config).request("runner",args=["doctor","--cases",receipt["case_directory"]+"/"+first.name,
                         "--inputs","/inputs","--output","/results","--json"])
            if answer["returncode"]: blockers.append("authenticated deployment runner readiness unavailable")
        except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError):
            blockers.append("public stage/runner mount/credential readiness unavailable")
    selected = read_json(Path(folder)/"selected-index.json")["tasks"]
    return {"ready":not (blockers if value["mode"] == "live" else local_blockers),
            "mode":value["mode"],"runtime":runtime,"blockers":blockers,
            "deployment_ready":not blockers[len(local_blockers):],
            "target":value["target"],"deployment_probe":remote,
            "unsupported_cases":sorted({t["case_id"] for t in selected if t["case_id"] != "pipeline01-experiment"}),
            "qualification":"transport readiness only; model/scientific/module qualification remains evidence-dependent"}


def run(folder, *, python=sys.executable):
    value,_ = validate_workspace(folder); folder = Path(folder)
    require(value["mode"] != "live" or os.name == "posix", "live Harbor controller must run on Linux/WSL for joined observer cancellation")
    with operator().host.lock(folder/"harbor.lock"), operator().host.lock(Path(value["operator_profile"]+".lock")):
        ready = doctor(folder,python=python)
        # A model-free preflight needs only its local Harbor/Docker runtime.
        local_errors = [b for b in ready["blockers"] if b.startswith(("selected Python","Harbor"))]
        require(not (ready["blockers"] if value["mode"] == "live" else local_errors), "Harbor/deployment readiness blocked; run harbor doctor")
        env = os.environ.copy(); env["AI4R_HARBOR_SUITE_CONFIG"] = str(folder/"suite-config.json")
        env["PYTHONPATH"] = str(REPO)
        launch = folder/"launches"/(uuid.uuid4().hex+".json")
        job = read_json(folder/"job.json")
        job["job_name"] += "-"+launch.stem[:12]
        publish(launch,job)
        result = subprocess.run([python,"-m","harbor.cli.main","run","--config",str(launch)],env=env)
        return {"returncode":result.returncode,"jobs":str(folder/"jobs"),"mode":value["mode"]}


@dataclass
class OperatorConfig:
    workspace: Path
    bundle_root: Path
    output_root: Path
    expected_build: str
    target_identity: str
    endpoint: str = "http://ai4r:5173"
    http_authority: str = "127.0.0.1:5175"
    token_file: None = None
    cancel_timeout_s: float = 45
    reconcile_without_local_campaign: bool = True

    @classmethod
    def load(cls,path):
        path = regular(path)
        value,config,receipt = staged(path.parent)
        require(path == Path(value["workspace"])/"deployment.json" and value["mode"] == "live", "wrong operator bridge config")
        identity = hashlib.sha256(canonical({"target":value["target"],"input_stage":receipt["input_stage"],
                                            "ssh_executable":value.get("ssh_executable")})).hexdigest()
        return cls(path.parent,Path(value["bundle_root"]),path.parent/"evidence",config["deployment"]["build_id"],identity)


class OperatorExecutor:
    """Async observer of the existing runner, with no copied app credential."""
    def __init__(self,config):
        self.config = config

    async def request(self,action,**values):
        require(os.name == "posix", "live Harbor observer requires Linux/WSL process-group containment")
        request = {"workspace":str(self.config.workspace),"action":action,**values}
        options = {"start_new_session":True} if os.name == "posix" else {}
        process = await asyncio.create_subprocess_exec(sys.executable,str(REPO/"deploy/m1/harbor_transport.py"),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,**options)
        try:
            out,_ = await process.communicate(canonical(request))
        except asyncio.CancelledError:
            # Stop only the local observer tree. Remote execution is uncertain;
            # shared bridge containment/reconciliation retains the active pin.
            if process.returncode is None:
                try:
                    if os.name == "posix": os.killpg(process.pid,signal.SIGTERM)
                    else: process.terminate()
                except ProcessLookupError: pass
                await process.wait()
            raise
        if process.returncode:
            raise ValueError("deployment runner transport failed; inspect operator doctor privately")
        result = json.loads(out)
        require(result.get("ok") is True,"deployment runner request unavailable")
        return result["result"]

    async def __call__(self,args):
        from ..harbor_pilot.bridge import observation
        folder = self.config.output_root/args.campaign_id
        if args.command == "resume" and observation(folder)["evidence_complete"]:
            return 0,{"reused_verified_terminal_snapshot":True}
        if args.command == "run":
            _,_,receipt = staged(self.config.workspace)
            command = ["run","--cases",receipt["case_directory"]+"/"+Path(args.cases).name,
                       "--inputs","/inputs","--output","/results","--campaign-id",args.campaign_id,"--json"]
        else:
            require(args.command in {"resume","cancel"},"unsupported deployment bridge operation")
            command = [args.command,"--campaign-dir","/results/"+args.campaign_id,"--json"]
        response = await self.request("runner",args=command)
        if args.command != "cancel":
            snapshot = self.config.workspace/"snapshots"/(args.campaign_id+"-"+uuid.uuid4().hex)
            await self.request("fetch",campaign=args.campaign_id,output=str(snapshot))
            self.publish_snapshot(snapshot,folder)
        return response["returncode"],{}

    @staticmethod
    def publish_snapshot(snapshot,folder):
        """Retain each verified generation, then expose its original runner view."""
        api = operator(); snapshot = api.host.checked(snapshot); folder = api.host.checked(folder)
        manifest = read_json(snapshot/".transfer-manifest.json")["snapshot"]
        require(manifest.get("files") and len(manifest["files"]) <= 10000
                and manifest.get("campaign") == folder.name,"empty/foreign/oversized deployment campaign snapshot")
        names = set(); verified = []; total = 0
        reserved = {"bridge-pins.json","pilot-receipt.json","suite-receipt.json","host-inventory.json","operator-snapshot.json"}
        for row in manifest["files"]:
            name = relative(row["path"])
            require(name not in names and name not in reserved,"duplicate or reserved fetched evidence path")
            names.add(name); source = regular(snapshot/name,128*1024*1024)
            require(pin(source) == {k:row[k] for k in ("sha256","size")},"verified fetch changed before publication")
            total += row["size"]
            require(total <= 1024*1024*1024,"deployment snapshot exceeds finite transfer policy")
            verified.append((name,source))
        if folder.exists():
            from ..harbor_pilot.bridge import observation
            require(not observation(folder)["evidence_complete"],"a complete original campaign cannot be rewritten")
        folder.mkdir(mode=0o700,exist_ok=True)
        # Publish mutable completion records last. A partial copy must never
        # release the bridge's active pointer before artifact bytes exist.
        for name,source in sorted(verified,key=lambda item:(item[0].endswith("run_record.json") or item[0] == "campaign_state.json",item[0])):
            target = api.host.checked(folder/name)
            # Every previous generation remains intact in snapshots/. Only
            # authenticated fetched bytes update a pending runner view.
            api.host.publish(target,source.read_bytes(),replace=target.exists())
        api.host.publish(folder/"operator-snapshot.json",canonical({"schema":"ai4r-harbor-operator-snapshot:1",
            "snapshot_id":manifest["id"],"files":manifest["files"]}),replace=(folder/"operator-snapshot.json").exists())
