You are the build agent. A request Capability Capsule describes a service that does not exist yet: `requests/compute_service_native.request.yaml` in your working directory, with `requests/README.md` explaining how to implement it and `requests/ontology/` holding its construction material.

Your job: implement it as a real CC and prove it works through the governed tools.

1. Use `cc_list` to confirm the request is not executable (it must not appear as a usable CC). Read the request file and README with your shell tools.
2. Create the implemented package at `built-ccs/compute_service_native/` (a `cc.yaml` with `cc: '2'`, a stdlib-only Python HTTP server, `api.json`, and a copy of the ontology material). Do not modify anything under `requests/`. The native command must use `{python}`, `{bundle}` and `{port.api}`. Keep every claim synthetic: no real inference.
3. Call `cc_list` again. Confirm your package is now listed and usable. If it reports an error, read the error, fix the package, and list again.
4. Start its `api` capability with `cc_start`, then use the returned `handle` with `demo.service_client` `benchmark` and workload `{"points": [2, 4, 8]}`. Verify the values.
5. Stop it with `cc_stop` and report the confirmed state.
6. Report exactly what you created, each tool result's state, and anything you could not do. Do not claim success for a step whose receipt or state says otherwise.
