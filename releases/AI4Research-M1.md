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

M1 remains an evolving milestone. The recorded benchmark is a routing-component
comparison; verifier false blocks and broader scientific validation remain
open work. Platform and model compatibility depend on the selected deployment;
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
for archive contents, checksums and reproduction. Documentation refreshes are
included in the downloadable packages; `release-manifest.json` identifies their
exact source commit, while the original M1 code tag remains `ai4research-m1`.
