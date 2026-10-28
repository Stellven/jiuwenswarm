# Heldout bench: why CC won on one case (gpt-6-luna, 10 cases x 1 rep)

Read-only review. I read the bench code, cases, saved prompts, replies and code. I also re-ran the bench's own checker on the saved code (no model calls) to confirm per-test results. Nothing else was changed.

Sources:
- Score table: C:\Users\m50066326\huawei\outputs\rebench-20261028\slate\modelbench\heldout\scores\heldout-gpt-6-luna.md
- Cases (gate and score suites): C:\Users\m50066326\huawei\AI4Research-Development\jiuwenswarm-agentic\benchmarks\ccbench\heldout\cases.json (MANIFEST check: OK)
- Runner and retry logic: ...\jiuwenswarm-agentic\benchmarks\ccbench\heldout\run_heldout.py (gate_reasons, fmt_reasons, retry_prompt, run_unit)
- Per-unit outputs: C:\Users\m50066326\huawei\outputs\rebench-20261028\slate\modelbench\heldout\heldout\gpt-6-luna\<case>\<arm>-r1\ (attempt1.py, final.py, call-N\prompt.txt, reply.txt, result.json)
- My re-run script (scratch, not a deliverable): C:\Users\M50066~1\AppData\Local\Temp\claude\C--Users-m50066326-huawei\0a2020ac-e084-49eb-a869-26d878a6b9b6\scratchpad\hv\rescore.py

## Headline

- Only one case moved: parse_duration. Plain, verify and selftest all failed it. CC failed its first attempt, got one retry, and passed.
- The other nine cases passed on the first attempt in every arm. On those, CC is the same as plain.
- Score: cc 10/10 cases and 74/74 tests. Plain and verify 9/10 cases and 73/74 tests. Selftest 9/10 cases and 72/74 tests.
- The win is one paired unit from one trap in one case at one rep. It is a demonstration, not a rate.

## 1. The failing case and the hidden score tests

Case: parse_duration. The spec says: "Terms may appear in any order and may be separated by spaces". "May be separated" makes spaces optional, so "1h30m" is valid. The gate suite has `{"args": ["1h30m"], "expect": 5400}`. Plain, verify and selftest all read the spaces as required.

Failing score test, plain and verify (first and only attempt):
- `{"args": ["30m1h"], "expect": 5400}` (the score suite has 10 tests for this case).

Selftest also failed `{"args": [" 2m "], "expect": 120}` in its final code. Its first attempt passed that test. Its retry broke it (see section 4).

Failing code region, plain final.py (attempt1 is identical):

    for term in terms:              # terms = s.split()
        i = 0
        while i < len(term) and term[i].isdigit():
            i += 1
        if i == 0 or i != len(term) - 1:
            raise ValueError("invalid duration term")

"30m1h" is one whitespace token. The digit run stops at "m", which is not the last character, so it raises.

Verify final.py fails at the same rule:

            if not s[i].isspace():
                raise ValueError("invalid duration separator")

Selftest final.py fails at:

        if i < n:
            if s[i] != " ":
                raise ValueError("invalid duration")

I re-ran the checker on the saved code. Plain and verify: 1 score failure each (30m1h), and 1 gate failure (1h30m, which is not scored). Selftest final: 2 score failures (30m1h and " 2m "). Selftest attempt1: 1 score failure (30m1h).

## 2. What was wrong in each other arm

- Plain: tokenizes with `s.split()` and assumes one unit per whitespace token. It rejects both "1h30m" and "30m1h". One call, no check.
- Verify: rewrote the parser as a character scanner, which is cleaner. It still requires a space after every term ("invalid duration separator"). The "check your function" instruction did not change the reading. Score: 73/74.
- Selftest: its first attempt had the same wrong reading (a space is required between terms). Its retry added `if s[i] == " ": raise ...`, which rejects a leading space. That is a new bug, and it broke " 2m ".

Same bug in all three: the adjacent-term rule. Selftest also has a second, self-made regression.

## 3. The CC arm

