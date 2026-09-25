# Development and Verification Environment

> Usage: copy to `docs/governance/ENVIRONMENT.md`. Update at adoption and when runtimes, dependencies, platforms, or services change. Task reports reference this document's version and explain deviations. Environment, working directory, actual command status, data/models/services, and limitations are required; explain N/A for irrelevant resources. Repository findings below come from static inspection. Candidate commands were not executed while preparing this SOP and do not establish successful installation or testing.

## 1. Static sources and environment to confirm (required)

- Static inspection: 2026-09-25, `jiuwenswarm_stellven` commit `52abe68db2dd167485f6bd79d6e36e193d608e64`.
- Sources: repository-root `pyproject.toml`, `Makefile`, `pytest.ini`, `tests/README.md`, `run_tests.sh`, and `jiuwenswarm/resources/.env.template`.
- Working directory: [Actual code repository root; do not confuse it with the enclosing research documentation directory].
- Operating system / architecture / shell: [Fill in].
- Actual Python / package manager / Git / Git LFS versions: [Commands, output, and date; currently unverified].
- Selected environment approach / maintainer / verification date: [Fill in].

Static findings: Python requires `>=3.11,<3.14`. `test` exists both as a pip extra and a dependency group; `lint` is a dependency group. The `dev` dependency group includes test and lint, while the pip `dev` extra contains desktop packaging dependencies. They are different. Do not infer that `pip install -e ".[lint]"` is supported or that `.[dev]` installs all testing and checking tools.

## 2. Candidate setup commands (confirm before adoption; all currently unverified)

Run from the repository root and record full output and exit codes. Select a consistent pip or uv approach and ensure tests use the interpreter into which dependencies were installed.

| Purpose / platform | Candidate command | Source and explanation | Actual status |
| --- | --- | --- | --- |
| Check interpreter | `python --version` | Compare with the range in `pyproject.toml` | [Not run] |
| Create pip environment | `python -m venv .venv` | Suggested isolation step; confirm interpreter compatibility first | [Not run] |
| Install test dependencies with pip on Windows | `.\.venv\Scripts\python.exe -m pip install -e ".[test]"` | Explicit-interpreter form of the installation command in `tests/README.md` | [Not run] |
| Install test dependencies with pip on Linux/macOS | `.venv/bin/python -m pip install -e ".[test]"` | Same source; does not assume the venv is activated | [Not run] |
| Set up with uv | `uv sync --locked` | `Makefile` uses `uv sync`; the additional lock consistency check is suggested. Confirm `uv.lock` exists first | [Not run] |
| Check uv interpreter | `uv run python --version` | `Makefile` uses `uv run python` | [Not run] |
| Inspect LFS working tree | `git lfs ls-files` | Checks object status; does not prove server retrieval is possible | [Recheck when adopting for a task] |

pip resolves declared version ranges and does not guarantee identical versions across machines; record resolved versions and a dependency snapshot. For uv, record the `uv.lock` version and any changes. `openjiuwen` is a dependency pinned to a GitCode commit; network access and build prerequisites need actual verification. Skipping required dependencies is not a successful installation.

## 3. Candidate verification commands (not executed or validated here)

| Check | Candidate command | Source and prerequisites |
| --- | --- | --- |
| Unit test directory | `python -m pytest tests/unit_tests/` | `tests/README.md`; requires test dependencies in the same environment |
| Selected file | `python -m pytest tests/unit_tests/test_config.py` | `tests/README.md`; select files based on the actual change |
| All tests | `python -m pytest tests/` | `tests/README.md`; establish external service, data, and execution cost requirements first |
| Ruff | `uv run python -m ruff check .` | `Makefile`; requires the lint dependency group |
| Pylint | `uv run python -m pylint jiuwenswarm` | `Makefile`; run separately to retain its exit code |
| Mypy | `uv run python -m mypy jiuwenswarm` | `Makefile`; run separately to retain its exit code |
| Codespell | `uv run python -m codespell` | `Makefile`; run separately to retain its exit code |

For pip, replace `python` with the venv's explicit interpreter. For uv, use `uv run python -m pytest ...` as appropriate. `pytest.ini` enables coverage reports, strict markers, and asynchronous mode, requiring the relevant plugins; execution creates report files. Parallel examples in `tests/README.md` require additional `pytest-xdist`; do not assume it is installed.

`Makefile` specifies `/bin/bash`, and the test script uses Bash. Do not assume these entry points work directly in Windows PowerShell. Use explicit Python commands or record the WSL/Bash environment and path differences. `make lint` uses `|| true` for pylint, mypy, and codespell; overall success does not establish that these checks passed. Retain each result separately.

## 4. Data, models, GPU, and services (required; explain N/A)

| Resource | Actual information to record | Configuration entry / variable names found statically |
| --- | --- | --- |
| Data and LFS artifacts | Versions/checksums, storage, permissions, integrity, and missing items | [Actual project entry]; a video LFS object returned server 404 during cloning, which may affect related tests |
| Main model | Provider, model version, protocol, sampling, endpoint identifier, and cost limit | `API_BASE`, `API_KEY`, `MODEL_NAME`, `MODEL_PROVIDER`, `ENDPOINT_PROFILE` |
| Embeddings / multimodal | Models and capabilities actually used, or N/A | `EMBED_MODEL`, `EMBED_API_BASE`, `EMBED_API_KEY`; inspect corresponding VIDEO/AUDIO/ASR/VISION variables when needed |
| GPU / local inference | Whether required, device and memory, driver/runtime versions, and allocation limits | [Actual configuration; static material does not establish a GPU requirement] |
| Browser / MCP and other services | Service versions, ports, health checks, and startup method | Actual settings such as `BROWSER_DRIVER`, `BROWSER_RUNTIME_MCP_HOST`, `BROWSER_RUNTIME_MCP_PORT` |
| Search / other external calls | Services, network conditions, quotas, and test substitute scope | Select task-relevant settings such as `BOCHA_API_KEY`, `PERPLEXITY_API_KEY` |

Record variable names and safe configuration identifiers only, never API keys, tokens, or restricted data contents. A variable in a template is not evidence that it is configured locally. Module owners must verify configuration loading paths and precedence.

## 5. Initial verification and limitations (required)

| Actual command / working directory | Environment identifier | Result / exit code | Impact of failures or missing resources | Evidence / owner |
| --- | --- | --- | --- | --- |
| [Fill in] | [Fill in] | [Not run / Passed / Failed / Blocked] | [Fill in] | [Fill in] |

- Still unverified: [Specific platform, installation, command, service, data, LFS, or other items].
- Existing baseline failures versus failures introduced by the task: [Comparison evidence or Under investigation].
- Conditions to unblock: [Action, owner, and deadline].

Record execution results with [TEST_REPORT_TEMPLATE.md](TEST_REPORT_TEMPLATE.md) and verification methods with [TESTING_TEMPLATE.md](TESTING_TEMPLATE.md).
