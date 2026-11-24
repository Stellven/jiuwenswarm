# How the assessment numbers are obtained

**What is assessed.** The figures in an assessment (the worked example here is `runs/muse-assessment-07/assessment.md`) are bounds and estimates for the model
Muse Spark Open on a DGX Spark, within 80 GB (one of the two memory budgets the target carries as candidates), for
an engine of one architecture: the weights every token uses and part of the experts are kept in memory, and the rest are read from
storage when a token routes to them. That architecture is written into the program `tools/so_assess.py`.

**What is not assessed.** The Muse design. The design contributes only which node types it has, read from its
`nodes.yaml`. No figure changes when the design's decisions change, unless a decision gives a number the program
reads: the reserve, the smallest cache and the chunk size, when a node settles that choice with a decision carrying
a numeric `value`. In the worked example no decision of the design carries one, so every figure comes from the model, the machine,
the environment measured on it, the target, and assumptions of the program. Nothing is built or run.

## Which run is which

Since 2026-11-19 the target follows what the bench runs: the model files are a third party's conversion at about
2 bits per expert weight. The kickoff page gives three memory figures: 128 GB as the target, 80 GB as the reference
configuration of Strata on this machine, and 12 GB as a feasibility target. The target carries 128 GB and 80 GB as
candidates, and the project has not chosen. The current figures are therefore two runs:

| Run | Model files | Budget | Upper bound | Decode estimates | First token | Cache |
|---|---|---|---|---|---|---|
| `runs/muse-assessment-08-budget-80` | as the bench runs them | 80 GB | 10.9 tok/s | 0.84 to 2.83 tok/s | 20 to 31 s | 12% to 28% |
| `runs/muse-assessment-08-budget-128` | as the bench runs them | 128 GB, more than the 127.2 GB the machine reports allocatable | 10.9 tok/s | 1.15 to 5.24 tok/s | 12 to 21 s | 35% to 51% |

For 128 GB the program answers "No" to whether it can run: the budget is 0.8 GB above the available memory the machine
reported at the probe. That is one reading, which other processes change (126.2 GB on 2026-11-13). The figures of
that run are what the arithmetic gives for 128 GB as written.

The rest of this document explains the method on one worked example, `runs/muse-assessment-07`: the model at the
precision it was published in (4 bits), within 80 GB. The method is the same for every run; only the inputs differ.
`python tools/so_run_all.py` regenerates all three.

## Read this first

