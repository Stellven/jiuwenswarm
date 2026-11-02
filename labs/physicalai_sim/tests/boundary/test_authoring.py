"""V-AUTHOR (AC-004): every artifact category through the tools; idempotent bind; immutability; confined components."""
import fixtures as F
from fixtures import header, run, scene_arm

FINGER_SCENE = """<mujoco model="mesh-drop">
  <asset><mesh name="finger" file="meshes/finger.obj"/><mesh name="finger_col" file="meshes/finger_collision.obj"/></asset>
  <worldbody>
    <geom name="floor" type="plane" size="1 1 0.1"/>
    <body name="finger" pos="0 0 0.3">
      <freejoint name="free"/>
      <geom type="mesh" mesh="finger" contype="0" conaffinity="0" mass="0.1"/>
      <geom name="finger_col" type="mesh" mesh="finger_col" mass="0.1"/>
    </body>
  </worldbody>
</mujoco>"""

NOSY = '''
import os, socket
def control(obs, params, ctx):
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=1)
        ctx.state["net"] = "CONNECTED"
    except OSError as e:
        ctx.state["net"] = "denied"
    try:
        open(os.path.expanduser("~/.codex/auth.json")).read()
    except OSError:
        pass
    return [0.0]
'''


def make_draft(service):
    d = service.draft_create(header=header(arms=[scene_arm(artifact="scene.xml", params={})]))["draft_id"]
    g = service.geometry_put(draft_id=d, path="meshes/finger.obj", primitive={"shape": "box", "half_size": [0.02, 0.01, 0.05]})
    c = service.collision_put(draft_id=d, path="meshes/finger_collision.obj", from_geometry={"path": "meshes/finger.obj", "method": "bounding_box"})
    m = service.model_file_put(draft_id=d, path="scene.xml", content=FINGER_SCENE)
    p = service.procedure_put(draft_id=d, procedure={"steps": [{"step_id": "drop", "duration_s": 0.6}]})
    i = service.intervention_put(draft_id=d, intervention={"intervention_id": "nudge", "at_s": 0.5, "action": "apply_force", "target": "finger",
                                                           "value": [0.2, 0, 0], "duration_s": 0.05})
    me = service.measurement_put(draft_id=d, measurement={"measurement_id": "final_z", "scope": "trial", "unit": "m",
                                                           "definition": {"kind": "final", "signal": "xpos:finger", "component": 2}})
    o = service.observation_put(draft_id=d, observation={"signal": "xpos:finger", "unit": "m", "rate_hz": 200})
    return d, [g, c, m, p, i, me, o]


def test_every_category_bind_idempotent_and_runs(service):
    d, puts = make_draft(service)
    assert {p["kind"] for p in puts} == {"geometry", "collision", "model_file", "procedure", "intervention", "measurement", "observation"}
    first = puts[3]["sha256"]
    changed = service.procedure_put(draft_id=d, procedure={"steps": [{"step_id": "drop", "duration_s": 0.7}]})
    assert changed["sha256"] != first, "artifacts can be changed before binding"
    service.procedure_put(draft_id=d, procedure={"steps": [{"step_id": "drop", "duration_s": 0.6}]})
    comp = service.component_put(draft_id=d, path="probe.py", extension_point="measurement",
                                 code="def measure(traces, params):\n    return float(traces['xpos:finger'][-1, 1])\n")
    service.measurement_put(draft_id=d, measurement={"measurement_id": "final_x", "scope": "trial", "unit": "m",
                                                      "definition": {"kind": "component", "artifact": "probe.py"}})
    listed = service.artifact_list(draft_id=d)["artifacts"]
    b = service.bind(draft_id=d)
    m = b["manifest"]
    assert {a["path"]: a["sha256"] for a in m["artifacts"]} == {a["path"]: a["sha256"] for a in listed}
    assert comp["sha256"] in {a["sha256"] for a in m["artifacts"]}
    d2, _ = make_draft(service)
    service.component_put(draft_id=d2, path="probe.py", extension_point="measurement",
                          code="def measure(traces, params):\n    return float(traces['xpos:finger'][-1, 1])\n")
    service.measurement_put(draft_id=d2, measurement={"measurement_id": "final_x", "scope": "trial", "unit": "m",
                                                       "definition": {"kind": "component", "artifact": "probe.py"}})
    b2 = service.bind(draft_id=d2)
    assert (b2["manifest"]["manifest_sha256"], b2["experiment"]["experiment_id"]) == (m["manifest_sha256"], b["experiment"]["experiment_id"])
    try:
        service.model_file_put(draft_id=d, path="scene.xml", content="<mujoco/>")
        raise AssertionError("a bound draft changed")
    except Exception as e:  # noqa: BLE001
        assert getattr(e, "code", "") == "E_BOUND"
    assert service.validate(experiment=b["experiment"])["findings"] == []
    res = run(service, {"experiment": b["experiment"]})
    t = res["trials"][0]
    assert t["attempts"][0]["status"] == "COMPLETED", t
    vals = {x["measurement_id"]: x["value"] for x in t["measurements"]}
    assert 0.0 < vals["final_z"] < 0.1 and vals["final_x"] > 0.0, vals
    assert any(e["kind"] == "intervention" and e["event_id"] == "nudge" for e in service.query(run_id=res["run_id"])["events"])
    tampered = dict(b["experiment"], objective="changed after bind")
    assert "E_SEMANTIC_MANIFEST_BINDING" in [f["code"] for f in service.validate(experiment=tampered)["findings"]]
    sub = service.submit(experiment=tampered)
    assert "findings" in sub and "run_id" not in sub


def test_extension_point_and_confinement(service):
    d = service.draft_create()["draft_id"]
    for ep, code, want in (("teleporter", "def control(o, p, c):\n    return []\n", "E_EXTENSION_POINT"),
                           ("controller", "def act(o):\n    return []\n", "E_EXTENSION_POINT")):
        try:
            service.component_put(draft_id=d, path="x.py", extension_point=ep, code=code)
            raise AssertionError("accepted")
        except Exception as e:  # noqa: BLE001
            assert getattr(e, "code", "") == want
    arm = scene_arm(artifact="act.xml", params={}, extra=[{"extension_point": "controller", "artifact": "nosy.py"}])
    b = F.build(service, scene=F.ACTUATED, scene_path="act.xml", head=header(arms=[arm]), components=[("nosy.py", "controller", NOSY)],
                procedure={"steps": [{"step_id": "s", "duration_s": 0.05}]}, measurements=())
    res = run(service, b)
    assert res["trials"][0]["attempts"][0]["status"] == "COMPLETED"
    denials = [e for e in service.query(run_id=res["run_id"])["events"] if e["kind"] == "confinement_denial"]
    kinds = {e["detail"]["kind"] for e in denials}
    assert {"network", "credential_path"} <= kinds, denials
