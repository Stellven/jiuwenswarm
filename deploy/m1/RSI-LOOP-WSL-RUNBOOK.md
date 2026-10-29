# RSI capsule improvement loop: WSL deploy and first real run

Audience: a Codex CLI agent on the user's Windows machine (PowerShell plus
WSL `Ubuntu-24.04`). It has the live WSL runtime but has not read the chat that
produced this branch. Follow the sections in order. Every **CHECK** must pass
before you continue. Every **STOP** means: record what you saw, change nothing
else, and report to the user.

Code on branch `rsi-loop` is the authority. Each section names the file that
defines the behaviour it describes. Where this runbook and the code disagree,
the code wins: stop and report the difference.

Branch content: merge commit `31399b8` (six workstreams W1 to W5 plus the
interface record `docs/rsi-loop/INTERFACES.md`). The only change on top of it
is the commit that adds this file. None of it has been deployed.

---

## 0. Conventions used below

Run every WSL block as Root. From PowerShell:

```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash -l
```

Set these once per root shell. Choose a `TAG` that does not already exist:
if `/opt/ai4r-capsule-admin-$TAG` exists, increase `rN`.

```bash
set -euo pipefail
umask 022                 # pinned files must end up with exact modes; chmod explicitly anyway
export TAG=20261027-r1
export SRC='/mnt/d/Codex Development Runs/jiuwenswarm-rsi-loop'      # Windows worktree of rsi-loop (section 1.1)
export L='/mnt/d/Codex Development Runs/rsi-ui-live-20261026'         # deployment workspace (handoff "L")
export RCPT="$L/loop-$TAG"                                            # receipts written by this runbook
export ADMIN=/opt/ai4r-capsule-admin-$TAG                             # new Root prefix (never reused)
export RT=$ADMIN/runtime                                              # run.source_root == prepare.source_root
export ADM=$ADMIN/admin                                               # broker/launcher/publisher/projection/slot/module
export BUILD=$ADMIN/build                                             # Root-only build scripts (not pinned)
export SLOTS=/var/lib/ai4r-cc-rsi-capsule-slots                       # durable ledgers (state_root parent)
export NS=/var/lib/ai4r-rsi-capsules/loop-$TAG
export CTL=/var/lib/ai4r-rsi-capsule-control/loop-$TAG
export EV=/var/lib/ai4r-rsi-capsule-evidence/loop-$TAG
export CGJOBS=/sys/fs/cgroup/ai4r-rsi-host/jobs
export ROOTCFG=/etc/ai4r/cc-rsi-capsule-root-loop-$TAG.json
export GW=/etc/ai4r/cc-rsi-capsule-gateway.json
export JOURNALS=/var/lib/ai4r-cc-rsi-capsules
export SOCK=/run/ai4r-cc-rsi-development/capsule.sock
export V18_IMAGE=sha256:00026931a8e236d255efca8d2e90ea49ae04989539fca4d418d318a98fa93ab2
export PY=/usr/bin/python3.12          # resolved interpreter; the broker pins a regular file, not a symlink
export CALC_SLOT=calc-loop-${TAG%-r*}  # e.g. calc-loop-20261027  -> run ids calc-loop-20261027-r1, -r2, ...
export NORM_SLOT=norm-loop-${TAG%-r*}
mkdir -p "$RCPT"
```

Two Docker daemons exist. Never confuse them:

* **App Docker** (`docker` on the default socket `/var/run/docker.sock`):
  runs the 5175 app container.
* **RSI Docker** (`/run/ai4r-rsi-docker/docker.sock`): runs the V18 step,
  worker and job containers. Reach it only through the existing namespace
  helper, as the launcher does (`deploy/m1/rsi_capsule_launcher.py:75-78`).
  Do not change global Docker binaries or symlinks.

```bash
# RESTORE = the restore helper already pinned by the last strict launcher configuration (section 3.4).
rsidocker() { /usr/bin/python3 -B "$RESTORE" client /usr/bin/docker --host unix:///run/ai4r-rsi-docker/docker.sock "$@"; }
```

Receipts: after each section, write the facts you observed (ids, hashes,
counts, exit codes) to `"$RCPT/<section>.json"`. Never write credentials,
raw container environments or browser bootstrap URLs into receipts.

---

## 1. Preconditions and safety

### 1.1 Get the exact branch, without disturbing the shared checkout

The original repository `D:\Codex Development Runs\jiuwenswarm` holds staged,
unstaged and untracked work that is shared among agents. Do not reset, clean,
stash or check out a different branch there. Use a separate worktree:

```powershell
cd 'D:\Codex Development Runs\jiuwenswarm'
git fetch <remote-or-bundle-the-user-names> rsi-loop
git worktree add 'D:\Codex Development Runs\jiuwenswarm-rsi-loop' rsi-loop
cd 'D:\Codex Development Runs\jiuwenswarm-rsi-loop'
git merge-base --is-ancestor 31399b8 HEAD; if ($LASTEXITCODE -ne 0) { throw 'STOP: 31399b8 is not in HEAD' }
git log --oneline -3          # HEAD = the runbook commit, its parent = 31399b8
git status --short            # must be empty
```

**CHECK:** `git diff --stat 31399b8 HEAD` lists only
`deploy/m1/RSI-LOOP-WSL-RUNBOOK.md`.

Blobs in this repository are committed with mixed line endings (many `.py`
files contain CRLF). Every deployed byte must be the **blob** byte. Export with
`git -c core.autocrlf=false archive` (section 3.1), never by copying the
Windows working tree.

### 1.2 Things you must never do

* Never reset, truncate, rewrite or delete a journal, ledger, lease, Core
  database, publication history, claim or Root receipt. That covers
  `/var/lib/ai4r-cc-rsi-capsules/*`, `/var/lib/ai4r-rsi-codex/**`, relay and
  benchmark ledgers, `.capsule-history`, `.capsule-claims` and
  `*/claims/*`. Durable state is append-only by design
  (`jiuwenswarm/server/rsi/cc_rsi_capsule.py:261-314`).
* Never replay Calculate `fcc60d-calculate-ui-r1` (failed: incomplete
  package) or `fcc60d-calculate-ui-r2` (failed: 0700 work parent plus pipe
  frames). Both are consumed. Their claims, failures and Failed publication
  rows must stay byte-identical. Do not re-prepare their run ids or reuse their
  directories.
* Never restart, re-signal or reuse broker PID `103815` (start ticks
  `5517235`), or any older broker. Its configuration, owner record, claims and
  journals stay where they are.
* Never copy `auth.json`, tokens, account or session directories, the gateway
  key or the relay session file into WSL, containers, receipts or the
  repository. The host-Codex login stays on Windows. The relay reaches it
  through the existing Windows binary, not through copied credentials.
* Never `docker rm`, `docker system prune`, `compose down` or delete a
  volume. Stopped app containers (`ba1920af`, `5371dfe1`, `fe93a4d1`) and
  stopped RSI containers stay for rollback and audit.
* Never edit a sha256 by hand. Every pin below is re-derived from the bytes
  on disk by the code that checks it, or by the generator scripts given here.
* Never touch frozen V18 `/opt/ai4r-rsi-frozen-v18-03ed3199`, the captured
  runtime `/opt/ai4r-capsule-runtime-fcc60d-20261026-r1`, earlier admin
  prefixes (`/opt/ai4r-capsule-admin-20261026-r1`,
  `/opt/ai4r-capsule-launch-admin-20261026-r3`,
  `/opt/ai4r-capsule-runtime-admin-20261026-r4`, `/opt/ai4r-capsule-prepare-*`)
  or historical captures. Read them; never write to them.
* No model request, protected job or Run click during setup. The only model
  work this runbook causes is the human clicking **Run** in section 7.
  Preparation, the compose doctor and preflights are model-free
  (`deploy/m1/rsi_capsule_slot.py:300-302`, `:324-325`).
* Builder stays unavailable. Results stay `UNQUALIFIED` and
  `SECURITY_DEFERRED`. No signing, admission or activation.

### 1.3 Observe the live machine (read-only)

```bash
cat /proc/sys/kernel/random/boot_id                    # compare with the last receipts in L
ps -eo pid,lstart,args | grep -E 'rsi_capsule_broker|rsi_host_codex|rsi_host.py hold' | grep -v grep || true
ls -l "$SOCK" 2>/dev/null; stat -c '%i %U:%G %a' "$SOCK" 2>/dev/null || true
ss -xlp | grep -F "$SOCK" || echo 'no listener on capsule.sock'
docker ps -a --format '{{.ID}} {{.Image}} {{.Status}} {{.Names}} {{.Ports}}' | head -20   # App Docker
docker inspect ba1920af53b5f30f87e38af2822cf2124219b606eb39d0d0cf7cb0e0d134280c --format '{{.State.Running}} {{.Image}}'
```

**CHECK:**

* The boot id matches the latest receipt in L. If WSL was restarted, `/run`
  was emptied: the RSI Docker daemon, `/run/ai4r-rsi-host-codex` and
  `/run/ai4r-cc-rsi-development` need the reviewed boot-restoration path
  (`deploy/m1/rsi_host_boot_restore.py` plan/apply and
  `rsi_host_codex.py restore-runtime`). That path is outside this runbook:
  **STOP**.
* PID 103815 is absent, or present with different start ticks. If it is
  present with start ticks 5517235: **STOP**. It was supposed to be stopped.
* No process listens on `capsule.sock`. The file may still exist: the stopped
  broker left it, and section 4.5 handles it.
* App container `ba1920af` is running, image
  `sha256:de43e2de4c6a4d003883425a73bef8ed6f16e25efe31a844eb2eaa286d694cae`,
  published on `127.0.0.1:5175`.

Record the Core totals before anything else. The handoff says they are 2 model
calls, 0 tool calls and 2 attempts, all from historical Screening:

```bash
CORE=/var/lib/ai4r-rsi-codex/development/host-codex-v6-screening-ui-1/core
$PY -c "import sqlite3,sys;d=sqlite3.connect('file:'+sys.argv[1]+'/state/research.sqlite3?mode=ro',uri=True);print({t:d.execute('select count(*) from '+t).fetchone()[0] for t in ('model_calls','tool_calls','attempts')})" "$CORE"
sha256sum /var/lib/ai4r-rsi-codex/ui-development/host-codex-v6-screening-ui-1/publication/publication.json
```

**CHECK:** the publication sha is
`4867784cf5d9bb404f9416efd64143e6b52e0aad2994cd605588650ecbf55678`. That is
the R2 failure publication, which includes Screening plus R1 and R2. If it
differs, find the explanation in L before going on. Save the bytes of the
Screening, R1 and R2 run rows and their nodes (section 6.4 compares them).

### 1.4 The WSL keeper and the host-Codex relay

**Keeper.** `deploy/m1/rsi_host.py hold --seconds N` is a finite foreground
lease, with N at most 7200 (`rsi_host.py:296-321`). systemd services alone do
not keep WSL alive. The last keeper (PID 83626) and relay (PID 83923) were
finite and have expired. Start a new keeper in its own PowerShell window. Use
the **same argv as the last recorded keeper**: read it from
`$L/capsule-keeper-new-active-r1.json` or from the newest keeper receipt in L.
The usual shape is:

```powershell
wsl.exe -d Ubuntu-24.04 -u root -- /usr/bin/python3 -B <installed>/deploy/m1/rsi_host.py hold --seconds 7200
```

**CHECK:** the first line is `FOREGROUND_HOST_HOLD_STARTED` with the current
incarnation key. A whole loop run without the paired benchmark can take up
to about 67 minutes; with the benchmark (merge wave, section 7.3) its hard
deadline is about 3.2 h and a typical run is 1–2 h, longer than one keeper
(N ≤ 7200 s). Before each Run click, make sure the keeper has at least 90
minutes left and plan the overlapping successor keeper for the run's whole
deadline (`wall_s` of the prepared revision). Start the next keeper about 10
minutes before the current one ends, so that the two overlap. Never kill a
keeper you did not start.

**Relay.** `deploy/m1/rsi_host_codex.py` provides
`serve | check | restore-runtime | prepare | smoke`. This branch does not
change it. Use only `serve` and `check`:

* `prepare` refuses to run when the runtime already exists
  (`rsi_host_codex.py:91`).
* `smoke` is a once-only, already-consumed operator action
  (`rsi_host_codex.py:260-267`).

