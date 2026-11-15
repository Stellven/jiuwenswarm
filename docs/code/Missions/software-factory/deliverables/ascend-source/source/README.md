# Source-lowered STRATA computational core

This independent C++20 project compiles arithmetic and control flow extracted from real production CUDA function bodies. A bounded cooperative CPU runtime executes thread indices, shared memory, block barriers and full-warp shuffles. Unknown helpers, atomics, vectors, templates and divergent collectives fail explicitly. This is CPU reference execution, not validated CUDA/Ascend execution or complete model inference.

    cmake -S . -B build -DSTRATA_CORE_BACKEND=CPU
    cmake --build build --parallel 2
    ctest --test-dir build --output-on-failure
    ./build/strata_engine --input tests/cli-input.txt

An application supplies its own numeric file using this selected contract:

whitespace: N K D; N logits; N*D gate; N*D up; D shared

For multiple independently selected capabilities, pass --operation SOURCE_ID. Function names are accepted only as convenience aliases; source IDs identify exact producers. The bundled tests/cli-input.txt is an isolated arithmetic validation input, not model weights or production inference. Each selected known production source is called through its unique binding and receives an operation_checks result from its independent reference in tests/numerical.cpp. Aggregate comparison counts do not prove coverage of other sources. Arbitrary discovered scalar arithmetic requires a task-provided semantic oracle; zero reference comparisons must not be treated as correctness validation.

STRATA_CORE_BACKEND=ASCEND compiles src/strata_native.cpp and src/ascend/*.cpp, with no cooperative CPU kernels in that target. Concrete CANN graphs implement router softmax/stable-sort/top-k/clamped renormalization, SiLU-times-up activation, ordered weighted expert aggregation with optional shared addition, and stride-32 weighted RMS normalization when their complete immutable source contracts are recognized. Unsupported selected source contracts fail ASCEND configuration before SDK discovery. native/manifest.json records each bound source/function hash, graph, actual API-header evidence, and generated/compiled/device/equivalence status separately.

    cmake -S . -B build-ascend -DSTRATA_CORE_BACKEND=ASCEND
    cmake --build build-ascend --parallel 2
    ctest --test-dir build-ascend --output-on-failure

The standalone preparation runner checks source hashes without accessing hardware:

    python scripts/prepare_ascend.py --check-source-only

With actual prerequisites supplied, --compile performs only target compilation; --validate additionally executes the native operator comparisons. Its report records each layer separately and never marks full-model inference passed.

Native compilation requires actual CANN headers/libraries; execution requires a real Ascend device. Router/activation/combination candidate FP32 graphs differ from production FP64 intermediates. Task-tolerance comparisons and exact expert-index/stable-tie checks on the actual device remain mandatory. Source generation and CPU tests never establish native numerical equivalence. This computational-core project has no model loader or token-generation implementation; full-model status remains NOT_RUN and requires the separate integrated model path.

Source casts, expression ordering and collective structure are retained. CPU exp/rsqrt implementations may differ from device math intrinsics; CPU checks do not establish GPU bit equality. The independent upstream router host reference uses double probabilities whereas production selection rounds them to float; tests separately cover the production tie case.
