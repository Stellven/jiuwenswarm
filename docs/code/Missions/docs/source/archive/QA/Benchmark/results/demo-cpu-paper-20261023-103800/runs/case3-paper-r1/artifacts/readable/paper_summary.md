# Chunk Recomputation under Real Document Revisions: Update Workload, Retrieval Quality, and Boundary Drift

## Problem

Static retrieval evaluations do not reveal the embedding work required when documents change. Because chunks are embedded independently, an edit that shifts boundaries can force unchanged text into new embedding inputs. The paper asks how much recomputation fixed-size, recursive paragraph-first, and content-defined chunking require on real revisions; how edit size, position, and boundary rules contribute; and whether lower recomputation accompanies lower evidence recall under the same encoder and retrieval budget (Section I).

Sources: [PDF 1, p. 1]

## Method

Section III defines recompute fraction as the input-token count of distinct new-version embedding inputs absent from the previous-version cache, divided by the token count of all distinct new-version embedding inputs for that chunker. Counts include model special tokens; repeated identical inputs count once. Reuse requires byte-identical complete inputs under the same model configuration, and the cache covers only the previous version of the same document. Thus, this is embedding-input workload relative to each chunker’s own deduplicated full-new-version workload, not latency or price.

Section IV uses 120 primary adjacent Wikipedia revision pairs: 62 Chinese and 58 English. All three chunkers succeeded on 116 articles, forming the common-success comparison pool. Six separate articles supplied calibration; 23 articles with unresolved source reservations were diagnostic only. The primary benchmark has 240 questions and 480 version-specific labels, with sufficient evidence anchored to character spans. The common-success pool supplies 330 answerable, scorable labels.

All chunkers are stateless and partition the same canonical text. Frozen settings are non-overlapping fixed-size windows of 304 content tokens, recursive paragraph-first chunking with a 400-token target, and Steadlith content-defined chunking (CDC) with internal minimum/maximum settings of 176/352 tokens. Retrieval uses frozen BGE-M3 embeddings, exact dot-product ranking, identical multi-document pools, and whole-chunk packing within 2,048 input tokens. Recall records whether the retrieved chunks cover at least one sufficient evidence set; unanswerable versions are excluded. Metrics are averaged within articles and then across articles by language, with 2,000 article-level bootstrap resamples. Edit size is an atom-based matching proxy rather than an audited token-level alignment. Validation includes 20 hand-computed contracts, 13 tokenizer checks, and a no-edit control (Sections III–IV).

Sources: [PDF 1, p. 2], [PDF 1, p. 3]

## Results

At frozen parameters on the 116-article common-success pool, mean recompute fractions for fixed-size, recursive, and CDC chunking are respectively 68.4%, 55.7%, and 54.0% in Chinese, and 57.4%, 37.9%, and 42.8% in English (Table I). The requested fixed-size fractions are therefore 68.4% for Chinese and 57.4% for English, each relative to that method’s distinct full-new-version embedding-input workload. Chinese fixed-size recomputation on all 62 primary articles is instead 67.1%; it should not be confused with the common-success value (Section V).

CDC failed on 4 of the 62 Chinese primary articles; it succeeded on all 58 English articles, while both baselines succeeded on all 120 primary articles. Failures remain NA in the primary tables. Section VI attributes these failures to whitespace-delimited Chinese units of 403–550 tokenizer units exceeding CDC’s 352-unit maximum. Thus, the primary benchmark contains 120 revision pairs, and the common-success pool contains 116 articles (Section IV; Table I).

At frozen settings, recursive and CDC reduce mean recomputation relative to fixed-size by 12.7 and 14.4 percentage points in Chinese, and 19.6 and 14.7 points in English; all four paired 95% bootstrap intervals are below zero (Table II). Fixed-size has the highest mean recomputation in every tested length-matched grid setting. However, CDC-minus-recursive changes sign across settings: −0.7 to +5.5 points in Chinese and −2.4 to +6.2 in English, so their ordering depends on parameters (Section V).

