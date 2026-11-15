# Evidence and implementation references

- COMPONENTS.json identifies the integrated native prefill and verified drafting
  mechanisms, pinned source revision, source-map symbols and verification obligations.
  These mechanisms already exist; the package implements candidate configuration
  transforms, not a new kernel or an established performance improvement.
- SCOPES.json maps configuration, replay, subsystem, integration and recovery claims
  to different evidence obligations. VERIFICATION-UNITS.json lists development checks;
  passing them does not certify engine quality, GPU engagement or package-wide admission.
- MoE-Infinity: https://arxiv.org/abs/2401.14361 — routing/access history motivates
  retention and prefetch hypotheses. Offline temporal holdout and causal baselines in
  evaluate_prediction test a bounded prediction question, not the paper's whole system.
- Fiddler: https://arxiv.org/abs/2402.07033 — weight movement versus CPU execution is
  an applicability question on shared-memory GB10; measure local costs rather than
  importing a PCIe model. There is no automatic placement component here.
- Native Strata DS4_PROF and Nsight traces are observer evidence. Inspect retained
  failures and perturbation before requesting another admitted observer run. Missing
  counters require instrumentation work, not an assumption of zero cost.

Paper links are provenance and ideas, not fetched or verified citations. Pin source
bytes/revisions and check applicability before implementation admission. Read METHOD.md
for the claim boundaries shared by all tools in this job package.
