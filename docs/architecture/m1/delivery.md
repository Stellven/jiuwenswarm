---
type: design
status: draft
version: 3
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.write_report, publication.publish_report]
consumes: [cc.type.benchmark_payload, cc.type.hypothesis_blueprint, cc.type.research_brief]
depends_on: [pipeline.md, research-gates.md, measurement-protocol.md]
tags: [m1, contract]
---

# Report generation and ordinary publication

The report capsule `research.write_report` owns PRD 3.9 synthesis. An ordinary publisher owns mechanical file delivery. The split separates generated conclusions from trusted filesystem effects and adds no mechanical capsule or semantic judge.

| Boundary | Contract |
|---|---|
| report inputs | admitted evaluation_verdict, benchmark_payload, research_brief, idea_set, opportunity_card, hypothesis_blueprint; supervisor-bound StageContext |
| report output | canonical research_report; static pinned markdown template |
| report Gate | shared research.verifier; research.accept_report.v1 profile |
| publication call | publish_report(research_report_ref, poc_bundle_ref, benchmark_payload_ref, stage_context_ref, destination_ref, request_id) -> publication_manifest_ref |
| publication effect | idempotent_effect, only authorized outputs/<run_id>/ directory |
| publication validation | publication.manifest.v1 deterministic profile; zero semantic criteria |

Publication starts only after durable report Verification and release. It resolves stored inputs, writes a sibling staging directory, verifies every byte and manifest entry, then publishes atomically/recoverably under the store protocol. The supervisor persists completion only after publication evidence. Duplicates reuse the same committed manifest; changed bytes under a request ID return REQUEST_CONFLICT. Crashes retain a recoverable staging record and never expose an incomplete directory as completed.

INPUT_MISSING, REFERENCE_INVALID, OUTPUT_INVALID, DESTINATION_DENIED, PUBLICATION_FAILED and STORE_WRITE_FAILED retain evidence and halt final completion. Timeout/cancellation use the shared request lifecycle and cannot silently issue a new effect. The publisher is the sole output-directory writer; Data Foundation owns Artifact/manifest records. Native views read the committed manifest and display paths; they never mutate conclusions or trigger external messages.

Independent hooks render_report with fixture evidence and publish_report with a temporary destination. Verify scientific FAIL preservation, missing sections, stale numbers/citations, limitation retention, duplicate publication, destination denial and interrupted publication. This uses manifest publication with atomic replacement, following [Python os.replace](https://docs.python.org/3/library/os.html#os.replace); platform crash durability requires implementation validation.

## Template and complete inputs

The [verbatim upstream source](../../product/report-writer-upstream-2026-10-01.md) is retained under product inputs. Its installation/output-format instructions are source material; the M1 adaptation below governs the product.

Source verified: OpenJiuwen sciencediscovery commit `cee1974d463136aa611234e3f8a915a7dc57ae88`, `skills/report-writer/SKILL.md`, Default Report Template and Phases 2–4. Pin the adapted static template as a body file of research.write_report. Required section order: 1. Executive Summary; 2. Knowledge Research Findings; 3. Data Analysis Findings; 4. Cross-Domain Insights; 5. Contradictions (Unresolved); 6. Limitations & Gaps; 7. Recommendations; Verdict. Methodology and benchmark analysis go in Data Analysis Findings. Preserve unresolved contradictions. Empty/not-applicable sections remain visible. Source-template completeness labels COMPLETE/PARTIAL/FAILED are separate from the four scientific labels and Gate verdicts. M1 uses this fixed format even when upstream permits customization; no upstream package installation instructions or /mnt output path carry into the product.

Report inputs additionally include idea_set, opportunity_card and hypothesis_blueprint as recorded plan wires. A trusted `get_stage_context(run_id, through_step)` API in `cc/evidence.py` returns closed StageContext `{artifact_refs, observation_refs, verification_refs}`, scoped to completed steps of the caller's run; it does not provide hidden fixtures, credentials or arbitrary file access. The report uses these refs to enumerate earlier non-blocking issues and Gate limitations. This context is supervisor-supplied evidence, never a model-selected scope. Every citation must resolve to an idea_set source and retained excerpt; each number must match the admitted benchmark. No new research is performed.

Publisher inputs are research_report, poc_bundle and benchmark_payload plus the same authorized evidence context. Publish outputs/<run_id>/ as one recoverable manifest-backed directory containing research_report.md, POC_Artifact_Bundle.zip, empirical_results.json, raw stdout/stderr and an evidence index pointing to preserved blueprints/Gate decisions. Extract only validated four-role POC files. No partial directory is presented as completed. Duplicate identical requests return that publication; changed bytes conflict. Verify stored bytes, then expose them through native Web/TUI and /swarmflows. Do not send external notifications or alter scientific conclusions.
