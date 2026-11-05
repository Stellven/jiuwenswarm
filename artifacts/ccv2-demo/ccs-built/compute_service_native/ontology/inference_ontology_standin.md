# STAND-IN: synthetic service vocabulary

This is a short ontology stand-in, not a real inference specification.
No model execution, inference benchmark, or inference-quality claims are made.

- engine: a served synthetic HTTP compute application.
- health: GET /health returns {"status": "ok"} after startup.
- point / x: a finite numeric query input to GET /compute?x=...
- factor: the synthetic multiplier, fixed at 2.
- value: x multiplied by factor; a finite numeric response.
- runtime.platform: service process platform description.
- runtime.python: service process Python version.
- runtime.os_release: PRETTY_NAME from /etc/os-release, or null if absent.
- workload: an ordered list of numeric points.
- client_ms: elapsed client HTTP request duration, including client overhead.
- series: retained successful per-point rows, not a token stream.
- TTFT / token rate: unavailable; this service produces no inference tokens.
- readiness: HTTP startup observation, not performance or quality evidence.
