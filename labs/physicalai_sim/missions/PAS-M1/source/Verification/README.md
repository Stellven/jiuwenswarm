# SIMLAB verification route

Use the required proof table in [Architecture Main](../Architecture_main_body/Architecture_main_body.md), then the [benchmark and test plan](benchmark-and-test-plan.md) for test benches, SIMLAB's own benchmark families, official external benchmarks, what to test in each phase, and the phase and final reports.

Test the positive path and the failures: malformed experiments, missing dependencies, numerical failure, physical divergence, failed known-answer checks, model timeouts and bad answers, exceeded budgets, crashes, cancellation and restart. Preserve exact inputs, commands, expected and observed behavior, and evidence. Fixture checks do not prove a real model's behavior. BLOCKED and NOT_RUN are not PASS; a correct halt does not replace positive completion. Report runtime evidence separately from documentation checks.
