You are the lab agent. Evaluate the synthetic compute engine using your Capability Capsules (the `cc` tool server). Follow the methodology CC's `method` material; do not skip its steps. Report only what you observed.

1. Start the image-backed service `demo.compute_service` capability `api` with `cc_start`. Report its state, readiness, endpoint, and the image identity it ran from (use `cc_instance` if the start result does not show it).
2. Using the `handle` returned by the start, run `demo.service_client` capability `benchmark` with workload `{"points": [1, 2, 3, 4, 5]}`. Report count, values, p50/p95 client milliseconds, the server `runtime` block (which OS the service reported), and the retained `series` artifact.
3. Call the same benchmark again with the SAME `key` you used the first time and say whether it ran again or returned the earlier receipt.
4. Stop the instance with `cc_stop` and report the confirmed state. If it is not `stopped`, say so plainly.
5. State clearly that the timings are synthetic loopback client timings and say nothing about inference-engine latency or throughput.
