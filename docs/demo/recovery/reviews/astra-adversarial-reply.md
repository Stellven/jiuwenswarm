1. **Should-fix — unsupported claims about scripts.**  
   **Quoted text:** `ATTACK QUESTIONS.md`: “It can't decide that two patches must be present but off, notice a missing baseline receipt and stop, or revert in dependency order when a gate is null.” Console, Lessons: “a patch list either omits the hook (fill cannot run) or enables everything (no attribution).”  
   **Contradicting evidence:** `context/methodology_ab/AB.md` explicitly specifies implementable rules: “both require build admission,” “keep its commit with the switch OFF in every later arm,” and “revert both in reverse order.” These rules do not establish limitations of scripts; a script can encode them. `ENGINEERING-DETAILS.md` repeats the false dichotomy rather than demonstrating it.  
   **Replacement:** “The CC packages dependency, admission, switch and rollback rules that a bare patch list does not express. A script could encode these rules too.”

2. **Should-fix — unsupported necessity claim about raw Codex.**  
   **Quoted text:** `ATTACK QUESTIONS.md`: “it would have to rediscover the source map, the hook site and the measurement pitfalls … each time.”  
   **Evidence limitation:** `context/expert_streaming/STREAMING.md` says “Guidance is read by the agent; it does not itself execute patches.” This supports supplying reusable knowledge, not the claim that another agent must rediscover it every time. The permitted evidence contains no comparative raw-Codex trial.  
   **Replacement:** “The CC supplies versioned source maps and measurement guidance explicitly. We have not tested how raw Codex would perform with equivalent context.”

3. **Should-fix — ontology propagation is overstated.**  
   **Quoted text:** Console, Layers: “copies it, with the contract reference, onto seeded work nodes and plan edits.” `ATTACK QUESTIONS.md`: “attaches it, with the contract reference, to every seeded or edited work node.”  
   **Contradicting source:** `ONTOLOGY.md`: “initial_plan … copies it onto every seeded work node”; for edits, “plan_patch add and update operations validate any engine_slice they carry.” Validation of a supplied field is not automatic attachment to every edited node.  
   **Replacement:** “Seeding attaches the slice and contract reference to work nodes. Plan edits validate any slice they supply; the guidance tells the agent to preserve the target.”

4. **Should-fix — stock paging is presented as strictly serial, page-by-page I/O.**  
   **Quoted text:** Console, Engine: “The matmul thread page-faults on each missing page, one at a time.” `PRESENTATION.md`: “the matmul thread stalls on each missing page, one at a time.”  
   **Contradicting source:** `context/expert_streaming/SOURCE-MAP.md` describes faults serviced by “the touching compute thread” with “POSIX_FADV_SEQUENTIAL/default readahead unless advice changed.” Synchronous faults on a touching thread do not imply globally serialized, single-page storage reads.  
   **Replacement:** “Stock CPU matmul can stall when a touching compute thread faults on nonresident weight pages. Demand fill explicitly batches missing ranges into parallel reads before matmul.”

5. **Should-fix — historical output equality is upgraded to reference validation.**  
   **Quoted text:** Console, Result: “byte-identical to the reference in all 12 runs.”  
   **Evidence limitation:** `evidence/J-OM13/REPORT.md` reports “Output class: identical” and matching hashes across all three arms. `evidence/J-OM13/spec.json` supplies no frozen-reference hash. These establish agreement among runs, not independently documented agreement with a frozen reference. The fresh task’s reference is separate.  
   **Replacement:** “The fixed workload’s greedy output was byte-identical across all 12 runs; this is not a general model-accuracy claim.”

6. **Nit — throughput percentages are ambiguous in the spoken script.**  
   **Quoted text:** `PRESENTATION.md`: “The first comparison was 7.7% faster” and “A longer confirmation the operator authorised was 12% faster.”  
   **Source qualification:** `context/methodology_ab/AB.md`: “For ms/token ratio is A/B” and “Improvement requires ratio - 1 strictly above threshold.” `evidence/incremental/decisions.json`, revision 11, records “ratio A/B 1.119938205140209.” These are throughput-equivalent increases; the corresponding time reductions are approximately 7.11% and 10.71%.  
   **Replacement:** “Observed throughput was 7.7% higher … The confirmation observed 12% higher throughput.” Keep the null-gate qualification.

7. **Nit — whole-model file size is attributed to expert weights alone.**  
   **Quoted text:** `ATTACK QUESTIONS.md`: “The expert weights (22.4 GB) far exceed memory.”  
   **Contradicting source:** `context/expert_streaming/SOURCE-MAP.md` identifies a “20.8 GiB file” and separately describes expert tensors and non-expert tensors in that file. The file size is not an expert-only byte count.  
   **Replacement:** “The model file is 22.4 GB, far larger than the machine’s 7.4 GiB shared memory; the applicability check also confirms expert bytes exceed RAM.”

Overall verdict: No blocker found; fix the attribution and technical overclaims above before presenting.