`serve` takes the runtime lock, re-validates the Root profile, catalog,
qualification and session custody, and serves `/run/ai4r-rsi-host-codex/model.sock`
(Root:G13000, socket mode 0660) without opening any credential
(`rsi_host_codex.py:210-246`). Start it with exactly the argv, working
directory and `PYTHONPATH` of the last relay (PID 83923). Read them from
`$L/capsule-relay-resume-readiness-r1.json`. Run it in its own Root shell or
as a finite owned process (`timeout --signal=INT <seconds> ...`) that covers
the run window. Then check it:

```bash
# Use the same installed rsi_host_codex.py path and PYTHONPATH as the recorded relay.
$PY -B <installed>/deploy/m1/rsi_host_codex.py check
```

**CHECK:** the output is `{"status": "TRANSPORT_AVAILABLE", "active": false, "unresolved": false, "generation_sent": false, ...}`.

* `unresolved: true` means an earlier request has an unknown outcome. Do not
  clear it: **STOP**.
* A stale socket from an ended relay may block `serve`. The earlier
  procedure quarantined the exact stale socket inode without overwriting it
  (handoff, 22:32 UTC checkpoint). Do the same: record the inode, prove no
  process holds it, rename it to `.quarantine-model.sock-<inode>`, and do not
  delete it.

The relay must stay up through slot preparation (the compose doctor calls
`before_model()`, which checks native readiness:
`jiuwenswarm/research_rsi/capsule_doctor.py:737-738`), every preflight (a
read-only relay status as UID/GID 12001 with group 13000:
`deploy/m1/rsi_capsule_run.py:199-243`) and the whole run.

---

## 2. Portable verification on WSL, before touching Root

This runs only code from `$SRC`, in a throwaway venv. Nothing under `/opt`,
`/etc` or `/var/lib` is touched.

### 2.1 Test environment

The suites need `pytest pytest-asyncio jsonschema cryptography pyyaml
typing_extensions`. That set was verified on this branch. The worker-traversal
probes re-execute `sys.executable` as UID 12003
(`capsule_doctor.py:601-607`), so the venv must be **world-traversable**. A
venv under `/root` or another 0700 directory fails with
`PermissionError ... venv/bin/python` in
`test_package_preflight_derives_closure_and_worker_traversal_before_any_claim`,
`test_simulated_worker_traversal_and_tree_listing_as_uid_12003` and
`test_precreated_private_parents_are_corrected_inside_evidence_root_only`.

```bash
getent passwd 12003 || { echo 'STOP: worker identity 12003 missing'; exit 1; }
python3.12 -m venv /var/tmp/rsi-loop-venv-$TAG && chmod 0755 /var/tmp/rsi-loop-venv-$TAG
/var/tmp/rsi-loop-venv-$TAG/bin/pip install pytest pytest-asyncio jsonschema cryptography pyyaml typing_extensions
mkdir -p /var/tmp/rsi-loop-src-$TAG && chmod 0755 /var/tmp/rsi-loop-src-$TAG
git -C "$SRC" -c core.autocrlf=false archive --format=tar HEAD | tar -x -C /var/tmp/rsi-loop-src-$TAG
```

Run the tests from the Linux copy `/var/tmp/rsi-loop-src-$TAG`, not from
`/mnt/d`. DrvFs may not present the Linux owners and modes that the custody
and traversal checks assert, and it is slow.

### 2.2 Focused suites (the command from `docs/rsi-loop/INTERFACES.md`)

```bash
cd /var/tmp/rsi-loop-src-$TAG
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1
V=/var/tmp/rsi-loop-venv-$TAG/bin/python
$V -m pytest -o addopts= -p no:cacheprovider -p asyncio --confcutdir=tests/unit_tests/scripts \
  tests/unit_tests/scripts/test_rsi_capsule_launcher.py tests/unit_tests/scripts/test_cc_rsi_capsule.py \
  tests/unit_tests/scripts/test_rsi_capsule_publication.py tests/unit_tests/scripts/test_cc_rsi_projection.py -q
$V -m pytest -o addopts= -p no:cacheprovider -p asyncio --confcutdir=tests/unit_tests/research_rsi \
  $(ls tests/unit_tests/research_rsi/test_capsule_*.py | grep -v e2e_local) -q
```

**CHECK:** 91 passed for the scripts suites, 100 passed for the
`research_rsi` capsule suites (the appendix has per-file counts). Zero
failures and zero errors. A failure you cannot trace to the environment (for
example, a missing package): **STOP**.

### 2.3 Gate: the model-free end-to-end loop

`tests/unit_tests/research_rsi/test_capsule_loop_e2e_local.py` drives the real
`rsi_capsule_run` evaluator and controller over real OS pipes, the real
`capsule_session.run_session` loop, the real `LocalDispatcher` running the
frozen bootstrap and worker bodies over all 19 cases per capsule, three trials
each, and the real objective. Only the model is scripted (`FakeBackend`). It
needs Root (the child switches to UID/GID 12003) or UID 12003. It takes about
5 minutes.

```bash
$V -m pytest -o addopts= -p no:cacheprovider -p asyncio --confcutdir=tests/unit_tests/research_rsi \
  tests/unit_tests/research_rsi/test_capsule_loop_e2e_local.py -q -rs
```

**CHECK:** `3 passed` (about 12 minutes on a 2-CPU box: the third test runs
the real paired batched benchmark twice, 82 jobs each). A `skip` that names the
12003 identity means the gate did not run: **STOP**. What the gate proves:

* Calculate: the broken candidate is scored and not kept. The `max()` tie fix
  is kept with candidate correctness 1.0 > parent, `newly_passed` equal to the
  parent's failing ids (held-out included), and `best.iteration == 2`.
* Table Normalize: improvement can only come from latency strictly above the
  calibrated noise floor.
* Codex's round-2 Calculate candidate (sha `0fb940f0…`) through the real
  `LocalDispatcher.benchmark`: Root serves the parent A/A baseline (ratio
  near 1, objective not met) and the parent→candidate benchmark (3 AB/BA
  pairs, batches 100/4, explicit e2e gates: gain >= 5%, CI upper <= 0.95,
  no workload > 10% slower; production keeps the frozen 10%/0.90/5%);
  the candidate keeps every parent output byte, `median_ratio < 1`,
  `objective_met`, `latency_method == paired_batched_benchmark`, kept; every
  benchmark job is a `capsule-*` start claim inside the grant budget. The
  calculate test also proves the real `packet.py` dependency excerpt reaches
  the prompts.

### 2.4 Optional: the frontend that W5 changed

Use the same Node toolchain (Windows or WSL) that built the previous
`frontend-dist-catalog-r1` in L. Shown here for WSL:

```bash
cd /var/tmp/rsi-loop-src-$TAG/jiuwenswarm/channels/web/frontend
npm ci --no-audit --no-fund && npm run test:cc-rsi && ./node_modules/.bin/tsc --noEmit -p .
```

**CHECK:** 17 tests pass and `tsc` exits 0.

---

## 3. Build and install the new runtime package (Root)

### 3.1 Stage a closure-complete package

The runner refuses a partial overlay. `load_sources` requires the four
package roots, the exact `jiuwenswarm/` inventory equal to the pins, and the
derived import/resource closure of `jiuwenswarm.research_rsi` plus
`jiuwenswarm.research` plus the frozen composition
(`deploy/m1/rsi_capsule_run.py:111-157`, `capsule_doctor.py:473-496`). The
prepare step runs `-m deploy.m1.rsi_capsule_prepare` from the same root
(`rsi_capsule_slot.py:241-249`). The doctor and worker containers mount only
`source_root`, so the frozen composition must live **inside** it
(`rsi_capsule_slot.py:252-260`, `rsi_capsule_launcher.py:194-196`; see known
issue K2).

```bash
test ! -e "$ADMIN" || { echo "STOP: $ADMIN exists; bump TAG"; exit 1; }
install -d -o root -g root -m 0755 "$ADMIN" "$RT" "$ADM"; install -d -o root -g root -m 0700 "$BUILD"
git -C "$SRC" -c core.autocrlf=false archive --format=tar HEAD jiuwenswarm \
    deploy/m1/rsi_capsule_prepare.py deploy/m1/rsi_development_run.py | tar -x --no-same-owner -C "$RT"
git -C "$SRC" -c core.autocrlf=false show HEAD:deploy/m1/rsi_capsule_run.py > "$RT/runner.py"
for f in rsi_capsule_broker.py rsi_capsule_launcher.py rsi_capsule_slot.py rsi_capsule_publication.py; do
  git -C "$SRC" -c core.autocrlf=false show HEAD:deploy/m1/$f > "$ADM/$f"; done
for f in cc_rsi_capsule.py cc_rsi_projection.py; do
  git -C "$SRC" -c core.autocrlf=false show HEAD:jiuwenswarm/server/rsi/$f > "$ADM/$f"; done
chown -R root:root "$ADMIN"
find "$RT" "$ADM" -type d -exec chmod 0755 {} +
find "$RT" "$ADM" -type f -exec chmod 0444 {} +
```

**CHECK (all of these, saved to `$RCPT/3-package.json`):**

```bash
find "$RT" \( -name __pycache__ -o -name '*.pyc' -o -type l \) | head          # must print nothing
sha256sum "$RT/deploy/m1/rsi_development_run.py"   # 5ba11903f494c06cffaa56f40efae2b5cadee73711a3bc7dd2b9f7e04a6f8016 (runner COMPOSITION_SHA256)
cmp "$RT/runner.py" <(git -C "$SRC" -c core.autocrlf=false show HEAD:deploy/m1/rsi_capsule_run.py) && echo runner-is-blob
find "$RT/jiuwenswarm" -type f | wc -l                                          # 3235 on this branch
sha256sum "$ADM"/*                                                               # record; these are re-derived below, never typed
```

On this branch the blob hashes are:

| file | sha256 |
|------|--------|
| `jiuwenswarm/server/rsi/cc_rsi_capsule.py` | `44b459e3cf72cbcadc6b656f2783b14ed018a74c68f4c229f6b94385aae9c904` |
| `jiuwenswarm/server/rsi/cc_rsi_projection.py` | `3f6b0aa28eb1c89315beb61397a1edcf6dfbc2255a877126c10bb077f7fb98cc` |
| `deploy/m1/rsi_capsule_broker.py` | `01438d0a6679a7ed9df5df0615542d4a78f8a679fa549b9dd4325ea716e8f5c9` |
| `deploy/m1/rsi_capsule_launcher.py` | `e66ec7cfe9dcc7da9c52c007c318254fcc41f41f1172c5ede2fe0a2cae3c71bc` |
| `deploy/m1/rsi_capsule_slot.py` | `8788190c7aafe367bcafd73d2539af42400734d7186b78d4c2879e357aeb7ce7` |
| `deploy/m1/rsi_capsule_publication.py` | `bf01fee5b079721400173567db5b59b6cc163c2a4ce9ddd66d366dc8de501ceb` |
| `deploy/m1/rsi_capsule_run.py` (runner) | `f75be28f0d355b9ea4363023263234d6a3b857b8d4308119cae86f01f2f97e22` |
| `deploy/m1/rsi_capsule_prepare.py` | `f237d784ed4574f9669e5b14d4e5bcea966d064b77c48d99bec65d6b925d6b28` |
| `jiuwenswarm/research_rsi/capsule_doctor.py` | `9e6cb1e06b0026e31d1cd3580541bda7e27ba67bbe1e27321cb1cd6d81d165fc` |

A mismatch means the export converted line endings: **STOP**.

### 3.2 Prove source closure on the staged bytes, and time it

This uses the doctor the launcher will pin, loaded stand-alone and stdlib-only,
the same way the launcher loads it (`rsi_capsule_launcher.py:84-99`):

```bash
cat > "$BUILD/closure_probe.py" <<'EOF'
import hashlib, importlib.util, json, sys, time
from pathlib import Path
root = Path(sys.argv[1])
pins = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / 'jiuwenswarm').rglob('*')) if p.is_file()}
spec = importlib.util.spec_from_file_location('d', root / 'jiuwenswarm/research_rsi/capsule_doctor.py')
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
t = time.monotonic()
r = d.require_source_closure(root, pins, entry_files=[root / 'runner.py', root / 'deploy/m1/rsi_development_run.py'])
print(json.dumps({'files': len(pins), 'seconds': round(time.monotonic() - t, 2),
                  **{k: r[k] for k in ('complete', 'module_count', 'resource_count', 'modules_sha256')},
                  'optional_missing': r['optional_missing'], 'deferred_missing': r['deferred_missing']}, indent=1))
EOF
$PY -I -B "$BUILD/closure_probe.py" "$RT" | tee "$RCPT/3-closure.json"
```

