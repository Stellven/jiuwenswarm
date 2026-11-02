"""Design expansion: arms x conditions x replicates x episodes -> trials (PAS-M1-001 B05; PRD SL-3.D).

Deterministic: the same experiment always expands to the same ordered trial
set with the same seeds. Paired designs give every arm in a pair the same
seeds; unpaired designs derive a seed per arm.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from simlab.contracts.records import Experiment
from simlab.validation import conditions_of, split_settings


def derive(*parts) -> int:
    return int.from_bytes(hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).digest()[:8], "big") >> 1


def sample_random_variables(exp: Experiment, seed: int) -> tuple[dict, list[str]]:
    rng = np.random.default_rng(seed)
    out, outside = {}, []
    for rv in exp.design.randomness.random_variables:
        d = rv.distribution
        if d.kind == "normal":
            v = float(rng.normal(d.mean, d.std))
        elif d.kind == "uniform":
            v = float(rng.uniform(d.low, d.high))
        else:
            v = d.choices[int(rng.integers(len(d.choices)))]
        out[rv.name] = v
        if rv.bounds is not None and isinstance(v, (int, float)) and not (rv.bounds[0] <= v <= rv.bounds[1]):
            outside.append(rv.name)
    return out, outside


def expand(exp: Experiment) -> list[dict]:
    conds, _ = conditions_of(exp.design)
    r = exp.design.randomness
    paired = exp.design.pairing == "paired"
    trials = []
    ordinal = 0
    for cid, settings in conds:
        params_c, config_c = split_settings(settings)
        for rep in range(exp.design.replicates):
            for ep in range(exp.design.episodes):
                pair_id = f"{cid}|r{rep}|e{ep}" if paired else None
                for arm in exp.arms:
                    if r.seed_policy == "fixed":
                        trial_seed = int(r.base_seed)
                    else:
                        trial_seed = derive(r.base_seed, cid, rep, ep, "*" if paired else arm.arm_id)
                    rv_vals, outside = sample_random_variables(exp, derive(trial_seed, "rv"))
                    params = {**arm.params, **params_c, **rv_vals}
                    trials.append({"ordinal": ordinal, "arm_id": arm.arm_id, "condition": cid, "replicate": rep, "episode": ep,
                                   "pair_id": pair_id, "params": params, "config": config_c,
                                   "seeds": {"trial": trial_seed, "rng": derive(trial_seed, "rng"), "random_variables": derive(trial_seed, "rv")},
                                   "rv_outside_bounds": outside})
                    ordinal += 1
    return trials
