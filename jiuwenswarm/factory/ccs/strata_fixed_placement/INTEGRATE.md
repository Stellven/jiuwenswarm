# Source component integration

1. Inspect SOURCE.json, COMPONENT.json, fixed-placement.patch and VERIFICATION.json.
   The isolated source is clean and committed; shared baseline source is untouched.
2. In a controller-approved quiet CPU interval, compile/run the standalone helper
   checks from the source checkout. They require no GPU/model. Compilation and
   runtime validation have not yet been performed at package preparation.
3. Submit BUILD-REQUEST.json through the existing native builder CC with an
   operator-admitted build grant and deadline. It pins the clean source commit
   and clean retained ggml dependency. Do not run builds during quiet measurement.
4. Require a successful retained immutable image receipt. Admit the new env key
   only for this new image/source contract; old profiles/binaries must not pretend
   it engages. Set the same explicit budget both A/A arms under existing guards.
5. Run only a freshly admitted bounded diagnostic via the existing job/loop.
   Independently retain effective budget, every layer hash, aggregate hash, native
   chunk, expert count, prompt wire and all tokens. Reject placement mismatch or
   safe-budget failure. Persistent token mismatch disproves placement control as
   a sufficient remedy. No automatic promotion or performance acceptance follows.