**CHECK:**

* `complete: true`. On this branch: 3235 files, about 1101 modules, 53
  resources.
* `SOURCE_CLOSURE_INCOMPLETE: missing <path> required by <file:line>` means
  the export is wrong: **STOP**.
* Record `seconds`. It took **18.4 s** on the review box. Section 5.4 turns
  this number into a go/no-go decision (known issue K1).

### 3.3 Captured worker runtime: reused unchanged

The worker runtime is not rebuilt. The loop grant pins the existing capture
(`rsi_capsule_slot.py:181-205`, `capsule_executor.py:105-145`):

* runtime root: the same `evaluator.runtime_root` as the last strict run
  configuration (section 3.4), under `/opt/ai4r-capsule-runtime-fcc60d-20261026-r1`
* manifest file sha `223db62241ff7ea95fb83e4b0eabbbe77f49b70a782d882f7dbbcc0ceeedd75a`
* canonical digest `95e4b2f607dc9768f8d33f2e15ba88600c148505e3761b4a6b286e530fcf944b`
* bootstrap `ai4r-rsi-capsule-bootstrap:2` (`targets/capsule_runtime.py:23`)

The fixture JSON (public, public_extended, held_out) lives under
`capsule_extensions/<name>/fixtures/` in `$RT`. It is read only by the Root
evaluator and never enters the runtime package (`capsule_runtime.py:44-46`).

### 3.4 Locate the reviewed strict originals (read-only inputs)

The durable slot template takes its stable values from the last reviewed
strict revision of each target. Find them; do not edit them:

```bash
ls -d /var/lib/ai4r-rsi-capsule-control/fcc60d-utilities-r1/*/ /opt/ai4r-capsule-prepare-*/configuration/*.json
```

For each target, export `STRICT_RUN_CALC`, `STRICT_PREP_CALC`,
`STRICT_LAUNCH_CALC` and `STRICT_PUB_CALC`, and the same four with suffix
`_NORM`:

| variable | Calculate (known) | Normalize (find the analogue) |
|---|---|---|
| `STRICT_RUN` | `/var/lib/ai4r-rsi-capsule-control/fcc60d-utilities-r1/calculate-r2/run-configuration.json` | newest `.../table_normalize-r*/run-configuration.json` with `schema` `ai4r-rsi-capsule-run-configuration:2` |
| `STRICT_PREP` | `/opt/ai4r-capsule-prepare-calculate-20261026-r2/configuration/calculate-r2-prepare.json` | the matching `/opt/ai4r-capsule-prepare-table_normalize-*/configuration/*.json` |
| `STRICT_LAUNCH` | the `launcher-configuration*.json` in the same control leaf | same |
| `STRICT_PUB` | `.../calculate-r2/publication-template-r4.json` (the template used for the reconciled R2 publication) | the newest `publication-template*.json` in its leaf |

Also read the last strict broker configuration. Its path is in the argv of
`$JOURNALS/broker-owner*.json` (newest), for example
`/etc/ai4r/cc-rsi-capsule-root-r2.json` or later. Set:

```bash
export OLD_ROOTCFG=<that path>      # read-only
export RESTORE=$($PY -c 'import json,sys;print(json.load(open(sys.argv[1]))["restore"]["path"])' "$STRICT_LAUNCH_CALC")
```

**CHECK:**

* Each `STRICT_RUN` has `session.capsule_name` equal to its target and
  `evaluator.manifest` with canonical digest `95e4b2f6...`.
* The two targets' `composition.core_root`, `input_root`, `native_lease_root`,
  `account_root`, `principal`, `exact_binding_refs` and `work_capsule_refs`
  are identical (one shared isolated Core,
  `/var/lib/ai4r-rsi-codex/development/host-codex-v6-screening-ui-1/core`).
* `STRICT_PUB.publication_directory` is
  `/var/lib/ai4r-rsi-codex/ui-development/host-codex-v6-screening-ui-1/publication`
  (gid 10001, mode 0750: `rsi_capsule_publication.py:744-747`).

---

## 4. Gateway and broker configuration

### 4.1 Durable directories and cgroup branches

These are fresh prefixes. Revision directories under them are created by
`make_directories` and are never reused (`rsi_capsule_slot.py:147-158`).

```bash
install -d -o root -g root -m 0755 "$NS"        # parents of 12001-owned revision dirs: Root, no group/other write
install -d -o root -g root -m 0700 "$CTL"
install -d -o root -g root -m 0711 "$EV"        # UID 12003 must traverse the evidence root's parent (rsi_capsule_launcher.py:119)
install -d -o root -g root -m 0700 "$SLOTS"
stat -c '%a %U %n' /var/lib/ai4r-rsi-capsule-evidence   # must allow 12003 search (>= 711)
for s in "$CALC_SLOT" "$NORM_SLOT"; do
  mkdir "$CGJOBS/$s"                              # refuses an existing branch
  cat "$CGJOBS/$s/cgroup.controllers"             # must contain memory and pids (jiuwenswarm/research/executor.py:166-176)
done
```

Compare `cgroup.subtree_control` with the last strict per-run branch (the
`cgroup_root` in `STRICT_LAUNCH`). If that branch has `memory pids` enabled,
enable the same here: `echo '+memory +pids' > "$CGJOBS/$s/cgroup.subtree_control"`.
Each job creates its own child group under the slot branch
(`executor.py:269`). Job ids include the run id, so successive revisions never
collide.

### 4.2 Durable slot templates (generated, then validated by the slot module)

Schema `ai4r-rsi-capsule-durable-slot:1`, closed field set
(`rsi_capsule_slot.py:26-33`, `:88-128`).

```bash
cat > "$BUILD/make_template.py" <<'EOF'
import hashlib, json, os, sys
from pathlib import Path
target, slot_id, run_p, prep_p, launch_p, pub_p, manifest_p, out = sys.argv[1:9]
E = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8')
run, prep, lau, pub = (json.loads(Path(p).read_bytes()) for p in (run_p, prep_p, launch_p, pub_p))
manifest = json.loads(Path(manifest_p).read_bytes())
grant = run['session']['grant']
assert run['session']['capsule_name'] == target == pub['meta']['target_id'], 'TARGET_DIFFERS'
assert hashlib.sha256(E(manifest)).hexdigest() == grant['runtime_manifest_sha256'] == hashlib.sha256(E(run['evaluator']['manifest'])).hexdigest(), 'MANIFEST_DIFFERS'
env = os.environ; c = run['composition']
value = {
  'schema': 'ai4r-rsi-capsule-durable-slot:1', 'target_id': target, 'slot_id': slot_id,
  'state_root': env['SLOTS'] + '/' + slot_id,
  'roots': {'namespace': env['NS'], 'control': env['CTL'], 'evidence': env['EV']},
  'composition': {**{k: c[k] for k in ('core_root', 'input_root', 'native_lease_root', 'account_root',
                                       'principal', 'exact_binding_refs', 'work_capsule_refs')},
                  'account_id': prep['account_id']},
  'evaluator': {'runtime_root': run['evaluator']['runtime_root'], 'manifest_path': manifest_p,
                'metadata': run['evaluator']['metadata'], 'cgroup_root': env['CGJOBS'] + '/' + slot_id},
  # Per-job limits are the reviewed strict ones; only the session wall grows to the loop ceiling.
  'grant': {'limits': dict(grant['limits'], wall_s=3600), 'iterations': grant['iterations'], 'horizon_s': 7 * 24 * 3600},
  # ``benchmark`` sizes the paired batched benchmark (merge wave). Omit a key to keep its
  # default; ``workloads`` defaults to the capsule's fixtures/benchmark.json in $RT.
  'loop': {'model_backend': {'kind': 'host-codex'}, 'max_iterations': 5, 'max_no_progress': 3, 'trials': 3,
           'per_call_s': 120, 'wall_s': 3600, 'benchmark': {'repetitions': 11, 'warmups': 2, 'per_job_s': 6}},
  'prepare': {'source_root': env['RT'], 'parent_declaration': prep['parent_declaration'],
              'request_text': prep['request_text'], 'observed_symptom': prep['observed_symptom']},
  'run': {'source_root': env['RT'], 'runner': env['RT'] + '/runner.py',
          'composition_path': env['RT'] + '/deploy/m1/rsi_development_run.py'},
  'launcher': {'launcher': env['ADM'] + '/rsi_capsule_launcher.py', 'restore': lau['restore']['path'],
               'seccomp': lau['seccomp']['path'], 'publisher': env['ADM'] + '/rsi_capsule_publication.py',
               'projection': env['ADM'] + '/cc_rsi_projection.py'},
  'publication': {'meta': {k: pub['meta'][k] for k in ('workspace_id', 'target_id', 'target_name', 'mutable_path')},
                  'publication_directory': pub['publication_directory']},
  'container': {'image': env['V18_IMAGE'], 'step_timeout_s': 900}}
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
os.write(fd, json.dumps(value, sort_keys=True, indent=1).encode()); os.close(fd)
print(out, hashlib.sha256(Path(out).read_bytes()).hexdigest())
EOF
export SLOTS NS CTL EV CGJOBS RT ADM V18_IMAGE
MANIFEST=/opt/ai4r-capsule-runtime-fcc60d-20261026-r1/manifest.json   # file sha 223db622...; verify before use
sha256sum "$MANIFEST"
$PY -I -B "$BUILD/make_template.py" utility.calculate "$CALC_SLOT" "$STRICT_RUN_CALC" "$STRICT_PREP_CALC" \
    "$STRICT_LAUNCH_CALC" "$STRICT_PUB_CALC" "$MANIFEST" "$ADM/slot-$CALC_SLOT.json"
$PY -I -B "$BUILD/make_template.py" utility.table_normalize "$NORM_SLOT" "$STRICT_RUN_NORM" "$STRICT_PREP_NORM" \
    "$STRICT_LAUNCH_NORM" "$STRICT_PUB_NORM" "$MANIFEST" "$ADM/slot-$NORM_SLOT.json"
chown root:root "$ADM"/slot-*.json && chmod 0444 "$ADM"/slot-*.json    # the broker pins mode exactly 0444
```

Validate with the slot module that the broker will load. This also checks
registration, the closed field sets, the cgroup prefix, and that the horizon
covers one run:

```bash
for s in "$CALC_SLOT" "$NORM_SLOT"; do
  env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$RT" $PY -B -c '
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("slot", sys.argv[1]); slot = importlib.util.module_from_spec(spec); spec.loader.exec_module(slot)
t = slot.validate_template(json.load(open(sys.argv[2])))
loop = slot.revision_loop(t)
print(t["slot_id"], "benchmark", loop.get("benchmark"), "deadline_s", slot.run_deadline_s(t["grant"], loop))' "$ADM/rsi_capsule_slot.py" "$ADM/slot-$s.json"
done
```

**CHECK:** with 8 benchmark workloads Calculate prints
`benchmark {'workloads': 8, 'repetitions': 11, 'warmups': 2, 'per_job_s': 6, 'wall_s': 7560}`
and `deadline_s 11580`; Normalize prints `'wall_s': 7416` and `deadline_s
11436`: loop wall 3600 + benchmark wall + 2×120 + 60 + 120 of launcher slack
(`rsi_capsule_slot.py` `run_deadline_s`, identical in
`rsi_capsule_launcher.py`). The benchmark wall is
`(max_iterations + 1) × benchmark_job_count × per_job_s` = 6 × 210 × 6
(Calculate) or 6 × 206 × 6 (Normalize): one A/A baseline plus at most one
benchmark per iteration, each the owner's exact job count (8 workloads × 11
pairs × 2 sides + 8 untimed × 2 + semantic edges × 2; warmups run inside
each timed job, so `per_job_s` covers them). A capsule without
`fixtures/benchmark.json` and without a template `benchmark` block prints
`benchmark None` and the historical `deadline_s 4020`. A `benchmark` block
without any workload count is refused (`BENCHMARK_WORKLOAD_COUNT_REQUIRED`),
never guessed. Set `benchmark.wall_s` explicitly to override the derived
wall. Both templates have mode 0444 and owner root.

