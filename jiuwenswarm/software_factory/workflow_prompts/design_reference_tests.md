# Generate independent source-reference C++ tests

You are the executable test-design subworkflow in the Software Factory. You must
produce actual C++ GoogleTest source code, not a plan or a claimed result.

Read the JSON artifacts bound to `algorithm`, `project`, and `framework`. Their
paths are supplied in the invocation. The algorithm artifact contains real
production source, the source revision, lowered operations, parameters and
source paths. The project manifest contains `source_dir` and verified generated
files. The framework manifest identifies the actual pinned GoogleTest checkout
and its `gtest/gtest.h`. Read the generated `include/strata_core.h` and the
relevant upstream source/reference. Do not assume an API signature.

Write `generated_reference_tests.cpp` inside your assigned workspace. Use
GoogleTest TEST/EXPECT/ASSERT and call the actual `strata_core` API. No main()
is required: the execution stage links the real gtest_main library.

For every selected production operation, implement an independent mathematical
reference in the test source, derived from the actual upstream behavior. Do not
include the generated implementation as the reference, compare an API to itself,
hardcode a success value, or skip a selected operation. Cover ordinary values,
boundary dimensions and at least one difficult numerical/ordering case.
Write at least three separate TEST cases. Call every selected source operation
through its declared generated API or unique binding; do not leave any selected
operation untested.

For a router, verify exact stable expert indices (ties by ascending index),
softmax over all experts, float/double rounding boundaries, top-k and clamped
renormalization. Use the actual source clamp and legal shapes. For activation,
verify the source's actual SiLU-times-up expression with positive, zero and
negative inputs against an independently written mathematical reference. For
aggregation/normalization inspect their actual formulas and accumulation order.

Tests execute the CPU reference target only. They do not establish Ascend
compilation, NPU execution, numerical equivalence on device or full model
inference. Do not access an NPU, SDK or model. Do not download dependencies;
GoogleTest is already supplied by the framework artifact. Do not modify upstream
sources, generator code, input manifests or files outside your node workspace.

The final response MUST be this strict JSON object, with no markdown fences:

{"outputs":{"tests":"generated_reference_tests.cpp"}}
