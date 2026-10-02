---
type: review
status: draft
tags: [review, draft, prd, m1]
---

# Full M1 PRD: architecture review

> **Draft, not yet sent.** Architecture's review of the full M1 PRD, posted by Ramika on 2026-10-01 ([verbatim copy](../../product/prd-m1-full-2026-10-01.txt); `L123` below means line 123 of that file). The PRD is Ramika's. This page records source conflicts, runtime gaps, testability questions, and proposed architecture readings. A [fresh-context cross-check](../reviews/2026-10-01-full-prd-cross-check.md) has since verified the main readings; none is treated as settled without the relevant owner's confirmation. It replaces the [first-draft review](prd-review.md) for everything the full PRD covers.

## Summary

The full PRD and the CC design agree on the shape of M1: a fixed run plan, one runner for every capsule call, a two-tier gate after each step, deterministic pre-run eligibility (our freeze), time budgets because Codex reports no tokens, and RSI offline behind admission and human activation. Most of our earlier pushback is now settled.

The initial review identified three cross-section conflicts. The fresh-context cross-check confirms that the proposed readings are plausible but still need owners to confirm product decisions. Their impact is local: isolation and dependencies constrain 3.6/3.7/RSI; threshold semantics constrain 3.5/3.8. They do not block Screening's contract design.

1. **The isolation model is not buildable as written** (B1, B2). It asks for a separate unprivileged runner user and for a hidden fixture folder that the runner cannot read, while also requiring no root. On one user account, POSIX permissions alone cannot hide a folder from that same user, and the oracle runs RSI-mutated code next to the fixtures.
2. **The pass and fail rules have two sources** (A1, decision 2). The Brief's acceptance metrics (3.2.6) and the Hypothesis thresholds (3.5.4) can disagree, and nothing maps a result between the target and the falsification threshold.
3. **Who runs generated code** (A3). 4.9 says the Builder only builds and 3.7 runs the code, but 5.4.3 says the Builder runs it. 4.1.4 says one CC runner runs every capsule, but 4.9 gives the runner only 3.1 to 3.5 and 3.8 to 3.9, so nothing runs 3.7's capsule.

## Following the PRD as written

These readings are architecture proposals, not facts established by the PRD. They replace overlapping proposals below only after the relevant owners confirm them. The source cross-check records remaining gaps and affected scope.

| Point | Reading that follows the PRD | What we build |
|---|---|---|
| B1, B2: isolation | 4.4.9 describes fixture isolation without root for separate accounts; 5.2.1, 5.4.3 and 6.3 call for a restricted execution identity | a dedicated `jiuwen-runner` account plus an owner-only fixture directory is one possible mechanism. It requires an explicit resolution of 4.4.9's no-root wording, and a separate UID alone does not satisfy 2.9's network/system-effect limits. The trusted oracle must never run RSI-mutated code with fixture access. Platform support and the privilege mechanism remain unverified |
| A1: threshold sources | 3.2.6 passes Brief acceptance metrics toward 3.7; 3.5.1 states the claim's expected effect; 3.5.4 adds falsification thresholds | the blueprint must preserve the Brief acceptance target, claim expected effect, and falsification boundary as separate metric roles, with explicit units/comparators and deterministic relationships. A gate check ensures each mandatory Brief metric remains represented without weakening acceptance |
| A3: who runs 3.7 | 4.1.4's "every capsule call" governs. 4.9's split is about what a stage makes, not which runtime runs it | the CC runner runs every capsule, 3.6 and 3.7 included. 5.4.3's privilege drop applies to the tool host that runs generated code |
| A2, decision 1: dependencies | 3.6 never installs (3.6.1). 3.7 installs into its venv (3.7.1), and only "explicitly pre-installed packages" are available (3.6.1) | 3.7 runs `pip install --no-index --find-links <wheelhouse> -r requirements.txt` as `jiuwen-runner`. The installer fills the wheelhouse. The 3.6 gate runs the same command with `--dry-run`, so a package that is missing from the wheelhouse is the artifact's `FAIL`. A missing or broken wheelhouse in 3.7 is `ENVIRONMENT_BLOCKED`. This also answers C1 |
| Decision 2: target and threshold | 3.8.4 calls for deterministic comparison, while 3.8.5 lists four labels without defining their mapping | a code-based mapping is proposed, but it must retain the Brief acceptance target, expected claim effect and falsification boundary separately; define units, comparator, statistic/repeats, guards, incomplete evidence and anomalies. Scientific `INCONCLUSIVE` must route to Delivery after a passing gate; gate `INCONCLUSIVE` halts |
| Decision 3: gate result JSON | 1.6 gives the exact schema to architecture. 4.2.8 calls its JSON a "minimum" | the gate writes one durable record per decision that holds every 4.2.8 field. `normalized_verdict` and `routing_action` are computed from `gate_verdict`. This revisits [open issue](../open-issues.md) D8 ("never stored") |
| 4.8.2: hardcoded script | the requirement is a fixed, hand-wired sequence | the hand-written `run_plan` is that sequence, as data, pinned at freeze. The generic script only walks it |
| B4: `human_session` | 4.6.4 needs a terminal prompt for triage | on a halt, the CC launcher shows the triage prompt itself (abort, or restart after fixing the environment). It does not depend on the team backend. Needs a spike to confirm |
| B5: hot reload | reload without restarting the service | each run takes a snapshot of the config at start; a reload applies to the next run |

