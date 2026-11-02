"""V-BLK-REG (AC-016): registry admission only from evidence for this build; doctor items; resource records."""
import json
import subprocess
import sys

from simlab import build_identity
from simlab.doctor import run as doctor_run
from simlab.registry import admit, entries
from simlab.resources import COMPUTE_LOG_HEADER, ResourceMeter, compute_log_append


def by_cap(store):
    return {e["capability"]: e for e in entries(store)}


def test_mujoco_not_admitted_without_evidence(store):
    e = by_cap(store)
    assert e["engine:mujoco"]["status"] == "supported"
    assert e["engine:isaac_sim"]["status"] == "excluded" and "RTX 4080" in e["engine:isaac_sim"]["reason"]
    assert e["library:actuators"]["status"] == "missing"


def test_admission_is_tied_to_the_build(store):
    admit(store, "engine:mujoco", "benchmarks/reports/x/F1", True, "F1 passed")
    assert by_cap(store)["engine:mujoco"]["status"] == "admitted"
    store.set_capability("engine:mujoco", "engine", "admitted", "F1 passed", "old-report", "0" * 64)
    e = by_cap(store)["engine:mujoco"]
    assert e["status"] == "supported" and "not this build" in e["reason"]
    admit(store, "engine:mujoco", "benchmarks/reports/y/F1", False, "F1 failed")
    assert by_cap(store)["engine:mujoco"]["status"] == "supported"


def test_doctor_names_degraded_items(tmp_path, monkeypatch):
    lab = build_identity.project_root()
    good = doctor_run(str(tmp_path))
    names = {i["item"] for i in good["items"]}
    assert {"engine_version", "data_dir", "seccomp_available", "executor_network_denied", "no_credentials_in_env"} <= names
    inside = doctor_run(str(lab / "src"))
    assert any(i["item"] == "data_dir" and i["code"] == "D_DATA_DIR" for i in inside["items"])
    monkeypatch.setenv("SIMLAB_PROBE_API_KEY", "x")
    cred = doctor_run(str(tmp_path))
    assert any(i["item"] == "no_credentials_in_env" and i["code"] == "D_CREDENTIALS_PRESENT" for i in cred["items"])
    lock = tmp_path / "uv.lock"
    lock.write_text((lab / "uv.lock").read_text().replace('name = "mujoco"\nversion = "3.17.0"', 'name = "mujoco"\nversion = "3.16.0"'))
    old = doctor_run(str(tmp_path), lock=str(lock))
    assert any(i["item"] == "engine_version" and i["code"] == "D_ENGINE_VERSION" for i in old["items"])


def test_resource_record_and_compute_log(tmp_path):
    with ResourceMeter(disk_dir=tmp_path) as m:
        subprocess.run([sys.executable, "-c", "x = [0] * 10_000_000"], check=True)
        (tmp_path / "f").write_bytes(b"x" * 2_000_000)
    rec = m.record
    for k in ("wall_s", "cpu_s", "peak_ram_mb", "gpu", "peak_vram_mb", "disk_written_mb"):
        assert k in rec
    assert rec["peak_ram_mb"] > 50 and rec["disk_written_mb"] >= 1.9 and rec["gpu"] == "none" and rec["peak_vram_mb"] is None
    log = tmp_path / "compute-log.csv"
    row = compute_log_append(log, task="T", what="unit", wall_s=rec["wall_s"], cpu_s=rec["cpu_s"], peak_ram_mb=rec["peak_ram_mb"],
                             peak_vram_mb=None, disk_mb=rec["disk_written_mb"])
    lines = log.read_text().splitlines()
    assert lines[0].split(",") == COMPUTE_LOG_HEADER and len(row) == 9
