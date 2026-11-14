# Source-lowered STRATA computational core

This independent C++20 project compiles arithmetic and control flow extracted from real production CUDA function bodies. A bounded cooperative CPU runtime executes thread indices, shared memory, block barriers and full-warp shuffles. Unknown helpers, atomics, vectors, templates and divergent collectives fail explicitly. This is CPU reference execution, not validated CUDA/Ascend execution or complete model inference.

    cmake -S . -B build -DSTRATA_CORE_BACKEND=CPU
    cmake --build build --parallel 2
    ctest --test-dir build --output-on-failure
    ./build/strata_engine --input tests/cli-input.txt

An application supplies its own numeric file using this selected contract:

whitespace: N K D; N logits; N*D gate; N*D up; D shared

For multiple independently selected capabilities, pass --operation SOURCE_ID. Function names are accepted only as convenience aliases; source IDs identify exact producers. The bundled tests/cli-input.txt is an isolated arithmetic validation input, not model weights or production inference. Each selected known production source is called through its unique binding and receives an operation_checks result from its independent reference in tests/numerical.cpp. Aggregate comparison counts do not prove coverage of other sources. Arbitrary discovered scalar arithmetic requires a task-provided semantic oracle; zero reference comparisons must not be treated as correctness validation.

Optional STRATA_CORE_BACKEND=ASCEND requires real CANN headers, libraries and a device. Only a structurally proven SiLU-times-up activation has an explicit native aclnnSilu/aclnnMul implementation; remaining operations are CPU. Changed activation mathematics without a corresponding native implementation fails configuration. There is no silent backend fallback. All native/full-model validation flags remain false until actual target evidence exists.

Source casts, expression ordering and collective structure are retained. CPU exp/rsqrt implementations may differ from device math intrinsics; CPU checks do not establish GPU bit equality. The independent upstream router host reference uses double probabilities whereas production selection rounds them to float; tests separately cover the production tie case.
