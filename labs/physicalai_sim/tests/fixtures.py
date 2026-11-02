"""Shared experiment builders for SIMLAB tests. Everything goes through the tool interface."""
from __future__ import annotations

import copy

import mujoco

PENDULUM = """<mujoco model="pendulum">
  <option timestep="0.001"/>
  <worldbody>
    <body name="bob" pos="0 0 2">
      <joint name="hinge" type="hinge" axis="0 1 0" damping="${damping}"/>
      <inertial pos="0 0 -${L}" mass="${m}" diaginertia="1e-9 1e-9 1e-9"/>
    </body>
  </worldbody>
</mujoco>"""

BOX_DROP = """<mujoco model="box-drop">
  <worldbody>
    <geom name="floor" type="plane" size="2 2 0.1"/>
    <body name="box" pos="0 0 ${z0}">
      <freejoint name="free"/>
      <geom name="box_geom" type="box" size="0.05 0.05 0.05" mass="0.5"/>
    </body>
  </worldbody>
</mujoco>"""

ACTUATED = """<mujoco model="actuated-pendulum">
  <worldbody>
    <body name="arm" pos="0 0 1">
      <joint name="hinge" type="hinge" axis="0 1 0" damping="0.05"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.02" mass="1"/>
    </body>
  </worldbody>
  <actuator><motor name="torque" joint="hinge" ctrlrange="-5 5"/></actuator>
</mujoco>"""

PD_CONTROLLER = '''
def control(obs, params, ctx):
    q, v = obs["qpos"][0], obs["qvel"][0]
    return [params.get("kp", 5.0) * (params.get("target", 0.5) - q) - params.get("kd", 0.5) * v]
'''

CONFIG = {"engine": "mujoco", "timestep": 0.001, "integrator": "RK4", "solver": "Newton", "iterations": 100, "tolerance": 1e-10}


def header(**over) -> dict:
    h = {
        "objective": "Pendulum period across lengths",
        "objective_kind": "mechanism",
        "engines": [{"engine": "mujoco", "version": mujoco.__version__, "why": "admitted executor; analytic pendulum needs rigid hinge dynamics"}],
        "resolved_configuration": dict(CONFIG),
        "arms": [{"arm_id": "a", "role": "baseline", "components": [{"extension_point": "scene", "artifact": "pendulum.xml"}],
                  "params": {"L": 1.0, "m": 1.0, "damping": 0.0}}],
        "design": {"replicates": 1, "episodes": 1, "randomness": {"seed_policy": "derived", "base_seed": 7}},
        "limits": {"max_sim_time_s": 30, "max_wall_s": 120},
        "protocol_items": [{"item_id": "arms", "item_kind": "arm", "value": "a", "origin": "requester_declared"}],
    }
    h.update(copy.deepcopy(over))
    return h


PROCEDURE = {"steps": [{"step_id": "swing", "duration_s": 6.0}], "initial_state": {"qpos": {"hinge": 0.2}}}
PERIOD = {"measurement_id": "period", "scope": "trial", "unit": "s", "required": True,
          "definition": {"kind": "period", "signal": "qpos:hinge", "direction": "up"}}
QPOS = {"signal": "qpos:hinge", "unit": "rad", "rate_hz": 1000}


def build(client, *, scene=PENDULUM, scene_path="pendulum.xml", head=None, procedure=None, measurements=(PERIOD,),
          observations=(QPOS,), components=(), bind_header=None) -> dict:
    d = client.draft_create(header=head or header())["draft_id"]
    client.model_file_put(draft_id=d, path=scene_path, content=scene)
    client.procedure_put(draft_id=d, procedure=procedure or PROCEDURE)
    for m in measurements:
        client.measurement_put(draft_id=d, measurement=m)
    for o in observations:
        client.observation_put(draft_id=d, observation=o)
    for path, ep, code in components:
        client.component_put(draft_id=d, path=path, extension_point=ep, code=code)
    b = client.bind(draft_id=d, header=bind_header)
    b["draft_id"] = d
    return b

STIFF = """<mujoco model="stiff-slider">
  <worldbody>
    <body name="mass">
      <joint name="s" type="slide" axis="1 0 0" stiffness="1e12"/>
      <geom type="sphere" size="0.1" mass="0.001" contype="0" conaffinity="0"/>
    </body>
  </worldbody>
</mujoco>"""

BOX_STACK = """<mujoco model="box-stack">
  <worldbody>
    <geom name="floor" type="plane" size="2 2 0.1"/>
    <body name="b1" pos="0 0 0.05"><freejoint name="f1"/><geom name="g1" type="box" size="0.05 0.05 0.05" mass="1"/></body>
    <body name="b2" pos="0 0 0.15"><freejoint name="f2"/><geom name="g2" type="box" size="0.05 0.05 0.05" mass="1"/></body>
  </worldbody>
</mujoco>"""


def scene_arm(arm_id="a", role="baseline", artifact="pendulum.xml", params=None, extra=()):
    return {"arm_id": arm_id, "role": role, "components": [{"extension_point": "scene", "artifact": artifact}, *extra],
            "params": params if params is not None else {"L": 1.0, "m": 1.0, "damping": 0.0}}


def wait_result(client, run_id, timeout_s=300):
    client.wait(run_id=run_id, timeout_s=timeout_s)
    return client.result(run_id=run_id)


def run(client, built, timeout_s=300):
    r = client.submit(experiment=built["experiment"])
    assert "run_id" in r, r
    return wait_result(client, r["run_id"], timeout_s)


def attempts(res):
    return [a for t in res["trials"] for a in t["attempts"]]