What each revision then derives on its own, never hand-edited
(`rsi_capsule_slot.py:181-205`, `:263-344`):

* the revision's loop configuration: the template `loop` plus the
  materialized `benchmark` sizing above. It is written into the preparation
  configuration, so `session.loop.benchmark.wall_s` is the one value the
  runner, launcher and publisher read.
* grant v3 `ai4r-rsi-whole-capsule-development-grant:3`, with
  `max_executions = loop_execution_budget(cases, max_iterations=5, trials=3,
  benchmark=<materialized sizing>, capsule_name=<target>)` from the target
  owner (`capsule_executor.py`; preparation re-checks it with
  `loop_budget_for`). The slot never re-derives the formula. Without a
  benchmark it is the historical `19 × (3 + 3 × 5) = 342` for both capsules;
  with one it adds 6 × the exact per-call count: **1602** (Calculate, 210 jobs
  per benchmark) and **1578** (Normalize, 206). Calculate has 4 public + 8
  public_extended + 7 held-out cases; Normalize has 5 + 8 + 6.
* `limits.benchmark_wall_s` in the grant, equal to the sizing's `wall_s`
  (Root's dispatcher stops issuing jobs at `wall_s + benchmark_wall_s`; a
  session sizing without it is refused, `BENCHMARK_WALL_DIFFERS_FROM_GRANT`).
  The Root evaluator derives its benchmark repetitions/warmups from the same
  sizing; no evaluator `benchmark` block is needed in production.
* `wall_s` (run deadline, benchmark included) and `benchmark_wall_s` in the
  prepared ledger record; the broker refuses a revision whose horizon cannot
  cover that whole deadline plus the launch margin
  (`DURABLE_GRANT_HORIZON_INSUFFICIENT ... (N s deadline, including M s paired benchmark)`).
* `expires_unix_s = now + 604800`
* source pins of every file under `$RT/jiuwenswarm`
* runner, launcher, restore, seccomp, publisher and projection pins
* preparation, run, launcher and publication configurations

### 4.3 Policy v2 and the gateway configuration (`/etc/ai4r/cc-rsi-capsule-gateway.json`)

The app reads the gateway configuration once, at startup, as UID/GID 10001.
It requires the closed fields `schema policy gateway_public_key module_sha256`,
`schema` = `ai4r-cc-rsi-capsule-gateway:1`, Root ownership, mode `0440`, and
`module_sha256` equal to the sha256 of **the `cc_rsi_capsule.py` installed in
the app image**. It also requires the existing dedicated key
`/etc/ai4r/cc-rsi-development-gateway.key` (UID 10001, mode 0400, 32 bytes) to
match `gateway_public_key` (`cc_rsi_capsule.py:573-591`). Policy v2 has the
closed fields `schema workspace_id origin actors gateway_key_id slots`. A
durable slot is exactly `{target_id, mode: "durable", slot_id}`
(`cc_rsi_capsule.py:76-108`). The Root broker configuration must carry the
**identical** policy object: the click assertion is signed against the policy
fields, and Root re-verifies it (`cc_rsi_development.py:187-198`).

Do not install the new gateway configuration until the new app image exists
(section 6). Its `module_sha256` comes from the image. Prepare the policy now:

```bash
cp -p "$GW" "$ADMIN/build/gateway-before-$TAG.json"            # rollback copy (same bytes, mode kept)
sha256sum "$GW" "$ADMIN/build/gateway-before-$TAG.json"
$PY -I -B - "$GW" "$BUILD/policy-v2.json" "$CALC_SLOT" "$NORM_SLOT" <<'EOF'
import json, os, sys
old = json.load(open(sys.argv[1]))['policy']
policy = {k: old[k] for k in ('workspace_id', 'origin', 'actors', 'gateway_key_id')}
policy.update(schema='ai4r-cc-rsi-capsule-policy:2', slots=[
    {'target_id': 'utility.calculate', 'mode': 'durable', 'slot_id': sys.argv[3]},
    {'target_id': 'utility.table_normalize', 'mode': 'durable', 'slot_id': sys.argv[4]}])
fd = os.open(sys.argv[2], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400); os.write(fd, json.dumps(policy, sort_keys=True).encode()); os.close(fd)
EOF
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$RT" $PY -B -c '
import json, sys
from jiuwenswarm.research.cc_ui_runtime import module
cap = module("cc_rsi_capsule"); cap.policy(json.load(open(sys.argv[1]))); print("policy v2 valid")' "$BUILD/policy-v2.json"
```

If known issue K1 forces a single-slot first run (section 5.4), regenerate
this file with only the Calculate slot. Do it **before** sections 4.4 and 6,
because policy and broker slot set must match exactly
(`rsi_capsule_broker.py:160-161`).

### 4.4 Root broker configuration `ai4r-cc-rsi-capsule-root:2`

`load()` requires: Root ownership and mode 0600 for the configuration; the
closed field set `schema policy gateway_public_key module base_service
interpreter wrapper slots service_sha256 slot_module`; `service_sha256` equal
to the sha of the broker file being run; every pin Root-owned with mode
exactly 0444 and nlink 1. A durable slot entry is exactly `{target_id, mode:
"durable", template, launch_margin_s, max_consecutive_failures}`
(`rsi_capsule_broker.py:56-75`). Reuse `gateway_public_key`, `base_service`
and `interpreter` from the old strict root configuration. Re-verify their
bytes; never retype them.

```bash
$PY -I -B - "$OLD_ROOTCFG" "$BUILD/policy-v2.json" "$ROOTCFG" "$ADM" "$CALC_SLOT" "$NORM_SLOT" <<'EOF'
import hashlib, json, os, sys
old_p, policy_p, out, adm, calc, norm = sys.argv[1:7]
old = json.load(open(old_p)); policy = json.load(open(policy_p))
def pin(path):
    raw = open(path, 'rb').read(); return {'path': path, 'sha256': hashlib.sha256(raw).hexdigest()}
for key in ('base_service', 'interpreter'):
    assert pin(old[key]['path']) == old[key], key + '_BYTES_CHANGED'
slots = {'utility.calculate': calc, 'utility.table_normalize': norm}
value = {'schema': 'ai4r-cc-rsi-capsule-root:2', 'policy': policy, 'gateway_public_key': old['gateway_public_key'],
    'module': pin(adm + '/cc_rsi_capsule.py'), 'base_service': old['base_service'], 'interpreter': old['interpreter'],
    'wrapper': pin(adm + '/rsi_capsule_launcher.py'), 'slot_module': pin(adm + '/rsi_capsule_slot.py'),
    'slots': [{'target_id': s['target_id'], 'mode': 'durable', 'template': pin(adm + '/slot-' + slots[s['target_id']] + '.json'),
               'launch_margin_s': 300, 'max_consecutive_failures': 3} for s in policy['slots']],
    'service_sha256': pin(adm + '/rsi_capsule_broker.py')['sha256']}
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
os.write(fd, json.dumps(value, sort_keys=True, indent=1).encode()); os.close(fd)
print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())
EOF
chown root:root "$ROOTCFG" && chmod 0600 "$ROOTCFG"
stat -c '%U %a %h %n' "$ROOTCFG" "$ADM"/*     # config root 600; every $ADM file root 444, 1 link
```

**CHECK:**

* `interpreter.path` is a regular file such as `/usr/bin/python3.12`, not the
  `/usr/bin/python3` symlink. `base.pin` opens it with `O_NOFOLLOW`
  (`rsi_development_service.py:41-59`).
* `base_service` is the installed `rsi_development_service.py` that the old
  broker used. The broker also loads the installed
  `/opt/ai4r-cc-rsi-development/cc_rsi_development.py`
  (`rsi_capsule_broker.py:153-156`). Both are unchanged, Root-owned and mode
  0444.
* The template that each slot `template` pin points at has the slot `slot_id`
  that the policy names (`rsi_capsule_broker.py:212-214`).

### 4.5 Start the long-lived broker as an owned, finite process

The broker loads `cc_rsi_capsule` and the slot module by pinned path. It
imports `jiuwenswarm.research.cc_ui_runtime`, the targets and the executor
through `sys.path`, so `PYTHONPATH` must put `$RT` **first**. It must run with
`-B` and `PYTHONDONTWRITEBYTECODE=1`. A `__pycache__` appearing under
`$RT/jiuwenswarm` after pins are derived breaks the inventory check:
`SOURCE_CLOSURE_INVENTORY_DIFFERS` (`rsi_capsule_run.py:124-126`).

`serve` refuses to bind over an existing socket path:
`FRESH_CAPSULE_SOCKET_REQUIRED` (`rsi_capsule_broker.py:255-262`). The stopped
broker 103815 left its socket. Quarantine it, never delete it, and only after
proving no listener:

```bash
ss -xlp | grep -F "$SOCK" && { echo 'STOP: something still listens'; exit 1; } || true
INODE=$(stat -c %i "$SOCK"); echo "stale inode $INODE"
mv -n "$SOCK" "/run/ai4r-cc-rsi-development/.quarantine-capsule.sock-$INODE-$TAG"
```

Probe the imports, then start the broker detached and finite. GNU `timeout`
signals only its own process group. Launched runs survive the broker's end,
because `FixedLauncher` forks them into their own session
(`rsi_development_service.py:146-186`):

```bash
BENV=(env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
      PYTHONPATH="$RT:/opt/ai4r-rsi-host-codex/site-packages")
"${BENV[@]}" $PY -B -c 'import jiuwenswarm, cryptography; print(jiuwenswarm.__file__)'   # must print $RT/jiuwenswarm/__init__.py
# If cryptography is missing, append (after $RT) the remaining PYTHONPATH entries recorded for the old broker.
LOG=$JOURNALS/broker-loop-$TAG.log
setsid -f /usr/bin/timeout --signal=TERM --kill-after=60 86400 \
   "${BENV[@]}" $PY -B "$ADM/rsi_capsule_broker.py" serve --config "$ROOTCFG" >>"$LOG" 2>&1 </dev/null
sleep 3
TPID=$(pgrep -f "^/usr/bin/timeout .*rsi_capsule_broker.py serve --config $ROOTCFG")   # exactly one pid
BPID=$(pgrep -P "$TPID")                                                               # env exec'd into python
readlink /proc/$BPID/exe                                                                # must be $PY
$PY -I -B - "$BPID" "$JOURNALS/broker-owner-loop-$TAG.json" <<'EOF'
import json, os, sys, time
pid = int(sys.argv[1]); stat = open(f'/proc/{pid}/stat').read(); fields = stat[stat.rfind(')') + 2:].split()
argv = open(f'/proc/{pid}/cmdline', 'rb').read().rstrip(b'\0').split(b'\0')
rec = {'schema': 'ai4r-cc-rsi-capsule-broker-owner:2', 'pid': pid, 'start_ticks': int(fields[19]),
       'boot_id': open('/proc/sys/kernel/random/boot_id').read().strip(),
       'pid_namespace': os.readlink(f'/proc/{pid}/ns/pid'), 'mount_namespace': os.readlink(f'/proc/{pid}/ns/mnt'),
       'argv': [a.decode() for a in argv], 'deadline_unix': int(time.time()) + 86400}
fd = os.open(sys.argv[2], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600); os.write(fd, json.dumps(rec, sort_keys=True).encode()); os.close(fd)
print(rec)
EOF
stat -c '%U:%G %a' "$SOCK"          # root:10001 660
```

**CHECK:**

* The socket exists as `root:10001 660`.
* `$LOG` has no traceback.
* `$SLOTS/<slot_id>/00000001.preparing.json` appears within about 5 s: the
  monitor thread ticks every 5 s (`rsi_capsule_broker.py:241-254`,
  `cc_rsi_capsule.py:415-421`).

`resume`: only for a slot shown as FAILED (section 8.1). It appends one
`resumed` ledger record, never prepares or launches, and the running broker's
monitor then begins the next revision (`rsi_capsule_broker.py:285-298`,
`cc_rsi_capsule.py:517-524`):

```bash
"${BENV[@]}" $PY -B "$ADM/rsi_capsule_broker.py" resume --config "$ROOTCFG" --target utility.calculate
```

To stop the broker (rollback or replacement): re-read
`broker-owner-loop-$TAG.json`, verify pid, start ticks and boot id, then send
one `kill -TERM <pid>`. Do this only while no slot is `CLAIMED`. A `LAUNCHED`
run continues on its own, and on the next broker start it is retired as
`LAUNCHER_EXIT_UNOBSERVED` once its owner process is gone
(`rsi_capsule_broker.py:122-142`).

