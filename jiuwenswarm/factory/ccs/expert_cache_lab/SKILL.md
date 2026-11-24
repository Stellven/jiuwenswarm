---
name: expert-cache-lab
description: Validate expert traces, replay byte bounded caches and evaluate causal next expert predictions.
---

Prediction forecasts atomic request/token/layer expert sets before observing any selected expert. Use group-boundary chronological splits or explicit frozen request holdout; it does not establish next-token runtime or prefetch readiness. Read [METHOD.md](METHOD.md) for schemas and assumptions. Invoke the native tools with one `inputs` JSON object. Import bundled `components.py` only in an explicit integration; no host API dependency is required. Run `verification.py` for attached CPU checks. These results certify local reference invariants only; they grant no factory qualification or GPU performance claim. Source provenance is in [SOURCES.json](SOURCES.json).