What remains: obtain owner confirmation for readings 40–44, including the three threshold roles and full execution boundary. Screening-specific questions are recorded in open issues 48–50.

## What the full PRD settles

| Earlier point | Now | Where |
|---|---|---|
| [Open issue](../open-issues.md) 14: no repository input | settled: 3.1.2 binds a project directory and validation data as separate resources | L456-477 |
| Open issue 16: Task and Coding Memory against raw evidence | settled: raw logs go to Data Foundation run bundles; memory keeps summaries only | L835-836, 4.5.1 |
| [First review](prd-review.md) 1: three verdicts or five | settled: five gate verdicts, plus a normalized four for the test spec | 4.2.8 |
| First review 3: whether contracts exist | settled: `capsule.json` is the contract and generates `make_capsule.md`, as in [make_capsule](../capsule/make-capsule.md) | L964 |
| First review 4: two nodes produce the Brief | settled: one bounded LLM pass in Phase 1 (3.2 and 4.7 describe the same compiler) | L1669 |
| First review 5: token budgets | settled: time budgets are authoritative; tokens are best effort | 4.1.4, 4.2.4, 4.3.3 |
| First review 7: the permission rail never runs on Codex | acknowledged: 4.1.4 says the adapter bypasses the native rails | L1003 |
| First review 9: operator API keys | settled on our side: the scholarly connectors run model-free, with an optional key ([integration](../system/integration.md)) | |
| First review 10: the judge emits the verdict | settled: Tier 2 returns findings, and fixed aggregation produces the verdict | 4.2.8 steps 4-5 |
| First review 11: screening called deterministic | settled: "fixed-rubric LLM evaluation", then deterministic arithmetic | 3.4, 3.4.5 |
| 3.8 and the gate shared `verifier_capsule` | settled: 3.8 is its own `scientific_evaluator_capsule`; the gate verifies 3.8 but never re-judges the science | L855, 4.2.6 |
| CC's runner, freeze and Standing | match: one runner as Swarmflow's backend (4.1.4), pre-run eligibility (4.1.3), one manually moved pointer per capsule (4.1.2) | |

**Still open from the first review:** 6 (`human_session` halts; see C1) and 8 (where code runs, now B1 and A3).

## The PRD owner's open decisions

### Decision 1: pre-provisioned dependencies, or install in 3.7

**We recommend pre-provisioned for Phase 1.** 3.6 may only name packages that are already installed in the benchmark environment, and Tier 1 checks this. Installing in 3.7 can come later, as a separate step.

Why:
- **The PRD says both.** 3.6.1 excludes "dynamic, autonomous installation of packages via pip during runtime", but 3.7.1 runs `pip install -r requirements.txt` (L766 against L817).
- **`requirements.txt` is model-written** from the Brief (L764). Installing it downloads packages a model chose, which 2.4 and 2.9 forbid unless they are declared and bounded. The model might also name a typo-squatted package.
- **An install from an index needs network and may run build code.** Source packages run `setup.py` or a build backend. Wheels run no code at install, but their `.pth` files run at every interpreter start. The benchmark itself must have no network.
- **[Open issue](../open-issues.md) 32** already lists `pip install` and network access as what keeps 3.7 from running unattended. Pre-provisioning removes both.

