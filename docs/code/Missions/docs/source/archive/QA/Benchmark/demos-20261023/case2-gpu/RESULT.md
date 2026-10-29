# GPU demo: built, not run

Execution was explicitly deferred by the user. No app request, GPU preflight or measurement script was run for this case. There are no timings, measured ratio or research conclusion.

The public spec defines a random-weight two-layer transformer, batch 32, ten warm-ups and thirty timed iterations per dtype, CUDA-event timing and FP16/FP32 comparison. public/measure_gpu.py is supplied for the requested independent reviewer repeat on the actual execution host. It refuses a CPU substitute.

The current host inventory sees an RTX 4060 Laptop GPU, but the AI4R app container has neither a GPU binding nor PyTorch. The current benchmark capsule also supports accuracy rather than GPU latency. A later run needs an approved CUDA/PyTorch executor and latency support; current setup records ENVIRONMENT_BLOCKED instead of silently using CPU. This was not executed and is not reported as an observed blocked run.

Reviewer files are outside mounted inputs. No app configuration was changed to make this case pass.
