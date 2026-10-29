# AI4Research M1

**The first milestone release of AI4Research.**

Released October 29, 2026 · `ai4research-m1` · `AI4Research-Main`

## Integrated AI research workflow

M1 brings together the core AI4Research pipeline:

**Intent Compiler → Planner → Capability Capsules → Model Router → Verifier**

The Intent Compiler turns research intent into structured requirements; the
Planner organizes executable work; Capability Capsules provide research
capabilities; the Model Router selects suitable models; and the Verifier checks
outputs and execution evidence. **Recursive Self-Improvement (RSI)** supports
controlled capability improvement, evaluation and activation.

These components are integrated into the existing application, with a web
interface, persistent research state, artifact delivery and Docker deployment.
The local application runs at **http://127.0.0.1:5175**.

## Benchmark results

Benchmarking demonstrates an efficiency advantage over the evaluated fixed-model
baseline. In the matched routing benchmark, AI4Research Hybrid v8 used
**18.19% fewer reported tokens** than fixed ChatGPT inside AI4Research
(200,227 vs. 244,732), while both arms produced **24/24 correct worker answers**.
It also reduced subscription worker calls by **25%**.

These results cover eight public development fixtures, each repeated three
times, and include router and verifier token usage. They establish an observed
component-level efficiency improvement under the recorded conditions; they do
not establish faster execution or universal end-to-end superiority.
See the [benchmark evidence](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/benchmarks/reports/2026-10-27-matched-router/README.md).

## An M1 foundation for future development

This is an **M1 release**. Broader research capabilities, stronger planning and
verification, improved routing, more mature RSI, and further performance and
usability optimization remain areas for future development. Broader benchmark
coverage and end-to-end scientific validation are also continuing work.

## Release package

Download `AI4Research-M1.zip` or `AI4Research-M1.tar.gz`, with `SHA256SUMS` and
`release-manifest.json`. Both source packages include these release notes and
the Docker build/deployment definitions. Internal benchmark reports and
`benchmarks/output/` are excluded. Prebuilt images and credentials are not
included.

Follow the [deployment guide](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/deploy/m1/OPERATIONS.md)
to build and run, or the [packaging guide](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/releases/README.md)
for package verification and reproduction.
