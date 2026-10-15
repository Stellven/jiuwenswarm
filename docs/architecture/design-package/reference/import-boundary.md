# Import boundary

`Tier 3 · Part of: [Reference](README.md)`

This page owns the import rule that keeps the hot path independent of every side system. The rule proves `NB-11`, `RTR-4` and `RSI-1` in the build criteria. It follows from [D31](../method/decisions.md#d31), [D36](../method/decisions.md#d36) and [D44](../method/decisions.md#d44).

**Find:** [package groups](#package-groups) · [the one router client module](#the-one-router-client-module) · [lint config](#lint-config) · [how it is proved](#how-it-is-proved)

## Package groups

The names below are the logical package names this design uses. The code team may choose other names. If it does, it updates the lint config and keeps this table in step with the code.

**Hot path.** These packages hold code a research run cannot work without.

| Package | Holds |
|---|---|
| `ai4r.api` | Control API, web server, session token check |
| `ai4r.runtime` | Intake, binder, freeze, scheduler, check runner, gate host, admission, evidence builder |
| `ai4r.bridge` | Model bridge, `RouterPort`, `CodexRouter`, the router IPC client module |
| `ai4r.executor` | Launcher of the confined executor and the Builder tool-use sandbox |
| `ai4r.state` | SQLite state, artifact store, the hot-path writers of the `records/` folder |
| `ai4r.capsules` | The code of every CC |

**Forbidden for the hot path.** No hot-path module may import any of these.

| Package | Holds | Why |
|---|---|---|
| `ai4r_router` | The API router implementation. It runs as its own process | The router is a separate process, so the hot path needs none of its code ([D44](../method/decisions.md#d44)) |
| `ai4r_rsi` | The RSI workbench | Off the hot path ([D31](../method/decisions.md#d31)) |
| `ai4r_sidecar` | Job coordinator, benchmark and test runners, host launcher helpers | Off the hot path ([D36](../method/decisions.md#d36), [D51](../method/decisions.md#d51)) |
| `ai4r_record_builders` | The conformance, scorecard and sample export builders | A derived record never blocks a run and no gate reads one ([derived records](derived-records.md#release-rule)) |

## The one router client module

`ai4r.bridge.router_client` is the only module that talks to the router. It is an IPC client. It opens the local socket, sends a route request, waits for the deadline that `RouterPort` sets and returns the reply or an error. It imports the standard library and the `RouterPort` types, and nothing from `ai4r_router`. With the router as a separate process no router code is imported at all. The linter still checks this module on its own, so a later change cannot slip a router import into it.

## Lint config

The config is import-linter contract text. The linter is the tool that proves the rule. It runs in CI and before each merge.

```ini
[importlinter]
root_packages =
    ai4r
    ai4r_router
    ai4r_rsi
    ai4r_sidecar
    ai4r_record_builders

[importlinter:contract:hot-path-no-side-systems]
name = Hot path imports no side system
type = forbidden
source_modules =
    ai4r.api
    ai4r.runtime
    ai4r.bridge
    ai4r.executor
    ai4r.state
    ai4r.capsules
forbidden_modules =
    ai4r_router
    ai4r_rsi
    ai4r_sidecar
    ai4r_record_builders

[importlinter:contract:router-client-is-ipc-only]
name = The router client module is an IPC client only
type = forbidden
source_modules =
    ai4r.bridge.router_client
forbidden_modules =
    ai4r_router
    ai4r_rsi
    ai4r_sidecar
    ai4r_record_builders
```

## How it is proved

The import linter runs on the current tree, then adds one forbidden import to a hot-path module and runs it again. The first run exits 0. The second exits nonzero and names the module and the import.
