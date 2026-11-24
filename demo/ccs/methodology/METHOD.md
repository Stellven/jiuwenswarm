# Synthetic compute evaluation method

1. Use cc_list and cc_describe to discover the demo CCs and their ports,
   materials, required resources, and declared effects. Read this method and limits.
2. Ensure demo.compute_service was built with build_image.py and its image ID
   identifies the built application. Ask the host to grant declared effects.
3. Start demo.compute_service capability api with a stable operation key.
   Require state running and readiness ready; retain the instance identifier.
4. Pass the returned host-issued environment handle to
   demo.service_client capability benchmark as engine, with a workload such as
   {"points": [0, 1, 3]}. If the host API returns endpoints rather than a handle,
   have the host register an environment resource with the api URL and instance
   identifier, then use that host-issued resource handle. Do not invent a handle.
5. Inspect the assigned workspace with demo.workspace_inspect capability inspect,
   using its workspace handle. Retain summary.json and series.json artifacts.
6. Stop the service instance in a finally/cleanup step, including after failures.
   Inspect the stop result and confirm state stopped before claiming cleanup.

The service shows HTTP lifecycle and synthetic multiplication correctness.
Runtime metadata describes the service's OS and Python; it is not attestation.
Client metrics describe loopback HTTP requests including Python client overhead.
Workspace results describe bounded file inventory and simple structural metadata.
None of these establish model quality, inference TTFT, token throughput, or
production performance. Empty results may be valid successful observations.

Never report success when a receipt is failed, blocked, or unknown. Partial
receipts retain observations but do not establish workload completion. Report the
failure and evidence limits. Retry an identical operation with the same key;
do not change inputs or grants under that key. If effects are denied, a host
grant is required; obtain authorization and use a new key for a changed request.
An unknown execution needs host reconciliation before a fresh execution.
