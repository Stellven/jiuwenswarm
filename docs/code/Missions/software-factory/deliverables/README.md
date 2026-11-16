# Factory-generated source projects

Each directory contains the exact source ZIP published by its recorded factory
run and the extracted C++ project. CMake, source code, headers, reference excerpts
and tests are included. The projects build independently of the host factory.

| Project | Source-selected operations | Recorded run |
| --- | --- | --- |
| [core](core/source/README.md) | Routing, SwiGLU, expert-output aggregation | `6db7a2b968c8434eaa9a508a6d16a7cf` |
| [normalization](normalization/source/README.md) | Weighted RMS normalization | `02446be989844a3fb7e43dc9bd6a8e0a` |
| [mixed_oracle](mixed_oracle/source/README.md) | Routing and scalar scaling, with independent per-operation acceptance | `b152d434c8e14b01adc8c4aa40ad83f2` |

Build from a source directory:

```sh
cmake -S . -B build -DSTRATA_CORE_BACKEND=CPU
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

The package README defines numeric input contracts and optional native build
configuration. See the [recorded replay](../replay/README.md) to inspect how each
project was produced, including its actual source Diff and commands.
