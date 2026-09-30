# M1 PRD: kickoff messages and the Level 2 template

> **Copied verbatim** from Ramika's Discord posts, 2026-09-28 and 2026-09-29. The PRD owner is Ramika; the owner's version wins. These messages override the initial PRD on two points: the Verifier has five gate verdicts, and there are "6 core capsules (5 workflow + 1 verifier gate)". Section 3 of the M1 System PRD is in [prd-m1-section3.md](prd-m1-section3.md). The initial PRD is in `prd-m1-initial-2026-09-28.txt`.

## Initial PRD announcement

Hey @everyone 

This is the initial PRD that is almost finished = a quick overview - Updated once will be sent after I talk with all of you and we are all on the same page! 

Orchestration & Harness (jiuwenswarm fork): Native Swarmflow DAG, task memory, web workbench (localhost:5173), and human-in-the-loop (human_session).

Tools & Operators (deepsearch): Whitelisted operators for literature retrieval (DeepSearch) and codebase inspection (CodeSearch). Good starting point and we can build of based on what we find our own or adjust these.

Domain Intelligence (sciencediscovery): We are porting established research rubrics and prompts directly into our capsules rather than engineering prompts from scratch. Same idea as tools and operators, good starting point and we can build of based on what we find our own or adjust these.

De-risked Parallel Tracks: Complex dynamic features (Dynamic Planner, RSI loops, multi-model routing) are isolated on parallel tracks operating against sample fixtures so nobody is blocked by live pipeline stability.

plan is Ill meet with @Muxite first to talk about architecture and capsule design, then @Saurav for more details on benchmarking and RSI, and then finally @Xiaoyang Liu for the model routing + plan for coding this (also goal is to get everyone on the same page)

## Summary after meeting Stellven

Hi guys! Just met with Stellven and wanted to give a summary of the current state of the PRD:

all the features that are in the past-intern AI4Research will be implemented in M1 - feel free to reference the Test Report for the full list of features

what will new to M1:
-> The "Three-Repo" Stack: We are leveraging existing OpenJiuwen frameworks instead of building from scratch. We are using jiuwenswarm for the runtime/DAG, deepsearch for our tool operators, and sciencediscovery for our domain logic and grading rubrics.
-> Deterministic Pipeline at very brief start, then Dynamic Orchestration: M1 will have both a hardcoded, static Swarmflow DAG to have some fallback stability + Autonomous orchestration (the Dynamic Planner) which will be developed concurrently in an offline parallel track.
-> The Two-Tier Synchronous Evaluator Gate: Instead of end-of-pipe human review, we are injecting an automated Gate between every node handoff. It runs Tier 1 Python assertions (schema/budget checks) followed by a Tier 2 LLM semantic judge, halting execution on failure.
What each of our 4 models will have in M1 in terms of features:
-> Capability Capsule (@Muxite ):  Responsible for wrapping 6 core capsules (5 workflow + 1 verifier gate) into a standardized make_capsule.md contract. You will be porting existing rubrics from sciencediscovery directly into these capsules to enforce strict JSON input/output payloads.
-> RSI (@Saurav ):- Decoupled from the live pipeline. You will operate in an offline sandbox, running mutations directly against static make_capsule.md schemas and hidden test fixtures to prevent prompt overfitting, without needing to wait for a live DAG.
-> Model Routing (@Xiaoyang Liu ): Unblocked via a two-track approach. On the main branch, we are using a temporary Codex CLI adapter to run requests through an active subscription. Concurrently, you will develop the multi-model dynamic router on an isolated branch using simulated API endpoints until enterprise keys are provisioned.
-> Verifier (@Ramika ): Responsible for the physical Evaluator Gate logic. You will implement the 5 exact branch verdicts (PASS, PASS_WITH_KNOWN_LIMITATIONS, FAIL, ENVIRONMENT_BLOCKED, ESCALATE_TO_HUMAN) and lead the 3-phase benchmarking strategy to validate our platform against native OpenJiuwen.

