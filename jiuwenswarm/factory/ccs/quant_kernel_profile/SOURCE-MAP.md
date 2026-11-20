# Source map

All file bytes below were verified against the pinned local commits.

- llama.cpp revision 9048bad8d6e3a0f9f1726e238e451181c7e02613
- Strata revision ffa80d73133ea5c548aefe57889a16e8085a938f

| Engine and source anchors | Device | Source role | SHA-256 |
| --- | --- | --- | --- |
| llama.cpp ggml/src/ggml-cuda/ggml-cuda.cu (2252, 2412, 2554, 2598) | GPU | MUL_MAT and MUL_MAT_ID dispatch select MMVQ, few-row MMQ, MMQ or fallback by type, device, shape and fusion predicates. | 713eff6e26d4590903be9b0ed7b4b8a8dfd51e1a1af8c85c20e59add514a0ac2 |
| llama.cpp ggml/src/ggml-cuda/mmq.cu (51, 69, 291, 372, 395) | GPU | IQ2_XXS and IQ4_NL instantiate MMQ. Activation staging can quantize to Q8_1. | db3e2bc1123d7869a61a8ef02b8cb871290a765f09376d36c9f0273e7fbb4ecf |
| llama.cpp ggml/src/ggml-cuda/mmq.cuh (684, 720, 854, 890) | GPU | Format-specific MMQ tile unpack/load and integer dot or MMA are attributed to the combined kernel. | 046ef1826125736e4a966766b2476cb37ae53b55b6f2181ec7edf11db51a5182 |
| llama.cpp ggml/src/ggml-cuda/mmq-few.cu (37, 80, 861) | GPU | Few-row MMQ admits IQ4_NL under its shape and backend gates. IQ2_XXS is absent from that supported-type predicate. | 5c0451121f41c42e0267c59b06fbe7a62871e13889277f702ca982a08106ee88 |
| llama.cpp ggml/src/ggml-cuda/mmvq.cu (52, 58, 1401, 1437) | GPU | IQ2_XXS and IQ4_NL dispatch to their Q8_1 dot kernels on the admitted small-column shapes. | 11c41a96e5a7ce60c56d0f20236ca2ec974f016da2f5feafbe49d3d0850659e9 |
| llama.cpp ggml/src/ggml-cuda/vecdotq.cuh (1108, 1393) | GPU | The type-specific in-kernel quantized dot products fuse block unpack with dot arithmetic. | 5e6882fe30b86f2f1ba294542ec88866c962e8f90500d4e035882eff3942f975 |
| llama.cpp ggml/src/ggml-cuda/convert.cu (522, 534, 584, 596, 643, 655) | GPU | Type-specific standalone conversion/dequant dispatch is available. A conversion kernel must be observed to assign time. | 38f99f4d21e490639ed03f1cda1bdf9637e057c11b869dfc79ac6704129631fe |
| llama.cpp ggml/src/ggml-cuda/getrows.cu (371, 399) | GPU | Quantized row gather has distinct IQ2_XXS and IQ4_NL dequant cases. | 1a14a69383ab655fdb248b3b697646ac9bdd07a07198d511f8e34a2fb976b9b8 |
| llama.cpp ggml/src/ggml-cpu/ggml-cpu.c (346, 389) | CPU | IQ2_XXS uses the Q8_K row-dot trait and IQ4_NL uses Q8_0. | e6f33c7ecbe5eeb6cce487b6aad7ce4932800894d3e33269f0157feaaf74e769 |
| llama.cpp ggml/src/ggml-cpu/arch/arm/quants.c (3634, 3692, 4199) | CPU | ARM IQ2_XXS and IQ4_NL vector-dot implementations and conditional fallbacks. | 7b6d89b7172770442c5fe580c5f75c792d3f51ebdd81c56a065765dd6edede8a |
| llama.cpp ggml/src/ggml-cpu/repack.cpp (3975, 5077) | CPU | IQ4_NL has a conditional NEON dot-product packed trait on compatible shapes. The packed trait dispatcher has no IQ2_XXS branch. | 159d4e6e863ca3d39e0ba0ab4fa3b10be7d0c778f6d59f2baea07dcab00c744a |
| llama.cpp ggml/src/ggml-cpu/arch/arm/repack.cpp (449, 3429) | CPU | ARM IQ4_NL 4x4 packed GEMV/GEMM implementations. Availability does not show that this pack uses them. | eb7f06d503adec539f44c7899a3588fcc94c319f25eb1a5f67aeee63aa1837c2 |
| llama.cpp ggml/src/ggml-cpu/ops.cpp (5235, 5402) | CPU | Quantized CPU row gather applies the type dequant trait. | e6b36a3745a3463e99b13488277effbe8bb365b183f9655393361c4f9c5199c5 |
| llama.cpp ggml/src/ggml-quants.c (2504, 2741) | CPU | Standalone portable IQ2_XXS and IQ4_NL row dequantization. | bcda33625707fdfcb1367cdd2bb1a2f017430162ec9623abc84ad17459698f73 |
| llama.cpp src/models/deepseek41.cpp (372, 799) | placement-dependent | The model graph gathers IQ4_NL Engram rows; this lookup has different semantics from routed expert matmul. | 73916d555f7d664c43e54eecb0da8392693d940271a5268d0291ab98b0f8283d |
| Strata src/dsv41/ds4_iq.cu (40, 51, 61, 172, 279, 606, 1109, 1461, 1476, 1504) | GPU | Native GGUF IQ kernels implement typed block unpack, fused expert token/matrix paths and separate dequant dispatch. | 1af90fbbe5cf8b9a8d4d3ce03d4df49bc7d8e508281b04c89cc6416e0a0bbd76 |
| Strata src/dsv41/ds4_iq_cpu.cpp (9, 31, 645, 743, 899, 903) | CPU | The checked source undefines Maya native-expert dispatch. Its reachable fallback delegates to gg_cpu_fmt when present. The AVX path is not an ARM dispatch. | adb4d698213d3e127d3190886470defa4c0625f6bc8be069fbe42547a46e4d0c |
| Strata src/dsv41/ds4_gg_cpu.cpp (12, 36, 50) | CPU | When built with STRATA_DSV41_TQ_CPU, types 16 and 20 delegate to linked ggml-cpu traits with their own activation format and row shape. | c619195f421a22d564ef4a67795f18db726a5720dce3e2825db3f0fcb3c32347 |
| Strata src/dsv41/ds4_model.cu (3483, 7827, 11409, 14008) | placement-dependent | Engram format and row hooks are separate from routed experts, and use dedicated dequant at both GPU graph sites. | 26c5b9ddb8d34dc93fa2694f2adf4f45da6900ae18ec78cae4bb9652c87f2ba6 |
| Strata src/dsv41/ds4_kernels.cu (1543, 1967, 2331, 2637) | GPU | Engram rows use dedicated kernels including their IQ4_NL format branch. | cdd77c53aeadcd0bb1d23cf35faa1a3abf5d7ea982868ee3c34a2040d36131bc |
| Strata src/dsv41/ds4_tq.cu (1, 164) | adjacent | This implements distinct trellis TQ formats. It is a boundary reference and not evidence of IQ2_XXS or IQ4_NL execution. | 46d762e2b530557c705dc83312388b57efebd675921683b41f5553fd2634cd55 |

The retained Strata DeepSeek V4.1 Flash 2.00 bpw pack tensor index SHA-256 is f76a9f456b3f59dff7870366e6c4406a46b7c85cc8c805a6220fde96a376a28c. The index describes storage types and tensor roles. The retained conversion proves byte-preserving weights for the matched llama.cpp pack. Source eligibility and pack composition provide no timed kernel utilization.
