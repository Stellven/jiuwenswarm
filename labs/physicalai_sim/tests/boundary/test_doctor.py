"""V-OPS (AC-016): the doctor reports readiness, and names the failing item in degraded set-ups (through the CLI)."""
import json
import os
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]


def doctor(*args, env=None):
    r = subprocess.run([sys.executable, "-m", "simlab.interface.cli", "doctor", "--json", *args], capture_output=True, text=True,
                       env={**os.environ, **(env or {})}, timeout=120)
    return r.returncode, json.loads(r.stdout)


def failing(out):
    return {i["item"]: i["code"] for i in out["items"] if i["status"] == "failed"}


def test_healthy_and_degraded(tmp_path):
    clean_env = {k: v for k, v in os.environ.items() if not any(w in k.upper() for w in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "AUTH", "CREDENTIAL"))}
    r = subprocess.run([sys.executable, "-m", "simlab.interface.cli", "doctor", "--json", "--data-dir", str(tmp_path)],
                       capture_output=True, text=True, env=clean_env, timeout=120)
    healthy = json.loads(r.stdout)
    assert healthy["ready"] and r.returncode == 0, failing(healthy)
    rc, out = doctor("--data-dir", str(LAB / "src"))
    assert rc == 1 and failing(out).get("data_dir") == "D_DATA_DIR"
    rc, out = doctor("--data-dir", str(tmp_path), env={"SIMLAB_PLANTED_API_KEY": "not-a-real-key"})
    assert rc == 1 and failing(out).get("no_credentials_in_env") == "D_CREDENTIALS_PRESENT"
    lock = tmp_path / "uv.lock"
    lock.write_text((LAB / "uv.lock").read_text().replace('name = "mujoco"\nversion = "3.17.0"', 'name = "mujoco"\nversion = "3.18.0"'))
    rc, out = doctor("--data-dir", str(tmp_path), "--lock", str(lock))
    assert rc == 1 and failing(out).get("engine_version") == "D_ENGINE_VERSION"
    writable = tmp_path / "src"
    writable.mkdir()
    rc, out = doctor("--data-dir", str(tmp_path), "--source-dir", str(writable))
    assert rc == 1 and failing(out).get("source_read_only") == "D_SOURCE_WRITABLE"
