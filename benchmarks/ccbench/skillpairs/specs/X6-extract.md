# Outcome X6: extract grounded claims from supplied sources
Given several short source passages and a list of facts to find, return for each fact the value, the unit, the passage it came from, and a quote copied exactly from that passage. If a fact is not in any passage, say it was not found rather than guessing. If two passages disagree about a fact, report the disagreement instead of picking one.
Example input (short): passages P1 "The index uses 2 hash functions." P2 "Memory was 4 MB." Facts: number of hash functions; memory; latency.
Example output (short): hash functions = 2 (P1, "The index uses 2 hash functions."); memory = 4 MB (P2, quote); latency: not found.
