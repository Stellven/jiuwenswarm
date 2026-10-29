# AI4Research M1

**The first milestone release of AI4Research.**

Released October 29, 2026 · `ai4research-m1` · `AI4Research-Main`

## Latest main-branch integration

This M1 release has been refreshed with the main-branch integration at
`6bb00afa28cae3c5edc95e7c3217a1a21dbb9890` (PR #12), plus the release
documentation update. The `ai4research-m1` tag and downloadable manifest identify
the exact published snapshot.

- Integrated the iterative RSI capsule loop, bounded budgets, durable execution
  slots, retained evaluated children and resource-lifecycle handling.
- Added paired, batched parent/child benchmarks, correctness feedback and
  retained-child integration with the Capability Capsule benchmark runners.
- Included the updated capsule/Planner/Builder contracts, source-closure pins,
  trace handling and current main-branch runtime fixes.
- Included the compact public RSI benchmark evidence and its documented
  reproduction inputs. See the
  [RSI benchmark guide](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/docs/rsi-loop/BENCHMARKS.md).

The historical measurements below retain their original executed-source and
runtime scope. Publishing this integrated source does not constitute a new
benchmark campaign or automatically admit or activate retained RSI children.

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

M1 evaluation covers **Capability Capsules, independent verification, RSI and
model routing**, with additional exploratory planning and contract checks.
The recorded comparisons demonstrate benefits in preventing incorrect results,
improving tool execution time and reducing model token usage. Each result below
keeps its own baseline and experimental scope.

### Capability Capsules and independent verification

| Evaluation | Observed result | Comparison and scope |
| --- | --- | --- |
| Broken team tools, live agent | **0/8 incorrect answers delivered**, including one request for clarification | Both plain JiuwenSwarm and the same agent prompted to check the tool delivered 1/8 incorrect answers. One live run per task and arm. |
| Tool admission before use | **14/14 broken tools rejected before first use**, in all 10 repeats; 0/2 correct tools rejected | A scripted plain-skill baseline caught 0/14 before use. This is a deterministic admission experiment, not a live-model comparison. |
| Faulty research inputs | **6/8 faulty runs stopped with the correct reason**; 0/3 clean controls stopped | Plain JiuwenSwarm stopped 1/8 with the correct reason. Capsule checks were replayed on the stored runs; two faults remained undetected. |
| Independent code checking | **10/10 coding tasks passed hidden tests** | Plain, prompted-to-verify and self-written-test arms each passed 9/10. A separate benchmark-side checker enabled a corrective retry; this checker is not a shipped capsule. |

A larger broken-tool experiment recorded **3 incorrect answers in 36 live
baseline runs** (12 tasks × 3 repeats). The capsule admission check rejected
all 10 broken tools and retained both correct controls on the same 12-task set;
that capsule comparison ran the admitted tool without a model, so it is not
36 additional live capsule runs. In the independent-checker experiment, the
gain came from one task; the self-written-test arm also allowed a retry when
its own tests failed, while the plain and prompted-only arms had no retry.

### RSI: tool performance and change acceptance

RSI reduced execution time across three tested tools while passing their
recorded correctness checks:

| Tool | Execution-time reduction vs. frozen parent | Selected iteration | Recorded checks passed |
| --- | ---: | ---: | ---: |
| Calculate | **23.1%** | 3 | 19/19 |
| Table Normalize | **16.6%** | 4 | 19/19 |
| Parse Duration | **17.5%** | 1 | 14/14 |

These are repeated-batch tool measurements on the tested workloads, rather than
end-to-end application speedups. The iteration column identifies the selected
result, not the total number of attempts. Controller and supplementary check
groups are not pooled as independent trials.

In a separate **400-proposal, 20-seed scripted self-change experiment**, the
capsule gate accepted **37 changes with zero accepted regressions or policy
violations**. The visible-example-only baseline accepted all 400 proposals,
including **154 correctness/work regressions**, or **362 unsafe changes** when
protected-file edits and prohibited effects were included. This tests the gate
on a planted proposal set; acceptance and final scoring used the same hidden
inputs, so it does not establish held-out autonomous RSI safety.

A small live Calculate comparison produced **4/4 correct answers in each arm**:
mean completion time was **72.4 s** for JiuwenSwarm without capsules,
**63.4 s** with capsules and **60.6 s** with RSI-optimized capsules. The RSI arm
averaged 4.75 model calls versus 4.00 in the other arms. These measurements used
separate runs and different runtime setups; the time difference cannot be
attributed to RSI alone.

### Model routing: token efficiency

AI4Research Hybrid v8 used **18.19% fewer reported tokens** than fixed ChatGPT
inside AI4Research (**200,227 vs. 244,732**), while both arms produced
**24/24 correct worker answers**. Subscription worker calls fell by **25%**
(24 → 18). Token totals include selector and independent-verifier usage.

This comparison used eight public development fixtures, each repeated three
times. Cumulative component time increased from 271.16 s to 313.69 s; it does
not establish faster execution or monetary savings. See the
[routing evidence](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/benchmarks/reports/2026-10-27-matched-router/README.md).

### Exploratory planning and contract checks

The QA appendix also records preliminary, single-run component comparisons:

- **Contract-based planning:** 10/12 valid plans from capsule contracts versus
  8/12 from skill summaries; two contract-based plans remained invalid.
- **Requirement checking and honest stops:** 2/10 wrong or fabricated answers
  with the requirement gate versus 4/10 for the plain model, matching the
  prompted-to-verify arm's 2/10.
- **Output contracts:** 5/10 correct and compliant results with the validator,
  versus 6/10 for the plain model and 2/10 for the prompted-to-verify arm.
  This experiment did not improve on the plain baseline; contract validation
  still needs stronger semantic checking.

**Evidence and interpretation.** These results summarize the supplied
`AI4R_QA_Part_B.html` and `AI4R_QA_Part_B_Appendix.html` assessment dated
October 29, covering the October 26–28 campaigns. Part A assesses engineering
practice and is not a quantitative product-performance benchmark. Live-model,
replay, deterministic and simulated results are reported separately, with no
pooled pass rate. Small development sets, author-designed checks and faults,
and the documented runtime differences limit generalization. These findings
are not a new acceptance test of this release or a claim of universal
end-to-end superiority. Original QA reports, internal reports and generated
`benchmarks/output/` remain outside this release package.

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

## Requirements

- A Linux Docker engine and Docker Compose v2. On Windows, run the commands
  below in a WSL2 Linux terminal with Docker accessible there.
- Internet access for the first image build and access to your selected model
  provider. The quick start uses the existing ChatGPT sign-in flow.
- Available local port **5175**. The app container has a 4 GiB memory limit;
  image builds need additional host resources.

Docker builds install the required Python and Node dependencies. Host Python
and Node installations are not required for this quick start.

## Download, start and try it

Download an archive and `SHA256SUMS` from this release. Open a Linux/WSL terminal
in the download directory, then run:

```sh
# Verify the downloaded assets.
sha256sum --ignore-missing -c SHA256SUMS

# Extract the TAR.GZ archive.
tar -xzf AI4Research-M1.tar.gz
# If you downloaded the ZIP instead, use: unzip AI4Research-M1.zip
cd AI4Research-M1

# Enable local file inputs and subscription chat, then build and start the app.
export AI4R_LOCAL_WORKSPACE=1
export AI4R_LOCAL_CHAT=1
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml \
  up -d --build ai4r

# Find the browser bootstrap link.
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml \
  logs --tail 100 ai4r
```

The first build may take several minutes. Open the **complete private bootstrap
URL** printed in the logs at **http://127.0.0.1:5175**, including its
`#research_bootstrap=...` fragment. If startup is still in progress, follow the
logs with `logs -f --tail 100 ai4r` using the same Compose options.

In **Settings → Models**, choose **Sign in with ChatGPT** and complete the
displayed device-code flow. Once signed in, send a message in the chat composer.
To try document analysis, upload a text document or a PDF with selectable text,
select it as a reference document, and ask for its main claims and limitations.
Keep the bootstrap link private.

The quick start launches the web app. Governed research runs, automatic routing
with local models, RSI activation and benchmarking require their documented
operator bindings, model resources and runtime setup. See the
[operations guide](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/deploy/m1/OPERATIONS.md)
and [benchmark instructions](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/benchmarks/harbor_suite/README.md).

## Stop, resume and preserve your data

Run these commands from the extracted `AI4Research-M1` directory:

```sh
# Stop the app.
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml stop ai4r

# Resume the existing app without rebuilding.
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml start ai4r

# Inspect service status.
docker compose -p ai4r-local -f deploy/m1/compose.benchmark-runner.yaml ps
```

Account state and saved inputs persist in Docker named volumes. Reuse the same
`ai4r-local` project name for subsequent starts and source updates, and preserve
those volumes. To rebuild after a source update, rerun the quick-start exports
and `up -d --build ai4r` command. Avoid `down -v` when retaining your data.

## Known limitations and feedback

M1 remains an evolving milestone. The recorded evaluations cover several
components under different experimental conditions; missed input faults,
invalid plans, semantic output errors, verifier false blocks and broader
scientific validation remain open work. Platform and model compatibility depend
on the selected deployment;
build images for the target architecture. The source package does not certify
all benchmark variants or complete end-to-end scientific acceptance.

Report bugs or request improvements through
[GitHub Issues](https://github.com/Stellven/jiuwenswarm/issues). Include the M1
version, OS/architecture, Docker/Compose versions, reproduction steps and
relevant logs, with credentials and private bootstrap URLs removed.

AI4Research is distributed under the
[Apache License 2.0](https://github.com/Stellven/jiuwenswarm/blob/ai4research-m1/LICENSE),
with third-party notices included in the source package. See the
[packaging guide](https://github.com/Stellven/jiuwenswarm/blob/AI4Research-Main/releases/README.md)
for archive contents, checksums and reproduction. The `ai4research-m1` tag and
`release-manifest.json` identify the current published M1 source snapshot.
