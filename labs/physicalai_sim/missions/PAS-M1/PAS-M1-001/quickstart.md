# Quickstart validation guide: PAS-M1-001 - Base simulator
Run guide for the phase 1 validation scenarios. Exact verification procedures and expected results are owned by [plan.md](plan.md) "Verification Design"; this page only shows the sequence. Commands become valid as the blocks are implemented (tasks.md).

## Prerequisites
- WSL2 on the laptop, Docker reachable, `uv`, and the `PhysicalAI-Sim` checkout at `~/jiuwenswarm`.
- `export SIMLAB_DATA_DIR=~/simlab-data` (outside the repository).
- For X1.1 only: the AI4R app images build from this checkout, and the owner completes the one-time model sign-in at the bootstrap URL that AI4R prints.
- Stop the AI4R app before check groups (memory: research.md R12).

## Sequence
1. Build: `cd ~/jiuwenswarm/labs/physicalai_sim && docker build -f docker/Dockerfile -t simlab-runner:dev .`
2. Health: `docker compose -f docker/compose.yaml up -d simlab-runner`, then `docker exec simlab-runner simlab doctor --json`.
3. Local feasibility (X1.1): `python tools/feasibility.py --output ~/.../feasibility-<run>` (starts AI4R through `deploy/m1/ai4r.py`, waits for sign-in, runs the simulator process, samples resources).
4. Tool path (X1.4 rehearsal): `docker exec simlab-runner simlab draft-create ...`, then the authoring commands, `bind`, `validate`, `submit`, `status`, `result`, `query`, `fetch`.
5. Check groups (X1.2, X1.3, X1.5): `python tools/check_groups.py --group all --output ../../.test_logs/simlab/all/<run>` (runs inside the image with no network, a 4 GB cap and read-only sources).
6. Benchmarks (F1, F5): `docker exec simlab-runner simlab bench run --family F1 --profile campaign`, with reports in `benchmarks/reports/<date>/`.
7. Agent-only (X1.4, opt-in live): `python tools/agent_only.py` (headless agent restricted to the SIMLAB MCP tools).
8. Fresh checkout (X1.6): `python tools/fresh_checkout.py --commit <recorded commit>` (needs an owner commit; before that, a rehearsal only).
9. Compute log: `simlab compute-log append --from <run record>` for every run.

## Expected outcomes
See spec.md AC-001 to AC-022 and plan.md V IDs. A skipped, blocked or not-run check is not a pass.