If installing in 3.7 is required, the safe form needs no network: `pip install --no-index --only-binary=:all: --require-hashes` from a local wheelhouse of allowlisted packages, into a throwaway venv. Anything that reaches an index is a separate provisioning step, with network for that step only and its own gate.

L766 sits in 3.6.1's blacklist, so one reading is "the Builder never installs; 3.7 may". If that is the intent, say so.

### Decision 2: results between the success target and the falsification threshold

**We recommend that 3.5 pre-registers the whole mapping, and that 3.8 applies it with code, not a model.** 3.8.4 already says "deterministic comparison" (L886).

For each dependent variable, the blueprint states: its direction (higher or lower is better), the success target, the falsification threshold, and any guard metric with a limit (for example "accuracy loss at most 2%"). Then:

| Observed | Scientific verdict |
|---|---|
| every primary metric meets its target, and every guard holds | `PASS` |
| any primary metric is past its falsification threshold, or any guard is broken | `FAIL` |
| between the target and the threshold on any primary metric, with no `FAIL` | `INCONCLUSIVE` |
| would be `PASS`, but 3.8.2 or 3.8.3 recorded a validity limitation (for example one seed, one batch size) | `CONDITIONALLY_ACCEPTABLE` |

Three things this needs from the PRD:
- **Metric semantics** ([open issue](../open-issues.md) 10): is a threshold absolute, a difference, or a relative change, and does `%` mean percentage points? Without this, "VRAM reduction is <10%" (L738) has two readings.
- **Repeats.** 3.7.2 sets no repeat count, and one run per arm cannot tell a 12% change from noise in latency or throughput. The blueprint should declare a repeat count and the statistic compared (for example the median of 5). This is not the power analysis that 3.5.4 excludes.
- **What `CONDITIONALLY_ACCEPTABLE` means.** 3.8.5 lists it but never defines it. If the definition above is not wanted, drop it from M1.

**Rename one of the two `INCONCLUSIVE`s and `FAIL`s.** The gate's `INCONCLUSIVE` halts the run. A scientific `INCONCLUSIVE` must go to Delivery, like a scientific `FAIL`. Two meanings under one word will cause routing bugs. Proposal: keep the scientific result in its own field (`classification`, as in our [evaluation_verdict](../types/evaluation-verdict.md)), and state in 3.8.5 that every scientific classification goes to Delivery when the gate passes.

### Decision 3: what should move to the Architecture Design

Section 1.6 gives exact schemas, IPC, process topology and storage layout to the Architecture Design (L191). These parts of the PRD specify them. We ask to keep the requirement and move the mechanism:

| PRD text | Keep in the PRD | Move to architecture |
|---|---|---|
| 4.2.8 "Minimum Gate Result Schema" (L1305-1329) | the five verdicts, their routing, and that every decision is durably recorded | the JSON shape. CC derives the verdict from the stored check results, so it never disagrees with them ([gate host](../capsule/gate-host.md)) |
| 4.2.1 Stage Evidence Bundle field list | what evidence the gate must see | the field names (`interface_hash` is our `decl_hash`) |
| 4.8.2 "hardcoded Swarmflow Python script", "manually wired" (L1744) | a fixed node sequence with user values injected | how it is built. CC uses one generic script that walks a recorded run plan, so the script and the plan cannot drift ([nodes](../system/nodes.md#the-one-generic-script)) |
| 4.6.3 "CC Runner as a managed subprocess" | time budgets, health checks, evidence packaging | process topology. 4.1.4 already says the runner is Swarmflow's backend |
| paths: `/workspace/poc/` (L763, L1773) against `./workspace/poc/` (L1883); `records/bundles/<run_id>/`; `~/.jiuwenswarm/oracle/fixtures/` | that these areas exist and what each may hold | the layout. The PRD already disagrees with itself on the POC path |
| 3.0.1 Unix socket, `0600`, session credential; 5.4.2 header token | local-only access, no TCP listener, an authenticated session | the mechanism |
| artifact file names and formats (`POC_Artifact_Bundle.zip`, `*.json`) | the artifacts and what each means | names and encodings. 4.2.2 has Tier 1 check filenames; CC checks the declared type instead |

## Contradictions inside the PRD

| # | Point | Evidence | We ask |
|---|---|---|---|
| A1 | **Two sources of pass and fail thresholds.** 3.2.6 sends the Brief's acceptance metrics to 3.7 "to define the pass/fail thresholds". 3.5.4 and 3.8.4 use the Hypothesis thresholds. A hypothesis can falsify at "<10%" while the user asked for "≥20%" | L561-563, L738, L886 | the Hypothesis thresholds govern 3.8, and must be at least as strict as the Brief's mandatory criteria. The 3.5 gate checks this mechanically |
| A2 | **pip install allowed and forbidden** | L766 against L817 | see decision 1 |
| A3 | **Who runs generated code, and what the Builder is.** 4.9 says the Builder constructs and 3.7 executes. 5.4.3 says "when the Builder executes AI-generated POC code in Stage 3.7". 4.1.4 says one CC runner executes every capsule call, but 4.9 gives the CC runner only stages 3.1 to 3.5 and 3.8 to 3.9 and calls the Builder a separate engine. So nothing runs 3.7's `benchmark_capsule.md` | L1765, L1974, L996-998, L810 | the Builder is the 3.6 capsule (`poc_capsule`) run by the CC runner, with code-writing tools. 3.7's capsule runs the code. Nothing else executes capsules |
| A4 | **The fixture folder is isolated without separate accounts, and with them.** 4.4.9 isolates the oracle folder by POSIX permissions "without requiring root sudo privileges for separate OS accounts". 5.4.3 and 3.7.1 run code as a separate `jiuwen-runner` or `nobody` user, which needs root to create and to switch to | L1556, L1974, L816 | see B1 and B2 |
| A5 | **Default version: latest, or the pointer (ambiguous).** 4.1.2 says new runs "default to binding against the latest optimized version", and also that "a manual command is required to shift the active default pointer". "Latest" may mean the latest human-activated version (4.4.9), but it also reads as the latest admitted one | L976, L980 | new runs use the version the pointer names, which a human moves. "Latest" is never implicit. This is CC's Standing |
| A6 | **Token limits at the 3.3 gate.** 3.3.6 has the gate verify "schema and token limits" | L632 | time and call counts only, as 4.2.4 says |
| A8 | **What the POC bundle holds.** 3.6.5 includes "the environment configuration"; 4.9.4 lists only three files. Tier 1's artifact check needs one list | L797, L1807 | one list, in one place |
| A7 | **Is 3.9 gated?** DoD item 10 gates every governed transition. 3.9 has no "Provides output to 4.2" line | L170, 3.9 | say whether the report gets a gate. CC proposes one for the report and fixed checks only for writing files ([open issue](../open-issues.md) 36) |

## What the M1 runtime cannot do as written

| # | Point | Evidence | We ask |
|---|---|---|---|
| B1 | **Dropping to an unprivileged user needs privilege.** `nobody` exists already, but switching to it, or to a new `jiuwen-runner`, needs root or a privileged helper. 4.4.9 rules out root. Dropping only to the `nobody` group (L1974) protects nothing: the uid still owns `~/.ssh`. 5.2.1 targets macOS and Linux, and the team develops on Windows through WSL | L816, L1974, L1877 | choose one, and name its platforms: (a) the installer runs once with `sudo` to create `jiuwen-runner` and a narrow helper; (b) a root-free Linux sandbox for the same uid (Landlock, or user and mount namespaces such as bubblewrap), noting that Ubuntu 23.10+ restricts unprivileged namespaces, WSL kernels vary, and macOS has neither; or (c) Phase 1 runs generated code as the user's own account and says honestly that this is weaker. Owner: Muk, with Xiaoyang |
| B2 | **Permissions cannot hide the fixture folder from the same user.** A process running as user U can read anything U's oracle daemon can read. ACLs do not help, because the owner can change them. So the 5.4.3 boot check ("the runner cannot read the hidden folder") fails unless the runner or the daemon is a different uid, or a B1 (b) sandbox hides the path. Worse, the oracle "runs the child capsule in a fresh subprocess". RSI-mutated code then runs as the daemon, which can read the fixtures. Blindness breaks even with separate uids unless the child also loses access | L1556-1557, L1976 | same choice as B1. The child runs with no access to the fixture folder; the oracle passes it one fixture's input at a time. Owner: Saurav |
| B3 | **The import ban is not a security boundary.** 3.6.2 and 4.2.5 ban `os`, `sys`, `subprocess` and others in all generated code. But `run_benchmark.py` imports the user's own baseline code, which will import `os`. `open()` needs no import, and `importlib`, `__import__`, `exec` and `ctypes` bypass a name list | L777, L1166-1172 | keep the scan as a hygiene check. Do not present it as the mitigation (4.1.4, L1000). The process boundary is the mitigation |
| B4 | **`human_session` halts.** The PRD routes every blocking verdict to `human_session` (4.2.7, 4.6.4, 5.3.3). On this runtime only the team backend has sessions, and the Codex adapter refuses replies ([B1 design](../b1-design.md), Stopping) | L1243, L1650 | M1 halts, keeps the evidence and shows the failure. A reply path is its own work item. Owner: Ramika, with Model Routing |
| B5 | **Hot-reloading `config.yaml`** (5.6). A reload during a run changes budgets, paths or model routes after the contract is set, against 1.4 | L2018 | each run takes a snapshot of the config at start, and records its hash. Reload applies to the next run |

## Not testable, or underspecified

| # | Point | Evidence | We ask |
|---|---|---|---|
| C1 | **FAIL against ENVIRONMENT_BLOCKED has no rule.** 4.2.9 case 7 removes "a required dependency" and expects `ENVIRONMENT_BLOCKED`. But if `requirements.txt` names a package that does not exist, the artifact is at fault | L1384-1388 | classify by who owns the failure. CC already gives every failure reason an owner (`runtime`, `input`, `capsule`), and the class follows from it ([seams](../seams.md#data-foundation)). Owner: Ramika |
| C2 | **Gate failure and scientific failure have grey cases.** A treatment that runs out of memory on the declared hardware: a defect, or a negative result? An "impossible" speedup flagged by 3.8.3: a gate `FAIL`, or a scientific `INCONCLUSIVE`? 4.2.6 says only "surface them for classification" | L879, L1210 | rule: if the declared protocol ran to completion and produced the declared measurements, any outcome is scientific. If it did not, it is infrastructure. A 3.8.3 anomaly makes the result `INCONCLUSIVE`, with the anomaly recorded |
| C3 | **No baseline or dataset supplied.** 3.1.5 checks only that the prompt is not empty and the folder is readable. 3.5.2 locks evaluation to a "static, standard, or user-supplied" dataset, and 2.4 forbids undeclared downloads. Nothing says where a "standard" dataset comes from, or what happens with no repository (3.7.2 also allows a foundation model as the baseline) | L501-511, L724, L261, L826 | 3.1.5 rejects a run that has neither a supplied dataset nor a declared, pre-installed standard one, or neither a project directory nor a named baseline model. Or the PRD defines a shorter run that stops after 3.4 |
| C4 | **3.5 names file lines with no tool to read code.** 3.5.3 says "implement the quantization logic in `model.py` at line 45", but only 3.6 has `CodeSearch` | L731, L773 | give 3.5 read-only `CodeSearch`, or say the mechanism names a function, not a line |
| C5 | **The 3.6 smoke test cannot check what it claims.** `py_compile run_benchmark.py` checks syntax only. It does not check `poc_patch.py`, and cannot check that output "conforms to the JSON schema" without running | L789, L1808 | compile both files, and add a dry run on a few rows of data inside the boundary, or drop the format claim |
| C6 | **3.4.6's deterministic filter needs a list.** "Unreleased proprietary models or closed datasets" is a judgment unless it checks a declared list | L688 | name the list and its owner, or move the filter into the rubric |
| C7 | **Screening ties.** The composite score is a sum of three 1 to 5 scores, so ties are likely with 3 ideas | L695 | a fixed tie-break order, for example feasibility, then compute alignment, then idea order |
| C8 | **Node states and halts.** Pending, Running, Evaluating, Completed or Failed has no state for "halted, waiting for a human". 4.6.4 forbids resuming without human review but does not say whether a human may resume a halted run | L1624, L1653 | add a halted state, and say whether resume from the halted node is in M1. CC can resume after `ENVIRONMENT_BLOCKED` ([open issue](../open-issues.md) 34) |
| C9 | **CLI exit codes.** Only 0 and "critical faults" are defined | L1922 | a scientific `FAIL` exits 0; a halt waiting for review has its own code |
| C10 | **The web token in the URL.** 5.2.2 opens the UI with a token in the query string, which the browser caches for later requests; 5.4.2 sends the session token in a header. Query-string tokens end up in browser history and logs | L1898, L1967 | the URL token is single-use and is exchanged for the header session token, so a leaked URL is worthless |

## Where the PRD meets CC's design: needs agreement

| # | Point | PRD | CC | Owner |
|---|---|---|---|---|
| D1 | **Who picks the model.** 4.1.1's permanent blacklist says the capsule layer never selects models. 4.3.2 Phase 2 has the router read the DAG's capsule and pick a model | L970, L1457 | the picker picks capsules only, which matches 4.1.1. Inside a capsule, the author's code calls a pinned router capsule, which decides ([reply](../model-routing/README.md)). We ask 4.1.1 to read "capsule selection never selects models; a capsule's model comes from the routing engine", so the reply and the PRD agree | Model Routing, with Muk |
| D2 | **An extra intent step before 3.2.** CC runs a deterministic `research.compile_intent` before the one LLM pass ([intent capsule](../m1/intent-capsule.md), [open issue](../open-issues.md) D5) | 3.2.1, 4.7.2 | no change to the single LLM pass or to the Brief. 1.6 asks us to raise this rather than decide it alone | Ramika |
| D3 | **Stage-named capsules.** The PRD names files (`search_capsule.md`). CC names capabilities (`research.search_ideas`), mapped in the [M1 pipeline](../m1/pipeline.md) | throughout | confirm the mapping ([open issue](../open-issues.md) 8) | Ramika |
| D4 | **Artifact names.** `Candidate_Set.json` is CC's `idea_set`; `POC_Artifact_Bundle.zip` is `poc_bundle` | 3.3.6, 3.6.5 | names are architecture's (1.6). Each type page names its PRD artifact, for example [idea_set](../types/idea-set.md) | none, for information |

## Section 6: implementation order

The order is right: backbone before stages, then intake, analysis, build, benchmark, delivery, shell, RSI. Stage 1's exit test (node A, gate, node B, both ways) is a good first milestone. Gaps:

- **Admission is on Stage 1's critical path.** "Define and admit a minimal capsule" means admission must exist before any run ([open issue](../open-issues.md) 6). Name it in Stage 1, with freeze.
- **The isolation decision belongs in Stage 0.** Stage 0 already sets up "the restricted execution identity" (L2100). B1 and B2 must be decided first, because the answer changes the installer, 3.7 and the RSI oracle.
- **Operators are missing.** `deepsearch` connectors and `CodeSearch` must be installed and wrapped before Stage 3. The `deepsearch` package's dependency pin conflicts with ours ([open issue](../open-issues.md) 33).
- **The failure-injection harness** (4.2.9) belongs in Stage 1, beside the gate it tests.
- **A reference research task.** The DoD needs one demo run end to end, and Stage 5 needs both a positive and a negative result. Choose a small baseline repository, a dataset and two hypotheses (one that should pass, one that should fail) before Stage 3, so every stage is built against the same inputs.
- **RSI fixtures start early.** 4.4.8 needs at least 20 loop and 20 final fixtures written by hand before RSI can start. That work can run from Stage 3, in parallel.

## Phase 1 scope

Candidates to move to Phase 2 or after M1, if the date is tight:
- installing packages in 3.7 (decision 1);
- a separate runner account and the oracle daemon (B1, B2), if option (a) is not accepted;
- macOS, for anything that depends on a B1 (b) sandbox;
- `CONDITIONALLY_ACCEPTABLE` (decision 2), unless it gets a definition;
- hot-reloading config (B5), TMUX management (5.5.1) and brand skinning (5.3.2), which no acceptance test needs.

## What this changes in the CC design

For our own follow-up, not for the PRD owner:
- **[intake](../types/intake.md)** must hold the project directory and validation data as typed resources (3.1.2). This closes open issue 14.
- **Open issue 16** closes: raw evidence goes to Data Foundation.
- **The black boxes for 3.4 to 3.9** now have their full PRD text. They still wait on decisions 1 and 2, B1, and open issue 10 ([black boxes](../system/blackboxes.md)).
- **3.8's capsule** is `scientific_evaluator_capsule`, separate from every gate capsule. This matches how [evaluation](../m1/evaluation.md) is designed, but that page still says the PRD puts 3.8 in `verifier_capsule.md`. Update it when the box is opened.
