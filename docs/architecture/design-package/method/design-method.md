# How to change the package

`Tier 2 · Part of: [Method](README.md)`

**For design authors and human reviewers.** The package is the authority that coders build from and testers check code against. Keep it small. Content stays only if a builder needs it, it explains why the architecture has this shape, a test depends on it, or it keeps later work unblocked.

1. Change the home first. Tier 3 owns fields and checks. Tier 2 owns behavior and reasons. Replace any copy elsewhere with a link, and grep the whole package for every link to what you changed.
2. Use the [glossary](../glossary.md) terms. The validator fails on a forbidden phrase.
3. If a change alters a producer, consumer, authority, budget, verdict or behavior, record a decision. Add the next number in [decisions](decisions.md). Never renumber.
4. Prefer a precise field row or check condition to an example. If an agent would need an example, fix the explanation.
5. Run `python -I reference/validate.py` from the package folder. Keep each file's line endings.
6. Record human review only when a person did it.

## Comprehension test with a small model

Run it after any change to tier 1 or to a topic's main page.

1. Give a fresh small model (for example Haiku) only the pages under test. Ask for a 5 to 8 sentence retelling, a few questions with known answers, every confusing quote, and a 1 to 10 rating.
2. A wrong answer means the page is unclear. A quoted term means it is used before it is defined. Fix the page, not the prompt.
3. Repeat with a new agent until the retelling is right and the only confusing terms link to a definition.
