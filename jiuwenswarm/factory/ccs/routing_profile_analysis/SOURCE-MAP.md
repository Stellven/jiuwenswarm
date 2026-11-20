# Source map

The read-only Strata checkout used for inspection was at `ffa80d73133ea5c548aefe57889a16e8085a938f`. The prior run's engine receipt is the identity of the executable that generated the counters.

| Source file and anchor | Method dependency | File SHA-256 |
| --- | --- | --- |
| `src/dsv41/ds4_model.cu` 3490–3508, 5546–5550, 11760–11767, 14307–14332, 14802–14811 | Main and drafter row layout, stable count ordering, route increments and uint32 persistence | `26c5b9ddb8d34dc93fa2694f2adf4f45da6900ae18ec78cae4bb9652c87f2ba6` |
| `src/dsv41/ds4_experts_rule.hpp` 54–64 | Shape admission and drafter rows | `7616389d112574eada6dba931ae77f6c9a6a4c2ff75261ce2ea9cce2d7c279e6` |
| `src/dsv41/ds4_packinfo.cpp` 79–113, 153–193 | Tensor index fields and `w1`/`w2`/`w3` payload accounting | `c06f88534a1aabc7aba53e46f10e4a52d43b212604f9d32476afee20154a9768` |

The DeepSeek V4.1 Flash pack metadata used for the historical Spark analysis declares 40 main layers and 384 routed experts per layer. Its `ds4.txt` SHA-256 is `f3c3271a8604f4394fc715bc45b38d8ab298407d97f71cc33d92afd1b28de4d0`. The report binds the profile and index inputs independently. The CC reads only those metadata artifacts.

## Recorder comparison sources

| Source and anchor | Method dependency | SHA-256 |
| --- | --- | --- |
| llama.cpp recorder commit `9d0733cba12c164827b646ea86af618ce7b5ca47`, `src/llama-event-recorder.cpp` 291–342, 444–485, 487–607 | Route matrix, submitted-copy observation, row tags, unknown transfer and final summary | `824e3d69c3ddc14460acf370489fe04d5e3a52cb140fc40ca2464b1e15b49d2f` |
| Retained `convert_ds41_upstream.py` 346–393, 451–499 | This campaign maps layer/expert IDs directly. Ordinary quantized tensors retain their names, shape and byte order through conversion. | `183614c38666af34174d71b5e593f2d12d1b25f5a02d9c0c7184f1f2cc0274f5` |

The historical C1 trace was produced with the recorder gate active, the converted DeepSeek text model and the strict stock placement profile. It demonstrates coverage on that functional probe. It is not a timed comparison or a held-out corpus.

## Copy timing sources

| Source and anchor | Method dependency | SHA-256 |
| --- | --- | --- |
| Recorder commit `9d0733cba12c164827b646ea86af618ce7b5ca47`, `src/llama-context.cpp` 3170–3281 | Cache-disabled host-weight copy path, grouping consecutive expert IDs with tail padding, submitted bytes | `cb0feb3baaba4351d8106b333ae7983371d1bf921988b915e4f0e1314ea2c99c` |
| Stock commit `9048bad8d6e3`, `ggml/src/ggml-cuda/ggml-cuda.cu` 3106–3113 | Backend upload issues `cudaMemcpyHostToDevice` on the backend stream | `713eff6e26d4590903be9b0ed7b4b8a8dfd51e1a1af8c85c20e59add514a0ac2` |
| Stock `ggml/src/ggml-backend.cpp` 2089–2147, 2213–2292 | Host weight inputs are copied before their dependent CUDA split. Other input prefetch activity has its own scheduling and is absent from the retained replay. | `4ea348d41d6fc5747906d9d3784ff3e15886ad40bce09c9cc9d6da6f2247314f` |
| `ops/spark/replay_expert_copies.py` in JiuwenSwarm commit `2cb7c5718` | Layer-by-layer reconstruction of the exact timed copy ranges and replay receipt | See bundled copy replay source evidence |
