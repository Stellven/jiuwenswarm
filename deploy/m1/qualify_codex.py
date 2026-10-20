"""Inspect the exact packaged CLI, without login or a model request.

This records protocol support, not model access or tool confinement readiness.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    from codex_cli_bin import bundled_codex_path

    version = importlib.metadata.version("openai-codex-cli-bin")
    if version != "0.144.4":
        raise SystemExit("RUNTIME_VERSION_MISMATCH")
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "/evidence")
    output.mkdir(parents=True, exist_ok=True)
    binary = Path(bundled_codex_path())
    manifest = {"recorded_at": datetime.now(timezone.utc).isoformat(),
                "package_version": version, "machine": platform.machine(),
                "python": platform.python_version(),
                "executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "model_access": "NOT_RUN", "tool_confinement": "NOT_RUN", "commands": []}
    commands = ["--version"], ["--help"], ["exec", "--help"], ["app-server", "--help"]
    for index, arguments in enumerate(commands):
        command = [str(binary), *arguments]
        result = subprocess.run(command, capture_output=True, timeout=30, check=False)
        (output / f"{index}.stdout").write_bytes(result.stdout)
        (output / f"{index}.stderr").write_bytes(result.stderr)
        manifest["commands"].append({"argv": command, "exit_code": result.returncode,
                                     "stdout": f"{index}.stdout", "stderr": f"{index}.stderr"})
    # This subcommand is documented by the just-recorded pinned --help. Its
    # generated schema is later inspected before selecting protocol fields.
    if b"generate-json-schema" in (output / "3.stdout").read_bytes():
        command = [str(binary), "app-server", "generate-json-schema", "--out", str(output / "schema")]
        result = subprocess.run(command, capture_output=True, timeout=30, check=False)
        (output / "schema.stdout").write_bytes(result.stdout)
        (output / "schema.stderr").write_bytes(result.stderr)
        manifest["commands"].append({"argv": command, "exit_code": result.returncode,
                                     "stdout": "schema.stdout", "stderr": "schema.stderr"})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"package_version": version, "machine": platform.machine(),
                      "command_exit_codes": [c["exit_code"] for c in manifest["commands"]],
                      "model_access": "NOT_RUN", "tool_confinement": "NOT_RUN"}))
    return int(any(c["exit_code"] for c in manifest["commands"]))


if __name__ == "__main__":
    raise SystemExit(main())
