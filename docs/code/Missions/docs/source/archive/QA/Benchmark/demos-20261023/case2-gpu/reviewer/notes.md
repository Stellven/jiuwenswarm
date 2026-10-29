# Reviewer only — never upload this file

This is a small demonstration, not M1 acceptance. Expected outcome: supported if an actual qualified tensor-core GPU measurement shows FP16/FP32 <=0.70; otherwise report the measured negative or ENVIRONMENT_BLOCKED.

Manual checklist (leave unchecked until a human reviews the saved evidence):
- [ ] The actual host, checkout commit, installed build and observed model are recorded.
- [ ] Expected stages: Compiler and Planner, then the complete scientific DAG only on an approved CUDA executor. Record missing stages and the earliest stop reason.
- [ ] Capsule verifiers and deterministic gates advanced or blocked for a documented reason.
- [ ] Claims cite only the supplied public inputs. Reviewer files were not uploaded.
- [ ] Every reported measurement traces to original raw outputs and an actual execution.
- [ ] No missing number, prediction or timing is fabricated.
- [ ] Execution/collection outcomes are distinguished from research quality.

Assessment:

Evidence references:

Review notes:


User subsequently deferred execution: build Case 2 only, do not run it now. Physical host has an RTX 4060 Laptop GPU, but the current AI4R container has no GPU device request/PyTorch and its approved benchmark capsule measures accuracy only. No GPU timing has been taken. Reviewer repeat: run measure_gpu.py on the same approved GPU with the same environment, then compare raw arrays/ratio; do not use a different host as if it were the app experiment.
