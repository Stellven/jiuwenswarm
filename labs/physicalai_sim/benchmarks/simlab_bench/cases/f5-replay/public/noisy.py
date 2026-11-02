def control(obs, params, ctx):
    """PD hold plus seeded noise: deterministic given the trial's random state."""
    return [float(ctx.rng.normal(0.0, params.get("noise", 0.3))) - params.get("kp", 3.0) * obs["qpos"][0] - 0.3 * obs["qvel"][0]]