---

## 5. Slot preparation (automatic) and READY

### 5.1 What happens for revision k of each slot

Code: `cc_rsi_capsule.py:389-406`, `rsi_capsule_slot.py:263-344` and
`:347-374`.

1. Ledger `00000k.preparing.json` with `run_id = <slot_id>-rk`.
2. Fresh directories:
   * `$NS/<run_id>/{records,work,prepare}` (UID 12001, 0700)
   * `$CTL/<run_id>/` (Root, 0700) with `claim/` and `doctor-scratch/` (12001, 0700)
   * `$EV/<run_id>/` (Root, 0711)
3. `grant.json` (v3, 342 executions) and `prepare-configuration.json`.
4. **Prepare step**: V18 container `ai4r-capsule-prepare-<run_id>`, UID
   12001, no network, read-only root. It runs
   `-m deploy.m1.rsi_capsule_prepare`, which appends uploads (session-digest
   file names), qualified intake and **five** diagnosis/proposal Intent work
   pairs (`rsi-development:<run_id>:<role>` and `...:<role>:<k>` for k = 2..5)
   to the existing isolated Core through `ContractFactory`. It makes zero
   model calls (`rsi_capsule_prepare.py:87-193`).
   Evidence: `$CTL/<run_id>/prepare-{claim,exit}.json`, `prepare-stdout.log`
   and `$NS/<run_id>/prepare/prepared.json`.
5. **Compose doctor step**: V18 container `ai4r-capsule-doctor-<run_id>`,
   started as Root and dropping to 12001 with group 13000. Originals are
   mounted read-only. It snapshots Core, records and leases into the scratch
   directory, composes the frozen pipeline, checks native readiness without a
   model call, and derives source closure (`capsule_doctor.py:767-819`).
6. `compose-doctor.json` (receipt), `run-configuration.json`,
   `publication-template.json`, `launcher-configuration.json`, then ledger
   `00000k.prepared.json` with the revision record and its sha256 `revision`.

### 5.2 What the proofs look like

`$CTL/<run_id>/compose-doctor.json` (bytes identical to
`doctor-scratch/doctor-result.json`) must contain:

```text
schema ai4r-rsi-capsule-compose-doctor:1, status COMPATIBLE, actual_frozen_compose_completed true,
originals_unchanged true, model_calls 0, tool_calls 0, execution_jobs 0, work_claims 0, native_starts 0,
uid 12001, gid 12001, groups [13000], python {version [3,12,15], executable_sha256 4dbf3143...},
source_closure {schema ai4r-rsi-source-closure:1, complete true, module_count >0, resource_count, modules_sha256, entry_packages},
native_policy_sha256 / native_binding_sha256  (previous doctors: 4f0da075... / 5f80d472...)
```

The runner re-checks this receipt and the live relay digests on every
preflight (`rsi_capsule_run.py:252-272`, `:312-316`). The launcher preflight
reply that Root accepts is:

```json
{"schema":"ai4r-rsi-capsule-launch-preflight:1","ready":true,"run_id":"<slot_id>-r1",
 "configuration_sha256":"<run-configuration sha>",
 "source_closure":{"complete":true,"module_count":...,"resource_count":...,"modules_sha256":"..."},
 "worker_traversal":"simulated","dispatcher":"v18-bwrap"}
```

(`rsi_capsule_launcher.py:102-127`, `:155-177`, `rsi_capsule_broker.py:78-87`.)
`dispatcher` must be `v18-bwrap`. The template never sets `dispatcher`, so the
protected path is used (`capsule_local_dispatcher.py:157-165`).

### 5.3 Native read-only check that the catalog sees READY

The broker accepts requests only from UID 10001 (`rsi_capsule_broker.py:268-269`).
Ask it for status as that UID. This is the same request the app sends
(`cc_rsi_capsule.py:180`):

```bash
cat > "$BUILD/status.py" <<'EOF'
import json, socket, sys, time
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(300); s.connect(sys.argv[1])
t = time.monotonic()
s.sendall(json.dumps({'protocol': 'ai4r-cc-rsi-capsule:1', 'operation': 'status'}).encode() + b'\n')
raw = b''
while not raw.endswith(b'\n'):
    part = s.recv(4096)
    if not part: break
    raw += part
print(json.dumps({'seconds': round(time.monotonic() - t, 2), 'reply': json.loads(raw)}, indent=1))
EOF
chmod 0444 "$BUILD/status.py"; cp "$BUILD/status.py" /var/tmp/capsule-status-$TAG.py
setpriv --reuid=10001 --regid=10001 --clear-groups $PY -I -B /var/tmp/capsule-status-$TAG.py "$SOCK"
```

Expected once both preparations finish (a few minutes; repeat the call):

```json
{"schema":"ai4r-cc-rsi-capsule-status:2","slots":[
 {"target_id":"utility.calculate","mode":"durable","revision":"<64 hex>","run_id":"calc-loop-YYYYMMDD-r1",
  "sequence":1,"ready":true,"phase":"READY","blocker":null,"security_status":"SECURITY_DEFERRED"},
 {"target_id":"utility.table_normalize", ... "phase":"READY" ...}]}
```

Phases: READY, BLOCKED, CLAIMED, LAUNCHED, PREPARING or FAILED
(`cc_rsi_capsule.py:464-492`). While one slot's prepare or doctor container
runs, the other slot is BLOCKED with `OWNED_RUNTIME_NOT_IDLE`. The launcher
requires an idle RSI Docker daemon (`rsi_capsule_launcher.py:160`). That is
expected and clears on its own.

### 5.4 Readiness latency check (known issue K1, fixed)

Since K1 was fixed, readiness is computed off the request path:

* **Closure proof, once per package.** Root preparation walks the source
  closure once and writes Root-owned, mode 0444 proofs to
  `$RT/.ai4r-source-closure/<key>.json` (`rsi_capsule_slot.py:366`,
  `capsule_doctor.py:626`). The key covers the walker's own source sha, the
  pins digest, the entry program bytes and the entry roots. There is one proof
  for the doctor/controller entry set and one for the launcher entry set.
* **Reuse without a re-walk.** The launcher preflight
  (`rsi_capsule_launcher.py:125`), the runner's `load_sources`
  (`rsi_capsule_run.py:133`) and the compose doctor reuse a proof only after
  re-verifying the actual `jiuwenswarm/` inventory and every byte against the
  pins. Any change to the package, the entry programs or the walker selects a
  new key and forces exactly one new walk. Read-only mounts (doctor, worker)
  only read proofs. Without the proof directory every caller walks as before.
* **Cached readiness.** Each slot has its own background thread
  (`cc_rsi_capsule.py:403`, `:850`; `rsi_capsule_broker.py:252`). The thread
  runs the unchanged full preflight (closure, traversal, idle runtime, runner
  preflight, relay check) every `readiness_refresh_s`, and again right after
  any state transition. A status request returns the cached row with
  `observed_unix_s` and `age_s`, which the gateway passes on in each target's
  `run` gate.
* **Phases.** PREPARING, FAILED, CLAIMED and LAUNCHED are read directly from
  the ledger and journal. A row older than `readiness_stale_s` is `BLOCKED`
  with `READINESS_STALE: ...`. A state Root has not checked yet is `BLOCKED`
  with `READINESS_PENDING: ...`. Neither is ever "unavailable".
* **Click window.** A signed click is checked against its own window at Root
  receipt, before any lock, refresh or preflight can delay it
  (`cc_rsi_capsule.py:359`). The gateway signs only after its readiness read.

The timeouts are now configuration, with the old values as defaults:

| where | optional key | fields (defaults) |
|---|---|---|
| broker root config (section 4.4) | `timeouts` | `preflight_s` 45, `request_s` 45, `click_window_s` 30, `readiness_refresh_s` 30, `readiness_stale_s` 120 |
| gateway config (section 4.3) | `timeouts` | `exchange_s` 45, `click_window_s` 30 |
| slot template `launcher` (section 4.2) | `timeouts` | `runner_preflight_s` 30, `docker_s` 45 |

The broker refuses unknown keys, values outside 1–3600, and
`readiness_stale_s < readiness_refresh_s`. Keep the gateway `click_window_s`
at or below the broker's.

Measure, while both slots are READY:

```bash
ls -l "$RT/.ai4r-source-closure/"           # two root 0444 proofs after the first preparation
REC=$(ls "$SLOTS/$CALC_SLOT"/*.prepared.json | tail -1)
LC=$($PY -c 'import json,sys;v=json.load(open(sys.argv[1]))["value"]["launcher_configuration"];print(v["path"],v["sha256"])' "$REC")
time env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin PYTHONDONTWRITEBYTECODE=1 HOME=/root \
     PYTHONPATH=/opt/ai4r-rsi-frozen-v18-03ed3199:/opt/ai4r-rsi-host-codex/site-packages \
     $PY -B "$ADM/rsi_capsule_launcher.py" preflight --configuration ${LC% *} --configuration-sha256 ${LC#* }
```

The environment above is `base.ENV`, which the broker uses
(`rsi_development_service.py:33-34`). Then record `seconds`, and each slot's
`run.age_s`, from the status call.

**Decision:**

* Status under 1 s, both slots READY, and `age_s` ≤ `readiness_stale_s`:
  continue with two slots.
* No proofs under `$RT/.ai4r-source-closure`, or a direct preflight still
  takes about the full walk time (18 s on the review box) on its second run:
  the proof is not being reused. Check the custody of `$RT` and of the proof
  directory: Root owner and no group/other write. Fix it before continuing.
* A slot stays `BLOCKED READINESS_STALE`, or a direct preflight is over the
  broker's `preflight_s`: **STOP**. Report the numbers and `$LOG`. You can
  raise the bounds with the `timeouts` keys above (new `TAG`), but never to
  hide a failing preflight.

---

## 6. App rebuild and reversible handoff of 5175

The app must contain this branch's server and frontend before the first loop
publication. Its projection validator accepts the run `lineage` block, and its
gateway module must hash to the `module_sha256` written in section 6.3.

### 6.1 Frontend build

W5 changed `jiuwenswarm/channels/web/frontend/src/features/rsi/`:
`CcRsiWorkbench.tsx`, `ccLoop.ts`, `ccTypes.ts`, `components/CcLoopTimeline.tsx`
and `styles/cc-rsi.css`.

```bash
cd /var/tmp/rsi-loop-src-$TAG/jiuwenswarm/channels/web/frontend
npm ci --no-audit --no-fund && npm run test:cc-rsi && npm run build        # tsc && vite build -> dist/
find dist -type f | wc -l; tar -C dist -cf "$BUILD/frontend.tar" .
```

### 6.2 Image build: derived from the live image with `installed_app_rebuild.py`

The live image `sha256:de43e2de...` was produced by the offline rebuild
pattern in `deploy/m1/installed_app_rebuild.py`:

1. A derived image puts `plan.json`, `base-installed-build.json`,
   `source.tar` and `frontend.tar` under `/run/ai4r-code-build`.
2. In `/tmp`, as Root, it runs the installer.
3. The installer verifies the inherited build identity and dependencies.
4. It extracts only listed regular files, builds and installs one wheel
   offline, verifies the installed frontend, and rewrites the build identity.
5. It writes `/usr/local/share/ai4r-rsi-ui-build.json` and removes the build
   directory (`installed_app_rebuild.py:115-178`).

If L contains the plan generator used for build `ef61f2ef...` (search L for
`ai4r-installed-app-rebuild:1`), reuse it with the new source. Otherwise build
`plan.json` as the installer requires:

* closed keys `schema base_manifest_sha256 source_archive_sha256 source_files
  frontend_archive_sha256 frontend_files installer_sha256`
* `source_files` and `frontend_files` are `[{path, size, sha256}]` over
  regular files only
* `source.tar` is the `git -c core.autocrlf=false archive` of HEAD. Leave out
  symlinks and `jiuwenswarm/channels/tui/frontend/{dist,node_modules}`
  (`installed_app_rebuild.py:136-141`).
* `uv.lock` and `pyproject.toml` must equal the base. The installer refuses
  dependency changes: `DEPENDENCY_INPUT_CHANGE_REQUIRES_FULL_BUILD`.

