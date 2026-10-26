"""Harbor control adapter; authority stays with the existing product runner."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

from harbor.agents.base import BaseAgent

from .contracts import canonical, pin, read_json, regular, validate_bundle
from ..harbor_pilot.bridge import Config, BridgeCancelled, atomic, run_trial

MARKER = re.compile(r"^AI4R_HARBOR_TASK_KEY: ([a-z0-9][a-z0-9_.-]{0,47})$", re.MULTILINE)


def select_task(instruction, index):
    matches = MARKER.findall(instruction)
    if len(matches) != 1:
        raise ValueError("one exact frozen Harbor task key required")
    found = [t for t in index["tasks"] if t["task_key"] == matches[0]]
    if len(found) != 1:
        raise ValueError("task is outside frozen suite index")
    return found[0]


def load_config(path):
    value = read_json(path)
    required = {"schema", "bundle_root", "output_root", "mode"}
    if (not isinstance(value, dict) or not required <= set(value)
            or set(value)-required-{"runner_config", "operator_config", "evaluation_config"}
            or value["schema"] != "ai4r-harbor-suite-config:1"
            or value["mode"] not in {"preflight", "live"}):
        raise ValueError("unsupported host-only suite config")
    if sum(bool(value.get(k)) for k in ("runner_config", "operator_config", "evaluation_config")) > 1:
        raise ValueError("select one runner backend")
    for key in ("bundle_root", "output_root"):
        path = Path(value[key])
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)) or not path.is_dir():
            raise ValueError("existing absolute non-symlink root required")
        value[key] = path
    bundle, output = value["bundle_root"], value["output_root"]
    if bundle.is_relative_to(output) or output.is_relative_to(bundle):
        raise ValueError("bundle and outputs must be separate")
    for key in ("runner_config", "operator_config", "evaluation_config"):
        if key not in value:
            continue
        ref = Path(value[key])
        regular(ref)
        if not ref.is_absolute() or ref.is_relative_to(bundle) or ref.is_relative_to(output):
            raise ValueError("runner credentials must remain outside bundle/evidence")
    return value


def receipt(task, *, status, launched=False, blockers=(), **extra):
    return {"schema": "ai4r-harbor-suite-receipt:1",
            **{k: task[k] for k in ("task_key", "case_id", "variant_id", "repeat", "expected_model")},
            "task_sha256": hashlib.sha256(canonical(task)).hexdigest(),
            "status": status, "launched": launched, "blockers": list(blockers), **extra}


def preflight_blockers(task, config):
    if config["mode"] == "preflight":
        return ["preflight-only wiring check; no product request was authorized by this configuration"]
    if task["entrypoint"] == "single_cc" and task.get("evaluation_binding") and config.get("evaluation_config"):
        return []
    if task["entrypoint"] != "run":
        return ["supported protected module campaign/job/profile binding and validated projection are absent",
                *task["case"]["product_prerequisites"]]
    if task["case_id"] == "pipeline02-recovery":
        return ["protected frozen fault controller and interruption/negative-capture binding are absent"]
    if not config.get("runner_config") and not config.get("operator_config"):
        return ["authenticated existing runner config is absent"]
    return []


async def dispatch(config, task, identity, *, runner=run_trial):
    blockers = preflight_blockers(task, config)
    if blockers:
        key = hashlib.sha256((task["task_key"]+"\n"+identity).encode()).hexdigest()[:24]
        folder = config["output_root"] / ("preflight-"+key)
        folder.mkdir(exist_ok=True)
        result = receipt(task, status="blocked", blockers=blockers, custody="preflight")
        existing = folder / "suite-receipt.json"
        if existing.exists() and read_json(existing) != result:
            raise ValueError("preflight custody scope changed")
        atomic(existing, result)
        return folder, result, None
    if task['entrypoint'] == 'single_cc':
        from .evaluation import dispatch as dispatch_evaluation
        return await dispatch_evaluation(config, task, identity)
    execute = None
    if config.get("operator_config"):
        from .deployment import OperatorConfig, OperatorExecutor
        bridge = OperatorConfig.load(config["operator_config"])
        execute = OperatorExecutor(bridge)
    else:
        bridge = Config.load(config["runner_config"])
    if bridge.bundle_root != config["bundle_root"] or bridge.output_root != config["output_root"]:
        raise ValueError("runner target roots differ from frozen suite config")
    cancelled = None
    try:
        run = await runner(bridge, task["task_key"], identity, **({"execute": execute} if execute else {}))
    except BridgeCancelled as error:
        run = error.result; cancelled = error
    result = receipt(task, status="observed", launched=bool(run.receipt.get("app_run_id")),
                     campaign_id=run.receipt["campaign_id"], custody="live")
    atomic(run.folder / "suite-receipt.json", result)
    return run.folder, result, cancelled


class AI4ResearchSuiteAgent(BaseAgent):
    @staticmethod
    def name():
        return "ai4research-suite"

    def version(self):
        return "1"

    async def setup(self, environment):
        path = os.environ.get("AI4R_HARBOR_SUITE_CONFIG")
        if not path:
            raise ValueError("AI4R_HARBOR_SUITE_CONFIG must reference host-only config")
        self._config = load_config(path)
        self._index = validate_bundle(self._config["bundle_root"], index_only=True)

    async def run(self, instruction, environment, context):
        task = select_task(instruction, self._index)
        validate_bundle(self._config["bundle_root"], selected=task)
        # Exact instruction pin prevents mutable prompts from changing a trial
        # while retaining its protected case/oracle identity.
        expected = (self._config["bundle_root"] / "tasks" / task["task_key"] / "instruction.md").read_text(encoding="utf-8")
        if instruction.strip() != expected.strip():
            raise ValueError("instruction differs from frozen task")
        folder, result, cancelled = await dispatch(self._config, task, str(Path(self.logs_dir).resolve()))
        await environment.upload_dir(source_dir=folder, target_dir="/app/ai4r-evidence")
        context.metadata = {"ai4research_suite": result, "measurement_scope": "development; original product evidence only"}
        if cancelled:
            raise cancelled