- Gate test that failed on the first attempt (cc-r1/attempt1.py): `input ["1h30m"]: expected 5400, raised ValueError`. This is gate test 1 of 4. Attempt1 was a whitespace-split parser that treated "1h30m" as one bad term.
- Exact retry text the model received (cc-r1/call-2/prompt.txt):

      Your previous answer failed independent checks that were written separately from this task:
      - input ["1h30m"]: expected 5400, raised ValueError

      Return a corrected complete function in exactly one ```python block and nothing else. Do not change the spec.

- What it changed (cc-r1/final.py, from cc-r1/call-2/reply.txt): it replaced the split-based parser with a character scanner. It reads a run of digits, then one unit letter. Between terms it accepts zero or more spaces. The unit map and the repeated-unit check stay the same. It did not add any special case for "1h30m".
- Hidden score tests the fix made pass: only `{"args": ["30m1h"], "expect": 5400}`. That was the only score test attempt1 failed. Final: 10/10 score tests, 4/4 gate tests.
- Cost of the rescue: 2 calls, 8,760 tokens for this unit (attempt1 about 7,100, retry about 1,660).

## 4. Selftest retries (two in total)

Retry 1, dedupe_records (selftest-r1). Its own assert failed at tests.py line 7:

    assert dedupe_records([{"id": True}, {"id": 1}], "id") == [{"id": True}, {"id": 1}]

The failure is AssertionError. Python hashes True and 1 the same, so they merged. The spec only says 1 and '1' differ. Attempt1 already passed all 6 score tests, and the retry (keys by (type, value)) also passed. This retry was harmless and was not a rescue.

Retry 2, parse_duration (selftest-r1). Yes, it retried on the failing case. The failure was:

    Traceback ... tests.py line 13 ... AssertionError: expected ValueError for '1h  '

Its own test list (selftest-r1/call-1/reply.txt):

    for invalid in ("", " ", "2", "x", "1w", "1s 2s", "+1s", "-1s", "1.5s", "s1", "1 s", "1s2m", "1h  ", " 1h\t1s"):

Why its tests did not catch the bug:
- It lists "1s2m" as invalid. The spec allows adjacent terms, so this test encodes the same misreading.
- Its valid-case asserts have no adjacent terms, so nothing contradicted the misreading.
- It lists "1h  " (trailing double space) as invalid. The spec allows trailing spaces. So its one failing assert was wrong, and the retry followed it. The retry started rejecting leading spaces, which broke " 2m ".

## 5. Verify arm

The verify sentence changed the code's shape but not its decision. The verify call-1 reply already required a separator after each term. It has no checker, so it did not retry. On this case the instruction did nothing useful.

## 6. Fairness

- What the gate shows: only the failing gate inputs, at most 3, each with the input, the expected value and what the function did (a value or an exception). It does not show the whole gate suite, and it never shows a score test.
- What it leaks: the rule for this trap. "1h30m" must be accepted. That same rule decides the score test "30m1h". The README calls this out as a real effect of the check, not noise.
- Disjointness: I checked the 10 cases. No (args, expect) pair appears in both the gate and the score suite. But the trap is shared: gate "1h30m" and score "30m1h" are the same rule. So the suites are disjoint by test, not by trap. The README says both suites were written by one author before any run. The independence is between the check and the worker.
- Could any test give the same rescue? Yes, in principle. Any self-written test with adjacent terms expecting 5400 would have caught the bug. Selftest's tests did not. They asserted the wrong rule ("1s2m" must raise). So selftest did not just write weaker tests. Its test writer shares the worker's misreading, so it cannot catch it. The gate is useful because it is written from the spec separately from the worker.
- Caveat: the win depends on the gate author choosing "1h30m". Without that input, CC would have been 9/10, like the others.

## 7. Plain-language explanation and what would make the win larger

All four arms got the same spec. Three of them read "may be separated by spaces" as "must be separated by spaces". Nothing in their own process caught it. The verify instruction re-read the spec and kept the same reading. Selftest's own tests shared the reading, and its one failing assert was about a trailing double space, which the spec allows. CC had a check written separately from the worker. It contained one input that the worker's reading gets wrong ("1h30m" must give 5400). That one line, with the expected value, was enough for a one-shot fix, and the same fix also passed the matching score input "30m1h". So CC won because an outside check caught a shared misreading, not because it retried more. The sample is still one trap in one case at one rep, and the other nine cases show no difference.

What would make the win larger or more reliable:
- More cases with the same kind of trap: optional separators, adjacent tokens, leading and trailing whitespace, sign and fraction edges. Each gate should include at least one input for each trap class.
- Two reps as the README planned, and a second model (gpt-6.1-sol). One rescue cannot show a rate.
- A control with the gate cut to the non-trap inputs, to measure how much of the rescue depends on the trap input being in the gate.
- Watch self-test retries that follow a wrong self-written test. This run had one harmless retry (dedupe) and one that broke correct code (parse_duration leading space).
