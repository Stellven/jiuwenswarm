You are an adversarial reviewer (advisor only; do not edit anything). Working directory is an extracted demo package for a ten-minute talk.

Bounded question: Do the audience-facing claims overstate, misattribute or mix evidence? Check ONLY these files:
- "20261113 Satay CC Demo Console prepresentation.html" (the console; all visible text)
- PRESENTATION.md (speaker script), "ATTACK QUESTIONS.md"

against this evidence:
- evidence/J-OM13/REPORT.md and evidence/J-OM13/spec.json (historical 64-token headline)
- evidence/incremental/results.json and evidence/incremental/decisions.json (fresh 32-token task, 11 decision revisions)
- context/engineering/ENGINEERING-DETAILS.md, ONTOLOGY.md, context/expert_streaming/SOURCE-MAP.md, context/expert_streaming/STREAMING.md, context/methodology_ab/AB.md

Specific risks to probe:
1. Any number that does not match its source, or a percentage applied to the wrong quantity (time vs throughput).
2. Anything implying the fresh recording produced the J-OM13 headline, or crediting the 13-Nov ontology slice link to historical runs.
3. Overstated CC contribution (e.g. claiming the capsule chose "fill first" when the operator objective also prescribed it), autonomy, generality, accuracy, or superiority over raw Codex.
4. The engine explanation: is anything technically wrong about CPU expert execution under -cmoe, mmap pages, the callback before expert matmul, or demand fill blocking? Any implication of moving experts to GPU?
5. The two engineering details: are they supported by the cited sources?

Output: a numbered list of findings, each with severity (blocker / should-fix / nit), the exact quoted text, the contradicting source with path and quote, and a suggested replacement. If a claim is fine, do not list it. Max 15 findings. End with one line: overall verdict.
