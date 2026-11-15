# Factory cohesive CPU analysis

Use `factory.cc_workflow_lab` when inspecting CPU CC invocation overhead or
combining several related receipt analyses. This skill does not authorize any
effect beyond the caller's existing grants.

1. Prepare once after selecting the implementation. Retain the release digest.
2. Supply compact receipt rows with stable package/call identity, elapsed_s,
   state and completeness. Keep failed rows. Never substitute GPU timings.
3. Use `run_batch` for 1..16 related independent analyses. Allowed operation names
   are exactly analyze_receipts, design_workflow and benchmark_fixture. Nested
   batches, arbitrary calls, paths and commands are unsupported.
4. Reuse the sealed release for fresh keys while the selected implementation
   remains appropriate. Reusing a key replays evidence; it does not measure work.
5. Read the raw repetitions and memory scope before comparing medians. Cost
   estimates from design_workflow are arithmetic assumptions, not measurements.
6. Run the attached negative checks before accepting results. Report CPU-only
   conclusions and preserve the original benchmark's contract and authority.

See EXAMPLES.json for complete capability inputs. The fixture benchmark is finite
and package-contained. Host benchmarking is an explicit developer exercise;
`benchmark_fixture` cannot invoke it.
