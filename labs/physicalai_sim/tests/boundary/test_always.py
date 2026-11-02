"""V-ALWAYS (AC-019): during a real run no SIMLAB host port exists, the executor cannot reach the network, and its
environment holds no credentials even when the service's own environment does."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import fixtures as F
from conftest import start_service
from fixtures import header, run, scene_arm
from simlab.interface.client import Client

LAB = Path(__file__).resolve().parents[2]
PROBE = '''
import os, re, socket
def control(obs, params, ctx):
    leaked = [k for k in os.environ if re.search("TOKEN|SECRET|KEY|PASSWORD|AUTH|CREDENTIAL", k, re.I)]
    if leaked:
        return [float("nan")]
    if not ctx.state.get("tried"):
        ctx.state["tried"] = True
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=1)
            return [float("nan")]
        except OSError:
            pass
    return [0.0]
'''


def test_no_port_no_network_no_credentials(tmp_path):
    proc = start_service_with_secret(tmp_path)
    try:
        client = Client(tmp_path)
        arm = scene_arm(artifact="act.xml", params={}, extra=[{"extension_point": "controller", "artifact": "probe.py"}])
        b = F.build(client, scene=F.ACTUATED, scene_path="act.xml", head=header(arms=[arm], resolved_configuration={**F.CONFIG, "timestep": 0.0001}),
                    procedure={"steps": [{"step_id": "s", "duration_s": 8.0}]}, measurements=(), components=[("probe.py", "controller", PROBE)])
        sub = client.submit(experiment=b["experiment"])
        deadline = time.monotonic() + 60
        while client.status(run_id=sub["run_id"])["status"] != "RUNNING":
            assert time.monotonic() < deadline
            time.sleep(0.05)
        audit = subprocess.run([sys.executable, str(LAB / "tools" / "port_audit.py"), "--json"], capture_output=True, text=True)
        rep = json.loads(audit.stdout)
        assert rep["result"] == "PASS", rep["problems"]
        res = F.wait_result(client, sub["run_id"])
        a = res["trials"][0]["attempts"][0]
        assert a["status"] == "COMPLETED", a
        events = client.query(run_id=res["run_id"])["events"]
        assert any(e["kind"] == "confinement_denial" and e["detail"]["kind"] == "network" for e in events)
    finally:
        proc.terminate()
        proc.wait(10)


def start_service_with_secret(data_dir: Path):
    os.environ["SIMLAB_PLANTED_SERVICE_TOKEN"] = "planted-not-real"
    try:
        return start_service(data_dir)
    finally:
        os.environ.pop("SIMLAB_PLANTED_SERVICE_TOKEN", None)
