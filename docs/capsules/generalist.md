# Generalist M1 candidate

`research.generalist` is a low-trust fallback for a bounded task with no selected
specialist. It uses the existing audited model connection, reads only its
supplied work packet, and returns generated data and UTF-8 file artifacts. Its
stable declaration describes this envelope rather than promising every possible
task. It gets one model call and one dispatch attempt; failures are retained and
there is no hidden retry or nested capsule dispatch.

The host freezes the Planner's objective, obligation IDs, parent/policy identity
and attempt in the ordinary execution contract before work. It copies that task
contract into the output and independently checks exact equality before review.
The semantic reviewer sees the declaration and exact output, including this
host-checked task projection. A mandatory fixed criterion assesses task alignment
and disclosed limitations. The Planner supplies the intended outcome, not judge
code, a model, verdicts, waived checks or new permissions. No original input,
worker conversation or hidden benchmark cases are added to reviewer context.

This is an explicit October 23 M1 amendment to the earlier Generalist deferral
and D20/D24's prohibition on task criteria hidden in output. The task projection
is named and authenticated by host checks; it is not represented as unchanged
compliance with that older restriction. Specialized capsules retain their
existing declaration/output review boundary. Required missing, failed or
indeterminate checks still block advancement.

## Bounded code and files

The model can author code files as artifacts. Such files are **not executed**.
For actual computation it may request one expression in a deliberately small
Python-syntax JSON language. The checked interpreter supports data/file lookup,
numeric arithmetic, comparisons, conditional expressions, literals and fixed
pure functions. It never uses Python `eval`/`exec`, imports, subprocesses,
attributes, package installation, comprehensions or loops. AST/depth/value/step
and time limits apply. Host evaluation and independent recomputation bind the
reported result to the exact original input. Refusal fails the task.

This gives useful bounded code execution without weakening the existing
scientific executor, which only admits its own scientific jobs. Arbitrary
Python/OS execution and interactive multi-turn agent tools require a separately
designed executor profile and are outside this release. No host credentials,
network, external integration or user filesystem is granted to the capsule.

Packet file paths are normalized relative artifact names. Contents and SHA-256
digests remain inside the durable `result.json` output; they are not written to
ambient user folders. Consumers can inspect/download that artifact normally.

Every output is marked `trust: low`, carries the original input provenance and
contract identity, and records a capability gap and limitations. Utilities must
preserve this taint. Passing a task does not certify a specialist or establish
scientific truth. The Planner prefers specialists, with a protected maximum of
two Generalist nodes; semantic specialist matching is a planning instruction,
not a claimed mechanically proven search of every possible specialist.

Merge after [the foundation](capability-dag.md), then qualify, admit and activate
the candidate through that guide's normal M1 process. Merge alone grants nothing.
Local tests use explicit model fixtures; real model, Docker and Spark execution
remain separate connected checks.
