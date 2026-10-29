# Outcome X2: screen candidate research ideas against a brief and a rubric
Given a research brief with constraints, a list of candidate ideas (each with citations), and a scoring rubric, remove the ideas that violate a constraint, score and rank the rest, and say why for each idea. Do not drop an idea for missing optional information. Keep each idea's identity and citations unchanged.
Example input (short): brief "CPU only, no new dependencies"; ideas A (uses numpy, cites [1]), B (pure Python, cites [2]), C (needs a GPU, cites [3]); rubric: novelty 0-5, feasibility 0-5.
Example output (short): C rejected (GPU); B ranked above A if scores say so; reasons listed.
