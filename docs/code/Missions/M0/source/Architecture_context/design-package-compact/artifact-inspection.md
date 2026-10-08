# Artifact inspection and evidence

**Reading level: human potential.** Question: how can a person understand what the system interpreted, checked and delivered without decoding storage objects?

## Substantive artifacts first

Persist and export descriptive, formatted files: `Intent_IR.json`, `Research_Brief.json`, `Intent_Assessment.json`, `Requirements_Assessment.json`, `Gate_Decision.json`, and the PRD research filenames. Identity-bearing directories may organize runs, but inspection must not require mapping anonymous `.bin` objects to their meaning. Internal content-addressed storage remains possible if the inspection/export boundary projects readable named artifacts without changing their bytes/meaning.

## Ownership and flow

## Manifest principles

A manifest names run identity, artifact role/type, schema/version, descriptive path/media type, exact hash, producing invocation, acceptance/decision reference, audience and redactions or missing evidence. Distinguish payload, runner-owned envelope and protected release record. Bind observations to contract, inputs, implementation/dependency pins and effective configuration. [Major field contracts](reference/other-contracts.md#manifest-and-runtime-records) define these connections.

## Lifecycle and failure meaning

Users can inspect saved Brief, ideas/citations, opportunity/reasons, hypothesis/test plan, measurements, scientific verdict and report. Viewing a historical run is read-only and never starts another experiment. An in-progress export states its stage/status and which artifacts have not yet been produced; it is not a completed result. A failed run retains the candidate, checking results, halt reason and available evidence. If storage fails, show the operational error without claiming that missing evidence was saved.
