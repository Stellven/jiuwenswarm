# Implementing the native compute request

compute_service_native.request.yaml is a non-executable cc-request/2 design.
Its desired section describes the service itself, not a tool for generating one.

1. Read desired and resolve open questions with their named owners.
2. Create demo/ccs/compute_service_native/ without modifying the request.
3. Write the native HTTP server, api.json, and cc.yaml (cc: '2').
   Supply a native command using {python}, {bundle}, and {port.api}.
4. Copy ontology/inference_ontology_standin.md into that package and preserve
   its stand-in label. Material paths are relative to their containing package.
5. Implement the stated health, compute, and runtime vocabulary. Keep claims
   synthetic; do not silently substitute real inference semantics.
6. Prepare the implemented directory with Host.prepare, start api with granted
   process.exec/network.listen, check readiness, exercise the API, then stop it
   and confirm stopped. Only this implemented package may execute.

Host.call and Host.start accept prepared implementation releases. Passing the
request file to either must be refused; preparing a request as cc.yaml must also
be refused. Resolve implementation and contract gaps before preparing a release.
