"""Simulator process for the X1.1 local-feasibility run (PAS-M1-001 B13).

Steps a MuJoCo pendulum scene with active contact for a fixed wall time and
reports what it did and what it cost. It is a real MuJoCo process, not a stub;
it exists so X1.1 can run before the experiment core does (ARCH build order).
"""
from __future__ import annotations

import argparse
import json
import math
import resource
import sys
import time

SCENE = """
<mujoco model="x11-pendulum-and-box">
  <option timestep="0.001" integrator="RK4"/>
  <worldbody>
    <geom name="floor" type="plane" size="2 2 0.1"/>
    <body name="arm" pos="0 0 1.2">
      <joint name="hinge" type="hinge" axis="0 1 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.02" mass="1"/>
    </body>
    <body name="box" pos="0.5 0 0.3">
      <freejoint/>
      <geom type="box" size="0.05 0.05 0.05" mass="0.5"/>
    </body>
  </worldbody>
</mujoco>
"""


def run(wall_s: float, report_every_s: float) -> dict:
    import mujoco  # noqa: PLC0415

    model = mujoco.MjModel.from_xml_string(SCENE)
    data = mujoco.MjData(model)
    data.qpos[0] = math.radians(60.0)
    t0 = time.monotonic()
    c0 = time.process_time()
    steps = 0
    samples = []
    next_report = report_every_s
    nonfinite = 0
    while (elapsed := time.monotonic() - t0) < wall_s:
        for _ in range(1000):
            mujoco.mj_step(model, data)
        steps += 1000
        if not all(math.isfinite(x) for x in data.qpos):
            nonfinite += 1
            mujoco.mj_resetData(model, data)
        if elapsed >= next_report:
            samples.append({"t_wall_s": round(elapsed, 3), "steps": steps, "sim_time_s": round(data.time, 3)})
            print(json.dumps({"progress": samples[-1]}), file=sys.stderr, flush=True)
            next_report += report_every_s
    wall = time.monotonic() - t0
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "record": "simlab-feasibility-sim",
        "mujoco": mujoco.__version__,
        "wall_s": round(wall, 3),
        "cpu_s": round(time.process_time() - c0, 3),
        "steps": steps,
        "steps_per_s": round(steps / wall, 1),
        "sim_time_s": round(data.time, 3),
        "ncon_final": int(data.ncon),
        "nonfinite_resets": nonfinite,
        "peak_rss_mb": round(ru.ru_maxrss / 1024, 1),
        "samples": samples,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="simlab feasibility-sim")
    ap.add_argument("--wall-s", type=float, default=60.0)
    ap.add_argument("--report-every-s", type=float, default=5.0)
    args = ap.parse_args(argv)
    print(json.dumps(run(args.wall_s, args.report_every_s), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