part-time interns: 
hello! Stellven briefly introduced what you guys had in mind for your term:
-> @BigS (Suraj) - data foundation supporting capability capsule in RSI
-> @Electron1c (James) - model fine-tuning supporting LLM as a verifier in RSI 

I'd love to meet with you guys in person tomorrow or wednesday to get a better idea + give you some time to think on how to integrate your parts - lmk what times work for you best

## Level 2 template request

Hey @everyone, 

Following our green light from Stellven, we need to translate our M1 strategy into a strict Level 2 engineering contract. This will define our exact boundaries so we avoid scope creep and have a clean document to feed into Codex on Friday.

I have broken down the baseline features for each of your modules using a Whitelist / Blacklist / Dependencies hierarchy. I need each of you to fill out your respective sections.

The Ground Rules for filling this out:

Baseline Parity: You must address the sub-features listed in your template (they carry over from the legacy architecture). - Anything about your model that was in the test report must be addressed in your PRD section of your model

The Blacklist is Crucial: Explicitly writing down what we are excluding from M1 is what protects our timeline. If an agent shouldn't do something, blacklist it. This doesn't mean that we won't implement it in the future, make sure you address everything but constraint to M1.

Explicit Dependencies: Name specific nodes and payloads (e.g., "Requires Research Brief JSON from Stage 1") rather than vague descriptions.

Additions Welcome: Add any new sub-features your M1-specific approach requires (e.g., offline test schemas, preset-based routing algorithms, or AI reviewer agents).

If you have any questions let me know - Please have your section done by Wednesday End of Work Day or latest Thursday 11AM. 

See thread for template for each of your sections:

for the part-time interns, I'd like to meet with you 1-on-1 today or tomorrow to figure out more what you're working on to get a better idea for what part of the PRD you should be responsible for. 

## The 3.W template (Capability Capsule)

### 3.W Capability Capsule

#### 3.W.1 Capability Capsule Definition & Assembly
*   **Definition & Expectation:** Define the capsule's contract, metadata, dependencies, resources, and executable entry points[cite: 8].
*   **Whitelist (M1 Scope):** [Fill in - e.g., standardizing `make_capsule.md` and wrapping the ported sciencediscovery logic]
*   **Blacklist (Excluded from M1):** [Fill in]
*   **Dependencies:** [Fill in]

#### 3.W.2 Capsule Governance, Certification & Registry Management
*   **Definition & Expectation:** Validate, certify, register, version, publish, suspend, deprecate, and audit capsules[cite: 8].
*   **Whitelist (M1 Scope):** [Fill in]
*   **Blacklist (Excluded from M1):** [Fill in]
*   **Dependencies:** [Fill in]

#### 3.W.3 Capability Discovery, Scoring & Selection
*   **Definition & Expectation:** Find and rank eligible capsules by compatibility, policy, quality, cost, and performance[cite: 8].
*   **Whitelist (M1 Scope):** [Fill in - Note: likely minimal for M1 since our DAG is deterministic/hardcoded]
*   **Blacklist (Excluded from M1):** [Fill in]
*   **Dependencies:** [Fill in]

#### 3.W.4 Capsule Invocation & Composition
*   **Definition & Expectation:** Execute capsules with governed inputs and compose compatible capsules into reusable capabilities[cite: 8].
*   **Whitelist (M1 Scope):** [Fill in]
*   **Blacklist (Excluded from M1):** [Fill in]
*   **Dependencies:** [Fill in]

#### 3.W.5 Capability Capsule Evolution & Version Promotion
*   **Definition & Expectation:** Improve capsules from runtime evidence, validate candidates, and promote or roll back versions[cite: 8].
*   **Whitelist (M1 Scope):** [Fill in]
*   **Blacklist (Excluded from M1):** [Fill in]
*   **Dependencies:** [Fill in]
