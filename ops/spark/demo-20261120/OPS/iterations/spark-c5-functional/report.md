# C5 mapper functional iteration

The native legacy mapper passed gate-off and gate-on greedy content and reasoning parity at 512 and 2048 tokens. Both capped probes exited cleanly. Gate off was marker-free. Gate on printed its active configuration and recorded zero layout decisions, zero mapped rows and three bypasses.

## Planned and actual cuts

The 2048-token plan expected stock logical spans 2047 + 1 and engaged mapper spans 1536 + 512. The proposed physical counts were five and four. The gate-on run retained the 2047 + 1 logical split and emitted no mapper layout markers. Physical microbatch counts were unmeasured.

## Source diagnosis and next action

The ordinary batch starts and resets with alora_scale=-1.0f, but mapper eligibility requires alora_scale==0.0f. A real adapter transition assigns its scale.

Recognize the stock no-transition sentinel while keeping actual adapter transitions bypassed. Verify changed logical cuts, measured physical microbatches, parity and silence before timing.

## Verified post-LAB fault and read analysis

The native analysis CC verified each report from the pinned request result and first-token counter snapshots. All four functional requests were discarded from timing. Page-cache and ordering differences preclude a speedup claim.

| Arm | Tokens | Functional TTFT | Process major faults | Process reads |
| --- | ---: | ---: | ---: | ---: |
| C5-off-functional | 512 | 52.033 s | 16779 | 24318382080 B |
| C5-off-functional | 2048 | 44.811 s | 1921 | 2811039744 B |
| C5-on-functional | 512 | 62.939 s | 24647 | 13925044224 B |
| C5-on-functional | 2048 | 125.120 s | 8048 | 5375512576 B |
