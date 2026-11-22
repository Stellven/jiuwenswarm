---
name: precision-lab
description: Calibrate and evaluate tensor precision using a portable INT4 CPU reference and explicit approximation budgets.
---

Use the inline `request` JSON tools listed in cc.yaml. Examples are in fixtures/. Read [METHOD.md](METHOD.md) for integration hooks and [SOURCES.json](SOURCES.json) for verified provenance. Run `python verification.py` for standalone reference checks.

Qualification is CPU reference only. Inputs cannot name executable code, files, or network endpoints. Supplied timings are observations, not hardware measurements made by this package. Preserve every selected expert and original router coefficient. Quantization changes numerics and must use a separate quality gate; it never qualifies as an exact execution optimization. No CUDA or GB10 speed result is claimed.