Use App Docker (`docker build`). The installer does not need the network.

**CHECK:**

* The build prints the `ai4r-installed-app-rebuild-complete:1` receipt with
  `dependencies_unchanged: true`, `tui_unchanged: true` and `model_calls: 0`.
* `docker image inspect <new> --format '{{json .Config}}'` equals the base
  image `Config` in `User`, `Entrypoint`, `Cmd`, `Env`, `WorkingDir` and
  `ExposedPorts`. A derived Dockerfile that switches to `USER root` must
  switch back.
* The installed module hash is the one the gateway will check:

  ```bash
  docker run --rm --network none --entrypoint sha256sum <new-image> \
    /opt/venv/lib/python3.12/site-packages/jiuwenswarm/server/rsi/cc_rsi_capsule.py
  # expected 44b459e3cf72cbcadc6b656f2783b14ed018a74c68f4c229f6b94385aae9c904 (= $ADM/cc_rsi_capsule.py)
  ```

  Also check `cc_rsi_projection.py` = `3f6b0aa2...` and
  `channels/web/frontend/dist` equal to your `dist/` inventory.

### 6.3 Install the gateway configuration (in place, same custody)

```bash
MOD=$(docker run --rm --network none --entrypoint sha256sum <new-image> /opt/venv/lib/python3.12/site-packages/jiuwenswarm/server/rsi/cc_rsi_capsule.py | cut -d' ' -f1)
$PY -I -B - "$GW" "$BUILD/policy-v2.json" "$MOD" "$BUILD/gateway-new-$TAG.json" <<'EOF'
import json, os, sys
old = json.load(open(sys.argv[1])); policy = json.load(open(sys.argv[2]))
value = {'schema': 'ai4r-cc-rsi-capsule-gateway:1', 'policy': policy,
         'gateway_public_key': old['gateway_public_key'], 'module_sha256': sys.argv[3]}
fd = os.open(sys.argv[4], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o440); os.write(fd, json.dumps(value, sort_keys=True).encode()); os.close(fd)
EOF
stat -c '%U:%G %a' "$GW"        # the live file's custody (root:<gid readable by 10001> 440); copy it exactly
cmp <($PY -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1]))["policy"],sort_keys=True))' "$ROOTCFG") \
    <($PY -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1]))["policy"],sort_keys=True))' "$BUILD/gateway-new-$TAG.json") && echo policy-identical
chown root:$(stat -c %g "$GW") "$BUILD/gateway-new-$TAG.json"; chmod 0440 "$BUILD/gateway-new-$TAG.json"
```

Check how `$GW` reaches the container (`docker inspect ba1920af` → `Mounts`):

* **directory bind** of `/etc/ai4r`: install with
  `cp --preserve=mode,ownership "$BUILD/gateway-new-$TAG.json" "$GW.new" && mv "$GW.new" "$GW"`.
* **file bind**: the same rename gives the old container's bind the old inode.
  The new container binds the new file. Either way, do it **after**
  `ba1920af` is stopped (section 6.4, step 2).

`$ADMIN/build/gateway-before-$TAG.json` stays as the rollback copy.

### 6.4 Replace the container reversibly

1. `docker inspect ba1920af... > "$RCPT/app-before.json"`. Canonicalize
   `Mounts` by unique `Destination`, keeping all attributes (Docker's order is
   not deterministic). Expect 15 mounts, 8 named volumes and
   `127.0.0.1:5175->5173/tcp`.
2. `docker stop ba1920af...`. Do **not** remove it. Install the gateway
   configuration (section 6.3).
3. Create the replacement from the inspected `Config` and `HostConfig` with
   only `Image` changed: same env, user, entrypoint, mounts, volumes, port
   binding, restart policy, security options and limits. Use a new name such
   as `<old-name>-loop-$TAG`. The earlier handoff saw exactly one
   create-API normalization, nullable `OomKillDisable` → `false`; anything
   else that differs: **STOP** before starting it.
4. `docker start <new>`. **CHECK:** the inspected mounts, volumes, env and
   ports are equal to `app-before.json` except `Image`, `Id`, `Name` and
   state. `curl -sI http://127.0.0.1:5175/` returns 200.
5. App logs show no `Capsule gateway installation differs`. That message means
   the module hash or custody check failed (`cc_rsi_capsule.py:578-583`).

### 6.5 Authenticated native WS checks (read-only)

Use the read-only native WS checker that produced
`$L/capsule-native-integration-readonly-r2.json` (search L for
`rsi.cc.targets.list`). Do not create new credentials. Use only the existing
native session mechanism. Requests are `rsi.cc.targets.list` with params `{}`
(any parameter is refused), `rsi.cc.snapshot` with `{}`, and, for one node,
`rsi.cc.candidate.get` (`research_http.py:408-466`). Do **not** send
`rsi.cc.run.start`.

**CHECK:**

* `rsi.cc.targets.list`:
  * Calculate and Table Normalize each have `development_grant_status` READY,
    `run_id` `<slot_id>-r1`, `revision` equal to the status call in 5.3, and
    `run` = `{allowed: true, blocker: null, phase: "READY", revision: ...}`.
  * `research.builder` is still blocked.
* `rsi.cc.snapshot`: the target `run` overlays carry the same phase and
  revision (`cc_rsi_capsule.py:252-258`). Screening has two nodes and its
  completed consumed run. Runs `fcc60d-calculate-ui-r1` and
  `fcc60d-calculate-ui-r2` are present with stage `Failed`. Their run rows
  and nodes are byte-identical (canonical JSON) to the copies saved in
  section 1.3.
* `publication.json` sha is still `4867784c...`. Setup publishes nothing.
* No new Core model or tool rows. Preparation appends uploads, intake, runs
  and contract records. The R2 preparation receipt
  (`docs/review/evidence-20261026/capsule-calculate-metadata-r2-outcome.json`)
  shows `attempts`, `model_calls` and `tool_calls` unchanged at 2, 2 and 0.
  Expect the same, and record the actual counts.

Save as `$RCPT/6-native-readonly.json`. Browser click testing is not claimed
unless a human actually does it.

---

## 7. First real run (human click only)

### 7.1 Before the click

* The keeper has at least 90 minutes left. The relay `check` shows
  `TRANSPORT_AVAILABLE`, `active: false`, `unresolved: false`.
* The status call (section 5.3) shows Calculate READY. Note its `revision`
  and `run_id` (for example `calc-loop-20261027-r1`).
* Tell the user: the click starts a real loop with up to **10 gpt-6.1-sol
  calls** (medium, no tools), up to 342 protected V18 jobs, and up to about 67
  minutes. Then wait. **Do not click for the user and do not send
  `rsi.cc.run.start` yourself.**

### 7.2 What the loop does

Code: `capsule_loop.py:513-727`, `capsule_session.py:110-208`,
`rsi_capsule_run.py:351-605`.

1. Root accepts the click. Gateway signature, durable revision, preflight,
   then journal `claim.json` → fork → `owner.json` → `launch.json` →
   `ack.json` (`cc_rsi_development.py:187-215`). Phase becomes CLAIMED, then
   LAUNCHED.
2. Launcher: preflight again, `run-claim.json`, worker container
   `ai4r-capsule-<run_id>` on RSI Docker (V18 image, Root with 6 caps, no
   network, read-only root filesystem).
3. The runner forks the Root evaluator. The controller drops permanently to
   12001:12001 with group 13000 and composes the frozen pipeline.
4. **Parent:** 19 cases × 3 trials = 57 jobs. Parent control requires the
   historical `public` group to pass. Calculate passes 4/4 public and 11/19
   overall: 8 of the 15 harder cases fail, 4 public_extended and 4 held-out,
   which is the `max()` tie headroom. Normalize passes 19/19. A failing public
   case ends the run before any model call (`PARENT_CONTROL_FAILED_NO_MODEL_CALL`).
   The parent trials calibrate the noise floor.
5. **Iterations 1..5**, each with one diagnosis call and one proposal call on
   iteration k's own prepared contract pair:
   * a duplicate body is not re-evaluated
   * otherwise the candidate gets 19 cases × 3 trials. Repeat trials are
     skipped if a case timed out.
   * a candidate that passes correctness (non-regression) then gets the
     **paired batched benchmark** against the parent (Interface E, 8
     workloads × 11 AB/BA pairs, both sides, warmups inside each job, plus
     untimed and semantic-edge cases: 210 protected jobs for Calculate, 206
     for Normalize, recorded as `loop.iterations[k].benchmark`); the loop
     also records one parent A/A baseline (`loop.benchmark_baseline`, the
     benchmark's self-noise, never a gain). A candidate that is not
     benchmarked records `benchmark: null` and the reason in
     `benchmark_decision`.
   * the candidate is scored against the parent and selected against the
     incumbent. `score.latency_method` is `paired_batched_benchmark` when the
     benchmark ran, else `single_job_floor`. It is kept only if correctness
     does not regress AND (correctness rose OR the benchmark
     `objective_met`).
   * the feedback for the next iteration carries failing ids, public diffs and
     timing deltas. Held-out cases go out only as ids and pass/fail.
6. **Stop reasons** (`capsule_loop.py:35`, `:500-510`, `:561-567`):
   * `max_iterations`: 5 done
   * `no_progress`: 3 consecutive iterations not kept
   * `budget`: 10 model calls, the grant's `max_executions` (342 without a
     benchmark; 1602 / 1578 with it), or no prepared contract left
   * `deadline`: loop wall 3600 s plus the materialized benchmark wall
   * `error`: an unknown model effect, evaluator refusal or relay loss.
     Nothing is retried.
7. The worker stops. The launcher records `run-exit.json` and
   `run-stdout.log`, then publishes from retained evidence
   (`rsi_capsule_launcher.py:210-254`). The broker reaper writes
   `launcher-exit.json`. The slot retires revision 1 and prepares revision 2
   automatically (PREPARING, then READY with a new revision). That makes Run
   re-runnable. Do not click again unless the user asks.

### 7.3 Where to watch (all read-only)

| what | where |
|---|---|
| phase and revision | status call (section 5.3), every minute or so. Each call runs preflights; do not loop tightly. |
| launch journal | `$JOURNALS/<run_id>/{claim,owner,launch,ack,launcher-exit}.json`, `launcher.log` |
| worker container | `rsidocker ps`, `rsidocker logs ai4r-capsule-<run_id>` |
| protected job progress | `ls $EV/<run_id>/claims/capsule-*.json \| wc -l` (one start claim per job, evaluation and benchmark jobs alike, ≤ the grant's `max_executions`) |
| evaluator terminal | `$EV/<run_id>/complete.json` (status STOPPED, `stop`, `executions`, `evaluations`) or `failure.json` |
| session result | `$NS/<run_id>/records/capsule-result.json` (`ai4r-rsi-capsule-session-result:1` with `loop`) or `controller-failure.json` plus the controller-terminal record |
| control | `$CTL/<run_id>/run-{claim,container,exit}.json`, `run-stdout.log` (last line `ai4r-rsi-capsule-run-terminal:1` with `stop_reason` and `completed_iterations`), `publication-receipt.json` or `publication-failure.json` |

Expected durations, from measured protected times (baseline: Calculate 4 jobs
2.84 s, Normalize 5 jobs 3.25 s, i.e. about 0.7 s per job plus sandbox
overhead):

* 342 evaluation jobs: roughly 5–15 min.
* Model calls: 10 × 30–120 s (the relay timeout is 120 s per call).
* Paired batched benchmark, per benchmarked candidate and once for the
  baseline: 210 (Calculate) / 206 (Normalize) protected jobs, 176 of them
  timed batch jobs. Estimated
  from Codex's protected amortized medians (`performance-20261027-*`, batch
  sizes 1000 small / 20 large) plus ~0.7 s sandbox start: **Calculate about
  4–5 s per job, 14–18 min per benchmark; Normalize about 1.5–2 s per job,
  5–7 min per benchmark.** Only candidates that pass correctness are
  benchmarked.
* Typical total without a benchmark: 15–40 min. With it: Calculate about
  1–2 h (baseline plus 2–5 benchmarked candidates), Normalize about 45–75 min.
