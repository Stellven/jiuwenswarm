# Provenance

| Item | Revision |
|---|---|
| AI4R base | `Stellven/jiuwenswarm` branch `AI4Research-Main` at `141c1c401138f916af0a41aca791adf226d814c7` (2026-11-02, "Merge pull request #13 from Stellven/codex/rsi-console"), fetched 2026-11-05 and verified against the stated revision |
| New branch | `ai4r_ccv2`, created from that commit as a separate git worktree; no other branch or checkout was modified |
| CC protocol and reference code | `Muxite/tools` `main` at `89893083ebbcb3b54f5672df720e3afc37a8df7e`, from `AI4Research-Notebook/Designs/CC Protocols` (local copy `research/tools-transfer-20261104`) |
| Codex runtime | `openai-codex-cli-bin==0.163.0` (the version the transport pins) |
| Pinned base image | `docker.io/library/python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30` (`python:3.12-slim`) |
| Built image | `cc-demo/compute:1`, id `sha256:ec5b1df28d09604bf8895fbd83a423165d4970c90a7fed72a57e3bd5142f6551` |

The vendored runner is copied from the reference code, then changed as listed in `PROTOCOL-CHANGES.md`.

The runner fixes in `PROTOCOL-CHANGES.md` rows 1 and 2 (`stdin=DEVNULL` on helper children, `--pull=never` on finite image calls) were also applied to the reference copy as local commit `ea057c1` on branch `ccv2-runner-fixes` in `Muxite/tools`. The branch is pushed to `Muxite/tools` as `ccv2-runner-fixes` (based on `main` `89893083`, not merged).