Table I reports evidence recall for fixed-size, recursive, and CDC of 97.4%, 98.3%, and 98.3% in Chinese, and 96.7%, 96.8%, and 95.0% in English. All paired recall intervals include or touch zero; the lowest bound is −4.5 points for English CDC versus recursive. These observations do not establish retrieval equivalence or exclude recall decreases. Retrieval was measured only at frozen settings; the parameter grid measures cost alone (Section V).

In controlled 1% insertions across two Chinese and three English development articles, fixed-size mean recomputation falls from 100% for start insertions to about 12% for end insertions, while recursive and CDC means stay below 30% at each tested position. In a separate 17-article diagnostic, 50% of English and 47% of Chinese fixed-size recomputed input tokens belong to complete inputs whose text occurs verbatim in the old version. The authors interpret these diagnostics as support for boundary drift, without quantifying its causal contribution (Section VI).

Sources: [PDF 1, p. 3], [PDF 1, p. 4], [PDF 1, p. 5]

## Contributions

The paper contributes an explicitly defined, validated measurement procedure for embedding-input recomputation under exact reuse, and a bilingual real-revision benchmark with version-specific evidence labels (Sections I, III–IV). Its empirical contribution is to show substantial differences in update workload alongside small observed mean recall differences at frozen settings, while demonstrating that recursive-versus-CDC workload rankings change with chunk-length parameters. Controlled edits and verbatim-presence checks provide supporting diagnostics for the boundary-drift interpretation rather than a causal decomposition (Sections V–VI). The authors also describe a research artifact containing scripts, per-article results, grids, sensitivity analyses, benchmark identities, diagnostics, and failures; article texts are identified by revision IDs and hashes rather than redistributed (Section VII). Their practical recommendation is to evaluate recomputation under exact reuse across chunk-length settings alongside retrieval quality when selecting chunkers for edited knowledge bases.

Sources: [PDF 1, p. 1], [PDF 1, p. 2], [PDF 1, p. 3], [PDF 1, p. 4], [PDF 1, p. 5], [PDF 1, p. 6]

## Limitations

The authors limit the primary findings to 120 adjacent revision pairs from one source, using one encoder and one retrieval budget. Edit-size bands contain only 2–28 articles and are descriptive. Although lengths were calibrated separately, the realized median-length ratio is 1.17 in both languages; recursive-versus-CDC ordering changes across the grid, precluding a universal ranking (Sections V and VII).

Labels were not independently adjudicated by multiple annotators, and inter-annotator agreement is unavailable. An author audit agreed with 57 of 60 sampled labels; all three disagreements involved versions incorrectly labeled unanswerable. Residual errors could obscure the few-percentage-point recall differences. The reported intervals do not establish equivalence, and the authors do not rank chunkers by recall. Retrieval quality was evaluated only at frozen chunk-length targets, and overlap was varied only for fixed-size windows (Sections V and VII).

Formal token-level edit ratios and amplification factors remain unreported because their required natural alignment has not been independently audited. The atom-based proxy counts moves as deletion plus insertion, and the verbatim-presence diagnostic cannot quantify boundary drift’s causal contribution. CDC handling of unsegmented Chinese through word segmentation or a fallback splitter was not evaluated and would alter boundaries (Sections III, VI–VII).

The cost-only arXivEdits check has uncharacterized extraction noise, absent paragraph boundaries, and no length recalibration; it is not pooled with Wikipedia results. No comparable KARA run was obtained because of byte-preservation, splitting, cache-scope, and cost-model differences. The authors explicitly restrict their comparisons to the three stateless chunkers and draw no conclusion about KARA’s cost or quality (Sections V and VII).

Sources: [PDF 1, p. 2], [PDF 1, p. 4], [PDF 1, p. 5], [PDF 1, p. 6]
