# 20261116 Reusing Factory Experiments prepresentation

A missed performance gate does not invalidate an experiment or discard its source. Scientific acceptance, source availability and authority to execute are separate facts. The experiment library indexes retained observations, attempts, decisions and verified text artifacts without filtering out target_not_met or inconclusive results. Changed snapshots remain available.

## Available starting points

| Candidate | Cloud branch in Muxite/Strata | Measured commit | Three-prompt screen |
| --- | --- | --- | --- |
| ARM64 1 ms idle policy | factory/review-20261116-arm64-idle | f5075a168adcdcf4289d45165bfbad00584e9eba | 14.456 to 15.655 tokens/s, +8.30% |
| Idle policy plus ARM64 hardware hint | factory/review-20261116-arm64-yield | 84864456256b0e8fb4d933b7dcb67550daafaf85 | 14.473 to 15.817 tokens/s, +9.28% |

Both screens passed exact canonical outputs/finish on the three fixed prompts, placement and per-case regression checks. Both missed the frozen 10% gate and received no ABBA confirmation. Their reuse_status is available_for_optional_followup; performance_status remains target_not_met. A later session can choose either codebase if relevant, or choose something else. Neither result is an automatically promoted engine or a general accuracy claim.

The earlier factory/fixed-placement branch retains commit 231b10b9780c8fb678d130a5d23676660e798add and its narrower historical qualification. The two review branches are separate experimental lineages. Original baseline: 89ae0ee6123597636ef162dec826230186c00f3b.

## Discover, inspect and reuse

1. Search the native experiment library for reusable-strata-f5075a16 or reusable-strata-84864456. Read the returned snapshot with experiment_read. It contains the source repository, branch, exact commit, build/image identities, comparison, limitations and patch artifact ID.
2. Read the referenced patch snapshot. The library verifies its source-store digest and retains its complete bounded text. Source commits are preserved by named branches in the owned Spark checkout and on GitHub.
3. Fetch the selected branch from https://github.com/Muxite/Strata.git and verify its commit before creating a new task-owned checkout. Do not edit a prior task's checkout or rewrite its evidence.
4. Admit a fresh task using the chosen commit as an explicit starting point. Keep the declared comparator, workload, accuracy policy and resource limits appropriate to the new question. Reuse does not inherit old grants, reset a budget or authorize promotion.

The shared Spark source inventory is /home/user2/software-factory-spark-20261113/experiment-library/sources.json. It lists the 18 admitted history stores, including both current review phases. Use it as a configuration template for a new task's resources.experiment_library; per-task source admission remains explicit. A fresh library reader was verified to retrieve both real candidate records and their complete patches after the producing session finished.

For cloud readers without the live Spark database, experiments/20261116-strata-candidates.json and experiments/patches/ in this directory provide the portable candidate records and patches. The qualification record retains the complete decision and measurement summary. Mutable SQLite stores, credentials and model weights are kept off Git.

Regression coverage: tests/factory/test_reusable_candidate_history.py verifies that a rejected candidate's source locator, verdict, optional reuse status and verified patch survive store closure and a fresh library reader. This supplements the existing scope and immutable-snapshot tests.
