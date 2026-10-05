---
type: review
status: draft
tags: [review, draft, prd, m1, reply]
---

> **Draft, not yet sent.** Reply to Ramika's full M1 PRD post. Evidence: [full review](prd-m1-full-review.md#following-the-prd-as-written).

Hi Ramika, architecture side. We can build to the PRD as written. A few readings to confirm, plus our answers to your open questions.

**Please confirm**
1. **Isolation:** the installer runs `sudo` once to create `jiuwen-runner` (5.2.1, 6.3). Untrusted code, including RSI children in the oracle, runs as that user, and the fixture folder stays the user's only. The no-root rule in 4.4.9 applies to the oracle only. OK?
2. **Thresholds:** the Brief's metrics (3.2.6) reach 3.7 through the blueprint, which freezes them as success targets and adds the falsification threshold. The 3.5 gate checks that nothing is weaker than the Brief.
3. **3.6 and 3.7 run on the CC runner** (4.1.4, "every capsule call"). The 5.4.3 privilege drop applies to the process that runs generated code.

**Your open decisions**
- **Dependencies: both.** 3.7 runs `pip install` in its venv, but only from a local pre-provisioned wheelhouse, with no network. The 3.6 gate dry-runs the same install, so a missing package fails 3.6 and does not block 3.7.
- **Target vs threshold:** falsified = FAIL; claim met = PASS; a real effect short of the claim = CONDITIONALLY_ACCEPTABLE; evidence missing or anomalous = INCONCLUSIVE. Code computes the tag (3.8.4). The blueprint declares units and the repeat count.
- **Architecture side:** the exact gate JSON, field names, paths and IPC. We keep every 4.2.8 field.