1. **One figure is an upper bound that needs no assumption about how the experts are used:** 12.3 tokens per
   second. It is memory bandwidth divided by the bytes one token surely reads, for one sequence and one token per
   pass over the weights. The parameter counts behind it are read from the headers of the model files that are on
   the DGX Spark (a third party's conversion); the sizes are those counts at 4 bits, the precision of the published
   NVFP4 weights, whose files I have not read. If a tensor is stored at more bits there, the true bound is lower.
2. **Every other speed and time is an estimate under stated assumptions**, not a bound. The main one is that each
   token's choice of experts is independent of the previous token's. If successive tokens repeat experts, a cache
   that follows recent use finds more than my figures allow, so the speed estimates are then not upper bounds and
   the first-token estimates not lower bounds.
3. **The figures of the worked example are for 80 GB,** one of the target's two candidates. The machine reports
   127.2 GB allocatable. The figures change
   with the budget, the reserve, the context lengths and the range of unevenness of expert use; the assessment lists
   each with its source.
4. **The back-test checks the upper bound only.** Strata's reported speeds, divided by the tokens it produces per
   pass, are 0.29 to 0.46 times the bound computed the same way for its model: PASS. I wrote that pass condition on
   2026-11-18, after the first back-test result was known. Strata holds every expert in memory on this machine, so
   nothing about storage reads, cache hit rates or the time to first token has been compared with any engine.

5. **Measured on 2026-11-20, after these figures were computed.** With the bench's llama.cpp baseline on the DGX
   Spark (4 requests, prompts of about 2,000 tokens, 128 tokens out), decode was 1.05 to 1.12 tokens per second:
   under the upper bound, inside the estimates for 80 GB and just below those for 128 GB. The first token came after
   234 to 366 s, 10 to 15 times longer than the first-token estimates for these files (20 to 31 s and 12 to 21 s in
   the table above). Those estimates count reading the experts from storage and leave out computing them; they are
   not what a first token costs on that baseline. A cache holding 25% of the experts found 79% of those a decode step
   asked for, more than the 72% that independent choices allow, so assumption 2 does not hold for this model. The
   section "What the machine measured" has the runs and what each says about the figures.

## How the design enters

The program keeps one table, section by section, of the node types its arithmetic presupposes (model conversion and
expert source for storage; memory planning, positional state and expert cache for the memory plan; expert cache,
residency policy, expert fetch and expert dispatch for decode; prompt reading, expert fetch and prefix reuse for the
first token; telemetry for what is not known) and what it assumes each does. It reads the design's `nodes.yaml` and
lists, for every presupposed type, the design's nodes of that type. If `nodes.yaml` is missing it stops and says why.
If the design has no node of a type, the sections that presuppose it say that their figures describe an engine with
such a part, which this design does not have. It lists the decisions and invariants each such node's component
records.

I checked this. With every responsibility of the Muse components replaced by "Does nothing." and every decision and
invariant removed, no figure changes; the output reports that all 29 nodes were typed from text the design no longer
has, and that the design's words on the reserve, the smallest cache and the chunk size now stand in `nodes.yaml` only.
With a numeric value of 6 GB on the design's reserve decision, the reserve becomes 6 GB and the cache 7% to 16%.

## What goes in, and how each input is known

| Input | Value | How it is known |
|---|---|---|
| Layers, experts per layer, experts used per token | 62, 256, 8 | Model card (vendor stated) |
| All expert weights | 399.43 GB at 4 bits | 798.86B parameters, counted in the model files (below) |
| One expert | 25.17 MB | 3 x 4,096 x 4,096 parameters at 4 bits |
| Every weight other than the experts | 10.57 GB at 4 bits | 21.13B parameters, counted in the model files: 8.91 GB read in full by every token, an embedding table of 0.83 GB and an output head of 0.83 GB |
| Vocabulary, hidden size | 202,048, 8,192 | Model card |
| Memory budget | 80 GB | One of the target's two candidates (128 GB and 80 GB), given on the command line |
| Allocatable memory | 127.2 GB | Measured on the DGX Spark, 2026-11-19: available memory at the moment of the probe, which other processes change (126.2 GB on 2026-11-13) |
| Memory bandwidth | 273 GB/s | NVIDIA specification |
| Storage read rate | 4.77 GB/s with 8 expert-sized reads in flight, which is also the best of the four rates measured (4.34, 4.77, 4.63, 4.76 GB/s at 1, 8, 16, 32 in flight) | Measured on the DGX Spark on 2026-11-19 with a test file; another account's job was starting on the machine about then. The measurement of 2026-11-13 gave 4.58, 4.75, 4.79, 4.82 GB/s |
| Storage capacity | 2,015 GB | Total size of the file system as the machine reports it, not its free space |
| Context lengths | 8,192, 32,768 and 131,072 tokens | My choice: the target sets none. The model allows about 1,000,000 |
| Attention state per token | 0.254 MB at 16 bits when every layer keeps the token | The head counts are from the model files: 16 key-value heads of 64 values each, in 62 layers. The 16 bits per value are my assumption |
| Layers with a window | 46 of 62 attend only to the last 2,048 tokens | From the model files. Whether an engine drops older state for these layers is its choice, so both cases are tabulated |
| Reserve left free, smallest cache, staging area | 2 GB; the 496 experts one step can route (12.5 GB); 16 experts (0.40 GB) | My assumptions. The design states the reserve and the smallest cache in words only, and no node type lists the staging area as a choice |
| Unevenness of expert use | Zipf exponent 0, 0.45, 0.899 | My choice, not a property of the model; 0.899 is the largest possible (below) |

Where the sizes come from. On 2026-11-19 I read the headers of the model files that are on the DGX Spark
(`examples/given/records/muse-ud-iq2_xxs.header.json`, read with `tools/spark_kit/gguf_header.py`; the weights
themselves were not read). They list every tensor with its shape. The experts are three tensors of
4,096 x 4,096 x 256 in each of 62 layers: 798.86B parameters. Everything else is 21.13B parameters: attention 13.52B,
the projections into and out of the experts' latent space 4.16B, the embedding table 1.66B, the output head 1.66B,
the router 0.13B. In all 820.0B, of which 46.1B are active per token; the card says 816B and 42B. Before this the
sizes were derived from the card's two totals, which gave 799.0B and 17.0B. The files on the Spark store the experts
at about 2 bits; the sizes used here are the same parameter counts at 4 bits. The perception encoders are not in
these text-only files.

## The bytes one token reads

Expert weights: 8 x 62 x 25.17 MB = **12.48 GB**.

Other weights: every token reads the 8.91 GB of attention, projection and router weights in full, the output head
(0.83 GB) in full, and one row of the embedding table (4 kB). It does not read the rest of the embedding table, and
a text-only target does not use the perception encoders. Together: 12.48 + 8.91 + 0.83 = **22.22 GB**. With every
part sized, the figure for the upper bound and the figure for the estimates are the same.

The attention state read per token is not in it; leaving it out lowers the bytes and so keeps the bound an upper
bound. The program recognises the embedding table and the output head by their names in the model description,
because the model format has no field that says how much of a table one token reads.

## Upper bound and reference point

**Upper bound:** 273 GB/s divided by 22.22 GB is **12.3 tokens per second**, with every routed expert already in
memory. It holds for one sequence and one token per pass. An engine that checks several drafted tokens in one pass
can exceed it in tokens per second.

**Reference point:** with no expert in memory, every routed expert is read from storage: 12.48 GB at 4.77 GB/s is
2.6 seconds, 0.38 tokens per second. This is not a bound: a cache makes an engine faster, and computation makes it
slower.

## Memory plan

The cache gets the budget minus the other weights (10.57 GB), the attention state for the context, the staging
area (0.40 GB) and the reserve (2 GB). A row fits when the cache is at least 12.5 GB. All six of my rows fit (three
contexts, each with every layer keeping every token and with the 46 windowed layers keeping their last 2,048 tokens
only); the cache holds **8% to 17%** of the 15,872 experts. The attention state takes 0.9 to 33.3 GB: at 131,072
tokens it is 33.3 GB when every layer keeps every token and 9.0 GB when the windowed layers keep only their window,
which is the difference between a cache of 8% and one of 15%.

## Decode speed, as an estimate

**Step 1. The share of a token's experts found in the cache.** I model the use of experts within a layer as a Zipf
law with exponent s: the i-th most used expert has probability proportional to 1/i^s. I assume each token chooses
independently of the previous one, and that the cache holds exactly the most used experts of every layer. Under
independence, no cache can find more than that. The share found is the summed probability of the cached experts.

**Step 2. The largest possible exponent.** A token chooses 8 different experts, so the most used expert can be
chosen at most once per token: 8 x p1 <= 1. For 256 experts this holds up to s = 0.899. Larger exponents are
impossible for this model, and the program does not tabulate them (the figures sent on 2026-11-17 used 1.2, which
is impossible). The range
0 to 0.899 is my choice within what is possible.

| Use of experts | Cache 8% | Cache 17% |
|---|---|---|
| even (s = 0) | 8% found | 17% found |
| s = 0.45 | 23% | 35% |
| s = 0.899 | 53% | 64% |

**Step 3. Time per token.** The experts not found are read from storage: (1 - share found) x 12.48 GB, divided by
the read rate. A token whose experts are all cached still reads 22.22 GB from memory at 273 GB/s, 0.081 s. The time
per token is the larger of the two. This assumes reading and computing overlap fully and computation takes no time
of its own, which favours the engine.

| | Low end | High end |
|---|---|---|
| Use of experts | even | s = 0.899 |
| Cache | 8% | 17% |
| Found in cache | 8% | 64% |
| Read from storage per token | 11.43 GB | 4.47 GB |
| Read rate | 4.77 GB/s | 4.77 GB/s |
| **Tokens per second** | **0.42** | **1.07** |

With the other factors held, the estimate moves most with the unevenness of use (up to 2.33 times), then with the
size of the cache (1.33 times). The read rate is one figure in this run; between the two measurements taken it
differs by less than one percent at 8 reads in flight (4.77 against 4.75 GB/s). Reaching 1 token per second needs 62%
of a token's experts found in the cache; only the 17% cache at s = 0.899 reaches it among my rows.

Why these are estimates and not bounds: if successive tokens reuse experts, a cache that keeps recently used
experts finds more than the best fixed set, and the engine can be faster than my high end. The full overlap and the
missing computation time go the other way.

## Time to first token, as an estimate

A prompt is read as one chunk, one layer at a time, so an expert routed by several tokens is read once. The
probability that a token does not choose expert i is 1 - 8 p_i; over N independent tokens, expert i is touched with
probability 1 - (1 - 8 p_i)^N. Summing over the uncached experts, times 62 layers and 25.17 MB, gives the bytes read
from storage. For the 17% cache this is 232 to 333 GB, **49 to 70 seconds** at 4.77 GB/s, for prompts of
100 to 10,000 tokens that share nothing with stored state. Whatever the use of experts, one chunk cannot read more
than the 333 GB of uncached experts, 70 s at that rate. With even use, a prompt of 100 tokens already touches
96% of them. Under repetition between tokens fewer experts are touched, so these are not lower bounds.

Two changes in the arithmetic since the figures sent on 2026-11-17: the probability of being touched uses
1 - 8 p_i per token (those figures used (1 - p_i) raised to 8N), and the expert cut at the edge of a fractional cache
is treated the same way in the hit rate and in the prompt read (there it was counted as cached in one and uncached in
the other).

## Storage

The prepared files take 410 GB (the expert weights and the other weights at 4 bits). The target names the
checkpoint: the conversion the bench runs, six files of 225.6 GB. No field of the target gives the checkpoint a size,
so the program takes the weights of the target's model as its description sizes them, 226 GB. Checkpoint and prepared
files together are 636 GB, against the 2,015 GB of the file system: they fit. That figure is the file system's total
size; files already on it are not counted. In this worked example the two do not belong together: the prepared files
are at the published precision, and the checkpoint the target names is the 2-bit conversion, from which they could
not be made. In the runs on the bench's files both are 226 GB, 451 GB together. When a target names no checkpoint,
the program prices one for each precision the model card lists.

## The back-test

`tools/so_backtest.py` computes the upper bound the same way (the same function) for Strata's model on the same
machine, for its two weight packs: 43.5 tokens per second for IQ3_S and 41.2 for NVFP4. For that model the
description lists the embedding table and the output head separately with their sizes, so the bytes are the experts,
the other weights (4.86 GB), the output head (0.44 GB) and nothing for the embedding row, whose size cannot be derived
there. The lookup table is read while generating, in an amount the description does not give, and is not counted;
counting any of it would lower the bound. The description notes that the engine's own weight packs skip about
2.7 GiB of the 4.86 GB of other weights. The program does not read that note; it prints it. If those packs do read
less, the bound for them is higher than shown, so the result below would only move further from failing.

Strata reports 38.4 to 48.5 tokens per second. It drafts and checks 2.4 to 3.2 tokens per pass (from its own
documents, not stated for this machine). In tokens per second the reported speeds are 0.93 to 1.12 times the bound;
this cannot show anything, because the bound is per pass. Per pass they are 0.29 to 0.46 times the bound. The
condition, every reported speed divided by the fewest tokens per pass at or below the bound, holds: PASS. I wrote this
condition on 2026-11-18, after the result of the first back-test was known; that back-test, sent on 2026-11-17, had no
condition and could not fail. A per-pass ratio well below 1 says only that the engine is slower than the bound, not how close the bound is.

The first back-test reported "0.87 to 1.04" by comparing tokens per second with a figure per pass, and it left out
the output head that the Muse figure sent with it counted; that comparison does not test the bound.

I checked that the condition can fail: with the reported speeds multiplied by 10 the program prints FAIL (per pass
2.91 to 4.65 times the bound) and exits with 1. A reported speed far below the bound, such as 0.45 tokens per second,
still passes: an upper bound says nothing about how much slower an engine is.

On 2026-11-20 I ran Strata on the DGX Spark myself: the engine built there from the project's source, its IQ3_S
pack, the configuration its own setup writes for this machine, 4 requests per prompt length after 2 warm-up
requests. It decodes at 52.9 to 60.6 tokens per second on prompts of 2,034 to 2,616 tokens and at 57.0 to 58.6 on
prompts of 4,480 to 5,394 tokens, and the first token comes after 1.8 to 3.4 s. Its log gives the accepted drafts
of every request, from which a pass yields 2.25 to 2.84 tokens. Per pass the measured speeds are 0.43 to 0.62 times
the bound of 43.5: PASS (`runs/strata-backtest-03-measured`, records in `runs/strata-measured-2026-11-20`). These
speeds are higher than the 45.2 to 48.5 the project's table gives for this pack; that table is for a release build
of 27 October with 256-token answers on prompts of 4K to 32K, and I have not looked for the cause of the difference.

The memory part of the back-test adds up what the description gives an amount for: 59% to 67% of the memory the
engine and the system hold, as computed from the free memory Strata reports. The lookup table is matched to the
description's item by its size; for the NVFP4 pack the evidence says it is read from storage, so it is not counted
there.

## Whether it can run

The answer is computed from the storage result, the rows of the memory plan that fit, the target's context length
and the budget against the allocatable memory. For the worked example it is "Yes on memory and storage for the rows
of Section 5 that fit", with the context length open because the target sets none.

I tried each other answer on a copy of the worked example, on 2026-11-19:

| Change | Answer |
|---|---|
| A target context of 500,000 tokens | "Only if the attention state for the target's 500,000 tokens is held as in the rows of Section 5 that fit (the 46 windowed layers keep their last 2,048 tokens only)" |
| Storage reported as 500 GB | "Only if the checkpoint is prepared on another machine": 226 GB and 410 GB do not fit together |
| Storage reported as 100 GB | "No: the prepared files do not fit on storage" |
| A budget of 600 GB | "No": the budget is above the 127.2 GB allocatable |
| A budget of 22 GB | "No: no row of the memory plan fits" |

The last three are also planted by the self-test on every run of `python tools/so_run_all.py`, there on the bench's
model files. The command line takes only a budget the target names as a candidate, so the two budget cases are made
by changing a candidate in a copy of the target.

## What the machine measured, 2026-11-20

After these figures were computed I ran the model files the bench uses on the DGX Spark itself, with a llama.cpp
server in the bench's configuration: the expert weights stay mapped from the model files and are worked on the CPU
side (`--cpu-moe`), every other weight is on the GPU. Then the same with part of the experts cached on the GPU
(`--moe-cache-mib`). Each run is 4 requests after 2 warm-up requests, prompts of 2,042 to 2,398 tokens, 128 tokens
out, and the figures are the engine's own timings. `python tools/so_measured.py` prints the comparison from the
records in `runs/muse-measured-2026-11-20/`.

| Run | Experts cached on the GPU | Mapped model files, GPU memory | Decode, tok/s | Prompt, tok/s | First token, s | Found in the GPU cache while decoding |
|---|---|---|---|---|---|---|
| control | none | 91.9 GiB, 21.4 GiB | 1.05 to 1.12 | 6.3 to 9.0 | 234 to 366 | |
| 16 GiB cache | 8.3% | 76.3 GiB, 37.4 GiB | 0.41 to 0.48 | 6.2 to 8.2 | 265 to 404 | 52.8% |
| 48 GiB cache | 25.0% | 44.4 GiB, 69.4 GiB | 0.68 to 0.72 | 10.2 to 13.1 | 164 to 233 | 79.0% |

What this says about the figures above:

- **The upper bound holds.** The fastest request decodes 9.7 times below 10.9 tokens per second. A margin that wide
  says this baseline is limited by something other than memory bandwidth; it does not say how tight the bound is.
- **Decode.** The control run is inside the estimates for 80 GB (0.84 to 2.83) and 6% under the low end of those for
  128 GB (1.15 to 5.24), which is the nearer comparison: the process held about 122 GB. The estimates assume that
  reading overlaps fully with computing and that computing takes no time of its own. The baseline is not that
  engine, so this is a check of the order of magnitude and no more.
- **First token: the estimates do not hold for this baseline.** They are 20 to 31 s and 12 to 21 s; the control run
  took 234 to 366 s. The arithmetic counts one reading of the experts that are not in memory, at most about 30 s at
  the measured read rate, and nothing for computing them. The remaining time, more than 200 s, is not that one
  reading. I have not separated what it is: computing the experts on the CPU for 2,000 tokens in 62 layers, reading
  the same files again because 206 GB of experts pass through 92 GiB of page cache, or both.
- **The independence assumption does not hold.** A cache with 8.3% of the experts held 52.8% of those a decode step
  asked for, and one with 25.0% held 79.0%. If each token chose its experts independently, the most a cache of
  that size could hold is 52.3% and 71.9%, at the most uneven use the model allows. The second figure is above that
  limit, so successive tokens reuse experts, and the decode estimates are not upper limits for an engine with a
  cache that follows recent use. The counts are the server's, over every decode step of a run, warm-up included.
- **A cache on the GPU made this baseline slower at decoding.** Both cache runs decode slower than the control,
  although most routed experts were found in the cache. The memory given to the cache is taken from the page cache
  of the model files (92 GiB mapped without it, 44 GiB with 48 GiB of cache), and every expert not found is uploaded
  to the GPU. I have not measured how the loss divides between the two.
- **Two inputs agree with the machine.** The server allocates 4,096 bytes of attention state per token per layer,
  the figure derived from the model files. The storage read rate was measured three more times on the idle machine:
  4.44 to 4.81 GB/s for ranges of 25.2 MB and 4.28 to 5.04 GB/s for ranges of 12.98 MB, the size of one expert in
  these files; the figures use 4.77.

What these runs are not: an engine built to the Muse design. They test inputs, the bound and assumptions of the
arithmetic, with one runtime, one prompt length and four requests a run.

## What would narrow the range

1. Record the routing itself. The cache counts of 2026-11-20 show that successive tokens reuse experts, at two
   cache sizes; they do not give how often each expert is used or how long reuse lasts, which is what a cache
   policy and a decode estimate need.
2. Count the time of computing, per token and per prompt token, and add it to the decode and first-token
   arithmetic, which now counts reading only.
3. Fix the context length in the target.
4. Read the published NVFP4 files themselves. The headers read on 2026-11-19 are of the third party's conversion; the
   sizes used here are its parameter counts at 4 bits, and the encoders' weights are in no file I read.

## Headline figures: what was sent on 2026-11-17 against the worked example

| | Sent on 2026-11-17 | The worked example (run 07) |
|---|---|---|
| Memory-bandwidth figure | 13.0 tok/s, called a ceiling, with the other weights taken as 8.5 GB from the card's totals | 12.3 tok/s upper bound, with the weights as counted in the model files |
| Decode | 0.42 to 2.17 tok/s, called a ceiling | 0.42 to 1.07 tok/s, estimates |
| Unevenness tabulated | 0, 0.8, 1.2 | 0, 0.45, 0.899 (1.2 is impossible) |
| First token | 31 to 70 s, called a floor | 49 to 70 s, estimates |
| Cache | 9% to 17% of experts | 8% to 17% of experts |
| Back-test | 0.87 to 1.04, no condition | per pass 0.29 to 0.46 of the bound, PASS |

To reproduce:

```bash
python tools/so_backtest.py sys/strata --hardware hw/dgx-spark --evidence evidence/strata-on-spark/reported --out runs/strata-backtest-02 --root .
python tools/so_assess.py sys/muse-on-spark --spec spec/muse-spark-open-on-dgx-spark/target --environment env/dgx-spark-measured-20261119 --model model/muse-spark-open --budget-gb 80 --backtest runs/strata-backtest-02 --out runs/muse-assessment-07 --root .
```