* Hard ceilings: session `wall_s + benchmark.wall_s + 2 × per_call_s + 60`
  = 3600 + 7560 + 240 + 60 = 11460 s (Calculate) with the default sizing;
  launcher and slot deadline 11580 s (11436 s Normalize; 4020 s without a
  benchmark); the evaluator alarm, controller and model-start deadlines use
  the same session value (`rsi_capsule_run.run_wall_s`, alarm + 30 s close
  grace); Root's dispatcher stops issuing jobs at `wall_s +
  benchmark_wall_s` after its start. Raise `benchmark.per_job_s`
  for slower hardware rather than letting the deadline stop a run; the
  duration figures are estimates, the deadline is the hard bound.

### 7.4 What a successful publication looks like

`publication-receipt.json` = `{publication_sha256, model_calls: 0, qualification: false}`.
The previous bytes are archived in
`<publication_directory>/.capsule-history/<old-sha>.json`
(`rsi_capsule_publication.py:784-797`). `publication.json` now has
(`rsi_capsule_publication.py:509-599`):

* **Run row** `<run_id>`:
  * `stage` is `Complete`. It is `Partial` when `stop_reason` is `error` or
    issued ≠ served jobs, and `Failed` for an interrupted parent or a startup
    failure.
  * `status` is `VISIBLE_EVALUATED_UNQUALIFIED`.
  * `budget` has diagnosis and proposal call counts, `generation_call_limit`
    10 and `limit_seconds` 3600 (3600 + `benchmark.wall_s`, e.g. 11088, with
    the paired benchmark).
  * `activity` has the parent evaluation, one row per iteration (outcome and
    reason), one `Performance evaluation` row per benchmarked candidate
    (id `<run_id>:performance:<report sha>`, status `OBJECTIVE_MET` or
    `OBJECTIVE_NOT_MET`, summary `Measured improvement under the frozen
    protected batch protocol; security remains deferred.` or `No demonstrated
    improvement ...`), and the terminal summary
    `stop: <reason>, k/5 iterations; security campaigns deferred`.
* **`run.lineage`** (`cc_rsi_projection.project_loop`): `max_iterations` 5,
  `completed_iterations`, `stop_reason`, `model_backend`
  `{kind: host-codex, model: gpt-6.1-sol, pinned_sha256}`, `model_calls`,
  `parent_node_id` `base:<parent sha>`, `best_iteration`, `best_node_id`, the
  parent summary, and one entry per iteration. A run whose loop recorded a
  benchmark or a `latency_method` is `ai4r-cc-rsi-lineage:2`: it adds
  `benchmark_baseline` and, per iteration, `latency_method`,
  `benchmark {report_ref, relative_gain, ratio_confidence_interval, gates
  {minimum_gain, ci_upper_bound, max_workload_regression}, objective_met,
  protected_jobs, repetitions, workloads[{id, median_ratio}]}` and
  `improvement_basis` (`correctness`, `paired_batched_benchmark` or null).
  The UI claims an improvement only from that basis; a `single_job_floor`
  latency is labelled "single-job floor · not a measured speedup". Older
  loop runs keep `ai4r-cc-rsi-lineage:1` and render as before.
* **One node per distinct candidate**:
  * id `candidate:<run_id>:<sha>`, label `utility.calculate iteration k`,
    `parent_id` the published baseline node
  * `evaluation_status` is `passed`, `failed` or `not_evaluated`
  * `correctness` reads `p/19 checks (a/12 public, b/7 held-out)`
  * a benchmarked candidate's `speed` and `noise` use Codex's
    `performance-publish` text exactly, e.g.
    `Measured improvement: 16.78% amortized protected batch gain; original job latency separate. Uncalibrated public job totals: parent 2.768465 s, candidate 2.635614 s.`
    and `95% paired ratio interval [0.8185, 0.8418]; 11 AB/BA pairs per workload.`;
    its `evidence_refs` end with the benchmark `report_ref`. A
    `single_job_floor` node reads `<wall> s protected total; single-job floor,
    not a measured speedup`; a node with neither keeps `...; uncalibrated`.
  * every report is joined to Root originals before it is shown: its own
    bytes (`report_ref`), one retained original per protected job
    (`evidence_refs`, count = `protected_jobs`), parent/candidate hashes and
    capsule, gates consistent with `objective_met`, never a
    `local_unprotected` report. Served jobs = evaluation executions + every
    report's `protected_jobs`; they must equal Root's issued start claims for
    a `Complete` stage.
  * `security_status` `SECURITY_DEFERRED`, `admission_status` `unadmitted`,
    `activation_status` `inactive`, admit and activate denied
  * a matching `candidates` row holds parent and candidate code plus the
    rationale. Poor and failed candidates are included.
* The Screening, R1 and R2 rows and nodes are unchanged
  (`merge_publication`, `rsi_capsule_publication.py:192-211`).

**Calculate expectation.** A correct proposal makes the `max()` result
ordering-stable on equal Decimals (for example `"1.0"` vs `"1.00"`). It should
score 19/19 with `improved: true` and `newly_passed` equal to the 8 parent
failures. It becomes `best`. The test gate in section 2.3 asserts exactly this
on the real fixtures with a scripted model. The real model may need more than
one iteration, or may fail to find it. Report what happened; do not re-run to
get a better result.

**Then Table Normalize.** After Calculate is terminal, its slot shows
PREPARING and then READY (r2). The Normalize slot clears its transient
`OWNED_RUNTIME_NOT_IDLE` BLOCKED state and shows READY. Ask the user to click
Run on Normalize. The parent is already 19/19, so the only headroom is latency.
`improved` is true only when the paired batched benchmark meets its objective
(gain ≥ 10%, CI upper ratio ≤ 0.90, no workload > 5% slower); the UI then
shows the gain % with its CI band, and the best badge reads
`Best candidate · iteration k · +x.xx% paired batch gain measured`. Without
a benchmark the old single-job floor still runs but is never shown as a
speedup. `improved: false` with stop `no_progress` is a legitimate, honest
outcome.

After each run, write `$RCPT/7-<target>.json` with: run id, revision, stop
reason, completed iterations, model calls, issued and served jobs (benchmark
jobs included), best iteration, best correctness, best `relative_gain` and
`ratio_confidence_interval` with its report sha, publication sha, and the
Core model_calls, tool_calls and attempts counts.

### 7.5 What changed from Codex's performance runs

Codex measured Calculate 16.78% and Normalize 20.74% out of band:
a one-shot generated session (`perf271027-*`, 2 model calls), then a
separate protected benchmark under
`/var/lib/ai4r-rsi-capsule-control/performance-20261027-*/<capsule>/`, then a
reviewed `performance-publish` (`ai4r-capsule-performance-publication:1`)
that appended gain/CI text, the report ref and a `Performance evaluation`
activity to the already-published node. Those nodes and runs are in the live
`publication.json` and stay there: `merge_publication` retains them, they
have no `lineage` (legacy rows) and the projection serves their `speed` and
`noise` strings byte-for-byte (tested against
`docs/review/evidence-20261027-codex/`). **Do not replay them.** There is no
`performance-publish` operation in this publisher.

| Codex performance run | new loop flow |
|---|---|
| separate benchmark after the session | Interface E inside the loop's own grant, once per correct candidate plus one baseline |
| `ai4r-rsi-capsule-protected-benchmark-report:1` (raw `samples`) + `validate_benchmark_report` → `ai4r-rsi-capsule-performance-comparison:1` | `ai4r-rsi-capsule-benchmark-report:1` carrying the comparison directly |
| `comparison.relative_gain`, `.ratio_confidence_interval`, `.objective_met` | `report.relative_gain`, `.ratio_confidence_interval`, `.objective_met` (same meaning) |
| `comparison.rows[].median_ratio` | `report.workloads[].median_ratio` |
| frozen gates 0.10 / 0.90 / 0.05 in the protocol | `report.gates.{minimum_gain, ci_upper_bound, max_workload_regression}` |
| `protocol.repetitions` 11, warmups 2 | `report.repetitions`; slot `benchmark.{repetitions, warmups}` |
| report `evidence_refs` (192 = 176 timed + 16 correctness) | same, with `protected_jobs == len(evidence_refs)`, counted in grant `max_executions` and Root start claims |
| plan input `report_ref` | `loop.iterations[k].benchmark.report_ref` |
| node `speed`/`noise` text, activity `<run>:performance:<sha>` | identical text and activity id, written by `completed-publish` |
| no lineage | `ai4r-cc-rsi-lineage:2` with gain, CI, gates, `improvement_basis` |
| deadline outside any run | in the run deadline (`benchmark.wall_s`) and slot horizon |

To compare a new loop result with Codex's evidence, read its
`final-integration-index.json` `measured_results[]` (gain, ratio CI,
`objective_met`, report sha) beside the new iteration's `benchmark` block;
both describe the same quantity (relative reduction in amortized protected
batch wall).

---

## 8. Failure triage (evidence first, never re-execute)

Rules for every case:

* Read the retained evidence and report it.
* A consumed revision is never retried. Recovery is always a **new**
  revision: the automatic successor, or a new TAG and configuration.
* A publication failure is reconciled later from the same evidence, never by
  running the session again.

### 8.1 Slot phases

| phase / blocker | read | fix path |
|---|---|---|
| `PREPARING` for more than about 15 min | `$SLOTS/<slot>/*.json`, `$CTL/<run_id>/{prepare,doctor}-{claim,exit}.json`, `*-stdout.log`, `rsidocker ps -a` | Wait while a step container is running (step timeout 900 s). A step past its deadline raises `STEP_DEADLINE_EXPIRED_RECONCILE_NO_REPLAY` and stays running (K4): wait until `rsidocker inspect` shows it stopped before anything else. |
| `FAILED` (3 consecutive preparation failures) | newest `*.failed.json` (`exception_type`, `message`) and the step logs above | Fix the cause (custody, relay, image, path). Then run `resume --target <id>` (section 4.5). Never delete ledger entries. |
| `BLOCKED: ... OWNED_RUNTIME_NOT_IDLE` | `rsidocker ps` | Transient while another slot prepares or runs. Wait. |
| `BLOCKED: ... OWNED_GROUP_NOT_EMPTY` | `$CGJOBS/<slot>/**/cgroup.procs` | A job group still has processes. Find out why; never kill blindly. |
| `BLOCKED: ... CONTROLLER_READONLY_RELAY_STATUS_UNAVAILABLE` or `CLOSED_IDLE_NATIVE_RELAY_REQUIRED` | relay `check` | Relay down, active or unresolved (section 1.4). Unresolved: **STOP**. |
| `BLOCKED: ... COMPOSE_DOCTOR_NATIVE_BINDING_DIFFERS` | `compose-doctor.json` vs live relay digests | The relay was re-prepared with a different binding after the doctor ran. **STOP**. Do not edit receipts. |
| `BLOCKED: ... SOURCE_CLOSURE_INCOMPLETE: missing X required by Y` or `COMPLETE_CAPSULE_PACKAGE_CLOSURE_REQUIRED` | message (exact path) | The package is wrong. Build a new `$ADMIN` (new TAG) from a correct export. Never patch files under a pinned prefix. |
| `BLOCKED: ... SOURCE_PIN_DIFFERS` or `SOURCE_CLOSURE_INVENTORY_DIFFERS` | `find $RT -newer <run-configuration.json>` | A file under `$RT` changed or `__pycache__` appeared. New TAG. Always use `-B`. |
| `BLOCKED: ... WORKER_TRAVERSAL_BLOCKED: {"path": ..., "reason": "not_searchable", ...}` | that path's mode and owner | An ancestor of `$EV` or the runtime tree is not searchable or listable by 12003. Set the evidence ancestors to at least 0711. Never loosen the runtime capture (it is pinned). |
| `BLOCKED: ... WORKER_TRAVERSAL_UNCORRECTABLE` | `$EV/<run_id>/{,assets,work}` | A non-Root owner or group/other write on evidence directories. New revision. |
| `BLOCKED: ... DURABLE_GRANT_HORIZON_INSUFFICIENT` or `CAPSULE_GRANT_HORIZON_BELOW_ONE_RUN` | revision `expires_unix_s` | Expected near the end of the 7-day horizon. The monitor retires it as `GRANT_HORIZON_REFRESH_UNCLAIMED` and prepares a successor. |
| `BLOCKED: ... TimeoutExpired` | the stderr line in the blocker | K1, preflight too slow: **STOP** and report the timings. |
| catalog shows `Prepared capsule readiness is unavailable` | app logs; time the status call (section 5.3) | Over 45 s: K1. Broker down: `$LOG`. Socket custody: `stat $SOCK`. |
| `ROOT_PIN_BYTES_DIFFER`, `ROOT_BROKER_SOURCE_DIFFERS` or `CAPSULE_INSTALLATION_CHANGED` in `$LOG` | which pin | Something under `$ADM`, the template or `$ROOTCFG` changed after start. Restore nothing by hand: new TAG. |

### 8.2 Run phases

| symptom | read | meaning and next step |
|---|---|---|
| Click refused, no `claim.json` | app log, broker `$LOG` | No effect happened. `Exact current native development assertion required` means the click waited more than 30 s behind a status call (K1). The slot stays READY; the human may click again. |
| `claim.json` without `owner.json` | journal | `LAUNCH_FAILED_BEFORE_START`. The monitor retires it. No effects. |
| Worker exit ≠ 0 and `controller-terminal` result with phase `WAITING_FOR_EVALUATOR` or `COMPOSING` | `records/controller-failure.json`, `$EV/<run_id>/complete.json` | Startup failure with zero model calls. Published as `Failed` (`rsi_capsule_publication.py:845-868`). |
| `PARENT_CONTROL_FAILED_NO_MODEL_CALL` (`complete.json` `stop: PARENT_CONTROL_FAILED`) | parent rows in `capsule-result.json` | A public baseline case failed in the sandbox. Fix it in the environment or source for a **new** revision. The parent evidence is published. |
| `stop_reason: error` with `MODEL_START_AFTER_ROOT_GRANT_DEADLINE`, `NATIVE_CONTAINMENT_UNCERTAIN_NO_FURTHER_EFFECT` or relay errors | iteration `failure_ref`, relay `check` | Relay lost or uncertain. Partial publication. If unresolved: **STOP**. Never retry the call. |
| `stop_reason: budget` | `loop.stop_detail` | Normal: 10 calls, the grant's `max_executions` (benchmark jobs included), or out of prepared contracts. |
| `stop_reason: deadline` during a benchmark | `run-stdout.log`, `$EV/<run_id>/claims` count | The benchmark wall estimate was too low for this hardware. Report it; prepare a new revision with a larger `benchmark.per_job_s` or `benchmark.wall_s`. Never re-run the consumed one. |
| `publication-failure.json` with `ROOT_BENCHMARK_REPORT_ORIGINAL_DIFFERS`, `BENCHMARK_JOB_EVIDENCE_REQUIRED`, `BENCHMARK_SESSION_SOURCE_DIFFERS` or `BENCHMARK_OBJECTIVE_DIFFERS_FROM_GATES` | the report under `$EV/<run_id>/captures/<sha>.json` | A benchmark report does not join its Root originals. Evidence is retained; report it, never re-benchmark to repair publication. |
| `ROOT_EXECUTION_BUDGET_EXHAUSTED` | evaluator `failure.json` | The budget was hit inside an evaluation, so the run is Partial. The derived grant was too small for the trials actually used: report it. |
| `publication-failure.json` (launcher exit `PUBLICATION_FAILED_RECONCILE_FROM_RETAINED_EVIDENCE`) | its `message` (for example `ROOT_TERMINAL_EXECUTION_COUNT_DIFFERS`, `ROOT_SERVED_EVALUATIONS_DIFFER`, `PINNED_PROJECTION_LACKS_LOOP_LINEAGE`, `ROOT_PUBLIC_DIRECTORY_REQUIRED`) | Evidence is intact. Reconcile with a separately reviewed publication plan from the same evidence, as R2 was reconciled (`$L` and `docs/review/evidence-20261026/calculate-r2-interrupted-publication-plan.json`). Never re-run. |
| `Partial` run | `activity` row `unreported-jobs` | Root issued jobs the session never received (evaluator exit ≠ 0). Counts are reported, not invented. |
| `Failed` with `Worker exited N without a session result` | `run-exit.json`, `run-stdout.log` | A resultless worker (`publish_worker_terminal`). Model call count is unknown. Investigate before any new revision. |

---

## 9. Rollback

Rollback returns 5175 to `ba1920af` and leaves the new broker stopped. It
never deletes anything.

1. Make sure no slot is CLAIMED or LAUNCHED (status call). If a run is
   LAUNCHED, let it reach its terminal state first.
2. Stop the new broker (section 4.5: verified identity, one `SIGTERM`). Leave
   `$SOCK`. Before any later broker start, quarantine it the same way.
3. `docker stop <new-app>`. Do not remove it.
4. Restore the gateway configuration bytes:
   `cp --preserve=mode,ownership "$ADMIN/build/gateway-before-$TAG.json" "$GW.rollback" && mv "$GW.rollback" "$GW"`,
   then `sha256sum` equals the copy saved in 4.3. `ba1920af` checks the
   **old** `module_sha256`. With the new file it would refuse its capsule
   gateway at startup.
5. `docker start ba1920af53b5f30f87e38af2822cf2124219b606eb39d0d0cf7cb0e0d134280c`.
   **CHECK:** port 5175, 15 mounts and 8 volumes are as in `app-before.json`.
   The native WS snapshot loads.
6. Keep `$ADMIN`, `$ROOTCFG`, `$SLOTS`, `$NS`, `$CTL`, `$EV`, the journals,
   the cgroup branches, receipts and all containers. Old prefixes were never
   touched.
7. **Publication after a loop run (K3).** The `ba1920af` projection accepts
   only the fields `id target_id stage status blockers budget activity` on a
   run row, so a published `lineage` block makes its snapshot
   unavailable. The previous publication bytes are in
   `.capsule-history/<sha>.json`. Putting them back would rewrite published
   history, so it needs the user's explicit decision. This runbook does not do
   it.

---

## Known issues before deploy

* **M4-1: e2e benchmark gates on a noisy box.** With 3 pairs and batches
  100/4 the real benchmark of Codex's r2 Calculate candidate cleared Codex's
  frozen gates (gain ≥ 10%, CI upper ≤ 0.90, no workload > 5% slower) in one
  run and missed the CI gate in the next (gain 12.9%, CI [0.829, 0.913]; A/A
  CI [0.969, 1.055]). The e2e therefore sets its own gates (5% / 0.95 / 10%).
  Whether the production loop (11 pairs, 1000/20 batches, frozen gates) keeps
  latency-only candidates on the WSL host is measured only by the first real
  run; a run under load can miss the CI gate and record "objective not met".
* **M4-2: environment-specific failures in the full suite.** The
  cancellation/host-transport tests listed in the integration report fail on
  boxes without the host Codex transport / Linux custodian; they are
  unrelated to the loop.

**K1 (fixed): readiness latency against fixed timeouts.**

* **Was:** every status request ran a full preflight for every slot, in
  sequence, in the single-threaded accept loop. Each preflight walked the
  3,235-file closure twice, at 18.4 s per walk, against fixed 45/30/30 s
  bounds. Readiness could time out ("unavailable") and clicks could expire.
* **Closure proof.** The closure is walked once per installed package, during
  Root preparation. The result is persisted as a Root proof under
  `$RT/.ai4r-source-closure/`. The launcher, the runner and the doctor reuse
  it after re-verifying the pins: digest plus file inventory. A changed
  package invalidates it automatically.
* **Readiness.** Each slot has a background thread that keeps a cached
  readiness record. Status returns that record with `observed_unix_s` and
  `age_s`. A stale record is `BLOCKED READINESS_STALE`. The preflight
  semantics are unchanged.
* **Timeouts and click window.** All timeouts are configuration, with the old
  values as defaults. The click window is validated at Root receipt.
* Section 5.4 explains and verifies the fix. Tests:
  `test_slow_closure_preflight_never_blocks_readiness_and_package_change_invalidates_proof`
  and
  `test_closure_proof_is_walked_once_per_package_and_a_changed_package_invalidates_it`.
* **Residual:**
  * Policy v1 (legacy strict, schema `ai4r-cc-rsi-capsule-status:1`) keeps
    its inline status rows.
  * A click's own start still runs the full preflight under the slot lock. It
    now takes seconds instead of a full walk.

**K2 (fixed): `composition_path` must lie under `source_root`.**
`validate_template` refuses
`COMPOSITION_OUTSIDE_SOURCE_ROOT: <path> is not under <source_root>`
(`rsi_capsule_slot.py:124`). The refusal comes at template load and at every
revision preparation, before any directory or step exists. The doctor step and
the worker mount only `source_root`. This runbook puts the composition at
`$RT/deploy/m1/rsi_development_run.py`, which passes.

**K3: Rollback forward compatibility.** The pre-branch projection in
`ba1920af` validates run rows with an exact field set. The new publisher adds
`lineage` (`cc_rsi_projection.py:358-361` new, versus the old exact
`_fields(row, "id target_id stage status blockers budget activity")`). After
the first loop publication, rolling back the app shows the snapshot as
unavailable (section 9, step 7).

**K4 (fixed): interrupted or overdue preparation steps are proven stopped.**

* **Recorded before start.** `ContainerSteps` writes each step container's
  id, name, start time and timeout to `<step>-container.json` before starting
  it (`rsi_capsule_slot.py:393`).
* **Overdue step.** It is stopped by that id (`docker stop`, then `kill`) and
  waited for. Only then is `<step>-exit.json` written and
  `STEP_DEADLINE_EXPIRED_STOPPED_NO_REPLAY` raised. If termination cannot be
  proven, it raises `STEP_TERMINATION_UNPROVEN_RECONCILE_NO_REPLAY` and
  writes no exit record.
* **Before any successor.** Before a successor of an interrupted
  (`preparing`) or failed revision is started, the broker calls
  `ContainerSteps.reconcile` (`rsi_capsule_slot.py:469`,
  `rsi_capsule_broker.py:237`, `cc_rsi_capsule.py:645`, `:651`).
  `reconcile` finds each claimed step's container by recorded id or fixed
  name:
  * inside its own deadline: the slot stays PREPARING ("waiting for an
    interrupted preparation step") and the broker waits;
  * overdue: it is stopped and waited for;
  * once stopped: its terminal state is adopted into `<step>-exit.json`
    (`adopted: AFTER_INTERRUPTION`, or `STEP_CONTAINER_ABSENT`).
* The ledger records stay append-only and nothing is re-run. The section 8.1
  `rsidocker ps` check is now a cross-check, not the only guard.

---

## Appendix: verification observed while writing this runbook (review box)

Branch `rsi-loop` at `31399b8`, run as Root with UID/GID 12003 present. The
same counts were reproduced in a minimal venv (`pytest pytest-asyncio
jsonschema cryptography pyyaml typing_extensions`, world-traversable path):
91 passed for scripts, and 102 passed for all `research_rsi/test_capsule_*.py`
including the gate (11 min 45 s).

| suite | result |
|---|---|
| `tests/unit_tests/scripts/test_rsi_capsule_launcher.py`, `test_cc_rsi_capsule.py`, `test_rsi_capsule_publication.py`, `test_cc_rsi_projection.py` | **91 passed** (91 s) |
| `tests/unit_tests/research_rsi/test_capsule_*.py` except `e2e_local` (dispatch_e2e, doctor, executor, loop, objective, prepare, public_targets, run, runtime, session) | **100 passed** (6 min 10 s) |
| `tests/unit_tests/research_rsi/test_capsule_loop_e2e_local.py` (gate) | **2 passed** (5 min 7 s) |
| frontend `npm run test:cc-rsi` | **17 passed**; `tsc --noEmit` exit 0 |
| venv under a 0700 directory (negative control) | 3 traversal tests fail with `PermissionError` on `venv/bin/python`; 27 runtime fixtures error without `typing_extensions` |

Other observations:

* The real parent, evaluated in process over all fixture sets, passed
  Calculate **11/19**. The failures are `max-tie-trailing-zeros`,
  `exponent-equivalents`, `signed-zero-json`, `large-decimal-ties`, `h01`,
  `h02`, `h06` and `h07`. Table Normalize passed **19/19**.
* Derived values:
  * `max_executions` 342 for both capsules
  * run deadline 4020 s
  * loop `parent_trials` 3, `max_model_calls` 10
  * policy v2 with two durable slots validates; run id r1 is
    `<slot_id>-r1`
* Source closure on a `git archive` staging of `jiuwenswarm/` plus runner and
  frozen composition:
  * `complete: true`, 3,235 files, 1,101 modules, 53 resources
  * **18.4 s** per derivation (K1)
  * frozen composition sha `5ba11903...`, as the runner pins it
