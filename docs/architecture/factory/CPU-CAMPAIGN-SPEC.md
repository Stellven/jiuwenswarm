# Immutable CPU investigation campaigns

`scripts/factory_branch_mission.py` freezes a fresh, explicit CPU investigation.
It no longer extends the historical night mission deadline or discovers every
available package. Freezing, verifying and inspecting status do not call a
provider, launch inference or submit a job. `run` remains an explicit operator
action and uses the frozen policy.

Create a JSON specification with these exact fields (replace the identity,
absolute deadline, checkout SHA and absolute input paths before admission):

```json
{
  "schema": "factory.cpu-campaign/1",
  "campaign_id": "fresh-investigation-001",
  "deadline_utc": "2099-01-01T00:00:00+00:00",
  "objective": "Decide which numerical hypothesis merits a bounded followup, preserving unresolved evidence.",
  "source_commit": "0000000000000000000000000000000000000000",
  "packages": ["branch_workbench", "evidence", "inference_lab", "evidence_digest_lab", "numerical_investigation_lab"],
  "limits": {
    "max_turns": 4,
    "wall_clock_s": 900,
    "max_branches": 4,
    "branch_cpu_seconds": 40,
    "minimum_start_seconds": 60,
    "max_experiments": 0,
    "max_builds": 0,
    "gpu_seconds": 0
  },
  "evidence": {
    "engine": "/absolute/path/analysis.json",
    "extra": ["/absolute/path/diagnosis.json"]
  }
}
```

The date and zero SHA above are placeholders, not an admitted campaign. Obtain
`source_commit` from `git rev-parse HEAD` in the launcher checkout. Use a fresh
campaign ID and a new root; the historical mission ID and any existing root are
rejected. Identity uniqueness across unrelated roots remains the operator's
responsibility; there is no registry. The source commit must match the checkout.
The complete copied runtime hashes identify the actual snapshot, including
uncommitted work; a commit label alone does not claim a clean source tree.

```bash
ROOT/venv/bin/python scripts/factory_branch_mission.py \
  --root /absolute/fresh-campaign --campaign-spec /absolute/spec.json freeze
ROOT/venv/bin/python /absolute/fresh-campaign/launch.py verify
ROOT/venv/bin/python /absolute/fresh-campaign/launch.py status
# Only after operator admission of the frozen policy:
ROOT/venv/bin/python /absolute/fresh-campaign/launch.py run
```

The source launcher requires an explicit root. A copied launcher defaults only
to its own frozen directory. `--campaign-spec` is accepted only for `freeze`;
verify, run and status read the frozen policy. The historical `/1` format remains
verifiable and status reads only retained output. The current launcher refuses
to run `/1`. Historical copied launchers and directories are never rewritten.

The closed policy requires `branch_workbench` and `evidence`. Optional packages
are `memory_residency_lab`, `inference_lab`, `methodology_followup`,
`strata_prefill_chunk`, `strata_budget_workbench`, `cc_workflow_lab`,
`methodology_transfer_lab`, `evidence_digest_lab` and `numerical_investigation_lab`. Selection is a subset, not
an append operation. Each selected declaration is restricted to the launcher's
existing CPU capability allowlist, sealed and hashed. Digest provides `index`
and `project`; numerical investigation provides `replay_spec`, `compare_logits`
and `first_divergence`. Package availability makes no claim about live-agent cost improvement or an actual engine trace.

Limits are positive integers capped at six turns, 1500 controller wall seconds,
eight branches, 60 branch CPU reservation seconds and 600 minimum-start seconds.
Experiments, builds and GPU seconds must be exactly zero. Branch CPU seconds are
existing workbench allocation bookkeeping, not measured process CPU or an OS
CPU quota. The controller enforces its persisted turn/active-wall budget; the
launcher additionally bounds an invocation by the absolute deadline, retaining
30 seconds for cleanup. Native capsules remain trusted local code, not a process
sandbox. This slice does not connect branches to experiment cycles or admit GPU
work.

The engine input must be JSON. Inputs must be regular files, with at most eight
extra files and at most 2 MiB per file. Only explicitly selected evidence files
and the selected packages' retained examples/rounds are copied. Adjacent raw
files are no longer implicitly crawled: select useful raw evidence explicitly.
All copied inputs, runtime, restricted declarations, launcher, task and campaign
policy are pinned in the `/2` manifest. Verify rejects added or modified inputs,
policy/task disagreement, widened capability effects and expired policy. Run
requires sufficient remaining admission time before runtime/auth setup and
compares every original task field against the persisted task before resuming.
A changed objective, identity, deadline, packages, effects or budget requires a
new campaign, not an edited resume.

Hashes detect inconsistent or accidental changes; the manifest is not signed
against an adversarial operator who can rewrite every file and the database.
Credential material stays external. No live agent or GPU evidence is produced
by the campaign preparation tests.
