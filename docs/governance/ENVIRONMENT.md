# AI4Research Environment and Tooling

Recorded: 2026-09-28 · Maintainer: Xiaoyang · Scope: AI4R-001 preparation and dependency installation

## Installed local environment

| Item | Observed state |
| --- | --- |
| Repository | `https://github.com/Stellven/jiuwenswarm.git` |
| Local checkout | `D:\research\ai_for_research\jiuwenswarm` |
| Personal branch / upstream | `ai4r_xiaoyang` / `origin/ai4r_xiaoyang` |
| Initial team baseline | `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483` |
| Platform | Windows AMD64; PowerShell |
| Application Python | **3.11.3**, using the existing local interpreter; repository declares `>=3.11,<3.14` |
| Application virtual environment | Repository `.venv`, recreated for Python 3.11 after the initial Python 3.13 compatibility failure |
| Backend dependencies | Installed from `uv.lock` with the `codex` extra and `test` group; `workswarm` 0.2.5b1, `openjiuwen` 0.1.18, `pytest` 9.0.3 |
| Application Codex packages | `openai-codex` and `openai-codex-cli-bin` **0.144.4**, as locked |
| IDE Codex binary | `codex-cli 0.155.0-alpha.16.3`; distinct from the application package |
| Setup uv | **0.12.19** in the isolated Spec Kit tooling environment; application dependencies separately contain uv 0.12.5 |
| Selected Node / npm | **v22.23.3 / 10.9.9**, portable installation under `%LOCALAPPDATA%\ai4r-tools\node-v22.23.3-win-x64` |
| Existing global runtimes | Python 3.13.1 and Node v20.15.0 / npm 10.8.1 unchanged |
| Frontend dependencies | Installed with `npm ci --no-audit --no-fund` in `jiuwenswarm/channels/web/frontend`; 737 packages installed |
| Subscription authentication / actual model execution | Not exercised; no credential files inspected or copied |

## Spec Kit installation

- Specify CLI: **1.0.12**.
- Exact source commit: `e77daa9021d20db26b878f7dfa5640fe5a42d04e` from `github/spec-kit`.
- Tool environment: `%LOCALAPPDATA%\ai4r-tools\spec-kit-v1.0.12`.
- Executable: `%LOCALAPPDATA%\ai4r-tools\spec-kit-v1.0.12\Scripts\specify.exe`.
- Installation used Python 3.13.1 `venv` and pip 24.3.1 in that isolated environment because uv was initially absent. This changes the installer, not the SOP's pinned Spec Kit version. uv was subsequently installed there for project setup. Global Python packages were not modified.
- Integration: Codex skills in `.agents/skills/`; script type: PowerShell.
- Extensions/presets: none explicitly installed; core `speckit` workflow only. No Git extension or automatic branch/commit hooks.
- Generated in a fresh temporary directory, inspected, then copied into previously absent `.specify/` and `.agents/` directories. No existing application file was overwritten by bootstrap.
- Exact package/source metadata and original generated-asset hashes are in [SPEC_KIT_SETUP.json](SPEC_KIT_SETUP.json).

Commands executed from the parent workspace, with each result checked:

```powershell
$specKitTools = Join-Path $env:LOCALAPPDATA 'ai4r-tools\spec-kit-v1.0.12'
python -m venv $specKitTools
& (Join-Path $specKitTools 'Scripts\python.exe') -m pip install 'git+https://github.com/github/spec-kit.git@e77daa9021d20db26b878f7dfa5640fe5a42d04e'
& (Join-Path $specKitTools 'Scripts\specify.exe') version
# For a new staging directory only:
& (Join-Path $specKitTools 'Scripts\specify.exe') init $specKitStaging --integration codex --script ps --non-interactive
```

`$specKitStaging` was a newly generated path in the operating-system temporary directory. Do not rerun initialization over an occupied directory. The executable is intentionally referenced by its full path; no global PATH change was made.

## Application dependency setup and runtime selection

The user explicitly requested installation of missing tools/dependencies. The initial locked backend installation used Python 3.13.1. Baseline checks exposed invalid escape sequences in the third-party `pysbd` dependency under the repository's warning policy. The environment was recreated with the existing Python 3.11.3 interpreter, within the project's declared range; no dependency source, warning filters, tests, or lockfiles were changed.

The initial Node 20.15.0 session-input test failed loading ESM. A diagnostic run enabling module detection then failed in Node's experimental mock timers. Installing Node 22.23.3 alongside the existing runtime resolved both issues for the selected tests. Its official Windows x64 archive was verified against the official SHA-256 list before extraction:

- Archive: `https://nodejs.org/dist/v22.23.3/node-v22.23.3-win-x64.zip`.
- Checksum source: `https://nodejs.org/dist/v22.23.3/SHASUMS256.txt`.
- SHA-256: `2b0ff57b049cda1bbcea2240eec20467018713c1efe1f7360c2681859b90ed71`.

Executed installation commands (backend from repository root; frontend from its directory):

```powershell
$specKitTools = Join-Path $env:LOCALAPPDATA 'ai4r-tools\spec-kit-v1.0.12'
& (Join-Path $specKitTools 'Scripts\python.exe') -m pip install 'uv==0.12.19'
& (Join-Path $specKitTools 'Scripts\uv.exe') sync --locked --python 3.11 --extra codex --group test
# Working directory: jiuwenswarm/channels/web/frontend
npm.cmd ci --no-audit --no-fund
```

The frontend install used the original npm 10.8.1; subsequent verification used the selected Node 22/npm 10.9.9. Reproduction after setup uses the following session-local paths. Run this in the process executing the commands; already running IDE agents do not inherit another terminal's updated environment.

```powershell
$specKitBin = Join-Path $env:LOCALAPPDATA 'ai4r-tools\spec-kit-v1.0.12\Scripts'
$nodeToolDir = Join-Path $env:LOCALAPPDATA 'ai4r-tools\node-v22.23.3-win-x64'
$env:Path = $specKitBin + [IO.Path]::PathSeparator + $nodeToolDir + [IO.Path]::PathSeparator + $env:Path
specify version
node --version
# From repository root:
.\.venv\Scripts\python.exe --version
```

Use the project `.venv\Scripts\python.exe` for backend tests and the selected portable Node for frontend scripts. An unqualified global `python`, `node`, or IDE-provided `codex` may select a different runtime. Actual baseline results and exact test commands are in [TEST_REPORT](../code/Missions/AI4R-001/TEST_REPORT.md).

## Task selection

From the application root, in the process that executes native commands:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'docs/code/Missions/AI4R-001'
$env:SPECIFY_FEATURE_NO_PERSIST = '1'
& ./.specify/scripts/powershell/check-prerequisites.ps1 -PathsOnly -Json
```

The local `.specify/feature.json` selects the same feature and is ignored by `.specify/.gitignore`. Native specification generation can write this pointer. Separate concurrent tasks require separate authorized checkouts and explicit selection. Path resolution is not prerequisite validation or a passing application test.

## Remaining preparation

Inspect the pinned OpenJiuwen Codex integration, select and validate the application Codex protocol, and run an explicit local-account validation scenario. Dependency installation and bounded baseline checks do not establish whole-project subscription compatibility. Complete an end-to-end SOP pilot before claiming normal team-wide adoption is complete. See [AI4R-001 preparation evidence](../code/Missions/AI4R-001/TEST_REPORT.md).
