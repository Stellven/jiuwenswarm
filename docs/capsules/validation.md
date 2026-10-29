# October 23 validation receipt

Tested combined source revision: `fd966f3` on the local
`capsules/m1-integration-check` branch, based on remote `ai4r_M1`
`bfc30ba291c762d09f464c3e6a6c25f011826a33`. A separate fresh Git worktree
was checked out from committed source before the final checks.

| Check | Actual result |
| --- | --- |
| Fresh Windows checkout: deployment, capsules, composition, planning/binding, gate, Library and existing sequential runner/artifact tests | **103 passed** |
| Same fresh source under Ubuntu 24.04 WSL, Python 3.12.3 | **102 passed, 1 skipped**; Linux Docker Compose plugin unavailable |
| Windows Compose-render check | Passed using the actual Compose plugin without a Docker daemon |
| Candidate preparation and declaration/check/profile validation | All five optional candidates passed; preparation left Library empty |
| Frozen original compiler/scientific and versioned PDF catalogs | 4 compiler, 7 scientific and 3 PDF entries reproduced from fresh committed bytes |
| Utility composition | Actual CSV normalization → decimal calculations → Markdown, through exact registered check assets; original file and low trust retained |
| Separate branches and deployment merge rehearsal | Clean automatic merge; each capsule adds disjoint package/docs/test paths above foundation |
| Focused Ruff undefined/unused-name checks, Git whitespace, local documentation links | Passed |

Model replies in Generalist unit tests are explicit fixtures. Expression
evaluation and deterministic utility processing actually execute locally;
these are not live research outcomes. Generalist failure/cancellation is not
retried, altered task identities/results/taint are rejected, and host-code
escape attempts are refused by the restricted interpreter.

The checked test files are `tests/deployment/test_operator.py`, the six
`test_capability_extensions.py`, `test_generalist_capsule.py`,
`test_table_normalize_capsule.py`, `test_calculate_capsule.py`,
`test_markdown_report_capsule.py`, `test_capsule_composition.py` files under
`tests/unit_tests/research`, existing `test_planning.py`, `test_binding.py`,
`test_gate.py`, `test_library.py`, and `test_sequential.py`,
`test_human_reports.py`, `test_archive_collection.py` under
`tests/unit_tests/research_sidecar`. Run them with `python -m pytest ... -q -o addopts=`
in an environment containing pytest, pytest-asyncio, httpx, jsonschema, psutil,
cryptography and ruamel.yaml. This was a focused suite, not the entire repository.

## Explicitly unrun

- Independent protected calibration with actual semantic model observations,
  human admission/activation of these candidates and a live app DAG.
- Live Docker builds/two-container campaign, SSH/Docker target execution,
  unattended scheduling activation, ARM64 builds and native Spark execution.
- Full arbitrary Python/OS Generalist execution; this release does not offer it.

Docker Desktop could not start on this workstation because its ingest socket
could not be renamed. No host reset or unrelated resource deletion was used.
Passing source/fixture checks does not establish deployment readiness or
scientific correctness. Code commits are ready for review/merge; runtime
qualification remains an explicit required operation before selection.
