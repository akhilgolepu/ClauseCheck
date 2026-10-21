# ClauseCheck spec (v1, frozen at Phase 0)

ClauseCheck answers questions about regulated quality documents with clause-level citations, abstains when the evidence is weak, and checks SOPs against requirements to produce a gap table. The system and its evaluation are the deliverable.

*Research prototype. Not compliance advice.*

## Corpus cap (frozen)

| Doc ID | Document | Source | Format |
| --- | --- | --- | --- |
| `21CFR11` | 21 CFR Part 11 | eCFR API | XML |
| `EUGMP-A11` | EU GMP Annex 11 | EudraLex Vol. 4 | PDF |
| `ICH-Q9R1` | ICH Q9(R1) | ich.org | PDF |
| `ICH-Q10` | ICH Q10 | ich.org | PDF |

Part 820 (QMSR) is out: its substance is incorporated by reference from ISO 13485, a paid standard. CDSCO documents are future work. Anything else goes under "next steps", not into the corpus.

Plus 10-12 synthetic SOPs with seeded gaps, scored against a private answer key written before the detector.

## User stories

| ID | Persona | Asks | Gets |
| --- | --- | --- | --- |
| US1 | QA analyst | "What does Part 11 require for audit trails?" | Answer with clause citations, or an abstention |
| US2 | Regulatory associate | "Does our change-control SOP cover this guideline?" | Gap table: requirement, SOP section, status, evidence |
| US3 | Auditor | "Which SOPs mention e-signatures, and do they meet the requirement?" | Cross-document results with citations |

## Metric definitions

| Area | Metric | Definition |
| --- | --- | --- |
| Retrieval | recall@k (k = 1, 3, 5, 10) | Fraction of a question's gold clauses covered by the top k passages, averaged over answerable questions |
| Retrieval | recall@B tokens (B = 500, 1000, 2500) | Same, over the top passages that fit in B tokens of retrieved text. **The metric for comparing chunking strategies**: recall@k rewards bigger chunks |
| Retrieval | MRR | Mean of 1 / rank of the first passage covering a gold clause (0 if none in the top 10) |
| Faithfulness | Faithful-answer rate | % of non-abstained answers where every claim is supported by a cited, retrieved passage. LLM judge, validated against ~40 hand labels; Cohen's kappa reported |
| Citation integrity | Out-of-set citation rate | % of citations whose clause ID is not in the retrieved set. Target: 0 |
| Abstention | Correct refusal rate | Abstentions / unanswerable questions |
| Abstention | Wrongful refusal rate | Abstentions / answerable questions |
| Gap detection | Precision, recall, F1 | Per status (met / partial / missing) against the seeded answer key, plus confusion matrix |
| Operations | Latency, cost | p50 / p95 latency (total and per stage); tokens and USD per query |

**Clauses and coverage.** A clause is the smallest numbered unit a citation points to: a first-level paragraph in Part 11 (`11.10(e)`, with its `(1)`/`(i)` sub-paragraphs inside), a numbered section in the PDFs (`4.3`, `I.8`), or one glossary term (`7:Harm`). Gold labels are corpus-wide keys such as `21CFR11:11.10(e)`; a Part 11 numbered sub-paragraph can also be a gold key (`21CFR11:11.3(b)(4)`) and has its own span, so it is scored fairly whether a chunker keeps the parent paragraph whole or splits it. Every chunking strategy chunks the same rendered text, where each clause has a known character span; a passage covers a clause when it holds at least half of the clause, or 300 characters of a long one.

## Phase 1 baseline (dev set, 50 items)

Fixed 500-token chunks, BM25, Llama 3.1 8B (local, Q4) answering from the top 5 passages with no citation check.

| Dev set version | recall@1 | recall@5 | recall@10 | recall@500tok | recall@1000tok | recall@2500tok | MRR | p50 / p95 latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Revised (current)** | 0.51 | 0.78 | 0.90 | 0.51 | **0.61** | 0.78 | 0.74 | 5.1 s / 8.3 s |
| First draft (superseded) | 0.69 | 0.90 | 0.96 | 0.69 | 0.75 | 0.90 | 0.89 | 3.3 s / 5.0 s |

Runs: current `eval/runs/20261021T101544Z.json` (commit 62b331c, clean tree); first draft `eval/runs/20261021T093759Z.json`, recorded as commit 80ce17d, which history rewriting renamed to 513829c (identical tree).

The first draft's questions copied clause wording and named the target section in cross-reference questions, which BM25 matched directly; the revision rewrote those in practitioner language and hid the links, which cost 14 points of recall@1000tok. Recall@k by type on the revised set: lookup 0.72, multi-clause 0.88, cross-reference 0.75. The corpus is still small (46 chunks, so the top 5 is 11% of it).

Unanswerable handling isn't scored until Phase 3, but the baseline already shows the target failure modes: it answers from "general knowledge" when the passages are silent, and accepts false premises with a wrong citation (d041, "Which Part 11 clause requires blockchain-based audit trails?", concludes "§ 11.10(c)", quoting text that is actually in 11.10(e)). d041 is the brief's own example, so it is tagged `regression` and is not counted as independent evidence.

**Unanswerable means** the corpus has no statement that answers the specific question; the correct output is an abstention, optionally naming the nearest clause. All ten are in-corpus near misses (a missing number, threshold, interval or definition next to a real clause), each grep-checked against the parsed text.

**Targets** are margins over the re-run baseline, so they survive the baseline moving. With 40 answerable dev questions, one question moves a recall mean by up to 0.025, so +0.10 is about four questions.

| Metric | Baseline | Target |
| --- | --- | --- |
| recall@1000tok (Phase 2 exit) | 0.61 | baseline + 0.10 (≥ 0.71) |
| MRR | 0.74 | no regression |
| Out-of-set citations | n/a | 0 |
| Wrongful answers on unanswerable | not scored | set after the Phase 3 baseline |
| Wrongful refusals on answerable | n/a | set after the Phase 3 baseline |

Targets are pending sign-off, and dev gold labels are pending source verification (`verified: false`).

Known parsing limitations: the four tables in ICH Q10 section 3.2 flatten row by row into interleaved text, so no gold label depends on table content; some ICH Q9(R1) Annex II section titles absorb their first bold sub-heading.

## Eval hygiene and the test-set freeze rule

1. Eval set: ~150 items. Dev (~50) is for tuning; test (~100, ~20% unanswerable) is frozen at the end of Week 3.
2. On freeze, the test file's SHA-256 is committed. The test runner refuses to run if the hash differs, and logs every execution.
3. The test set is run **once**, on the locked final config, for the headline numbers.
4. Thresholds, prompts, and model choices are tuned on dev only.
5. The SOP answer key is written before the detector; at most one documented tuning iteration against it.
6. The model that generates answers never writes gold labels.
7. Gap-detection numbers are reported as a controlled test on synthetic SOPs, not evidence of real-world performance.

## Cut-line (drop in this order if behind)

1. CDSCO / Indian rules
2. React front end (fall back to a FastAPI-served page)
3. Cost dashboard (fall back to a cost table in the report)

**Never cut:** eval harness, abstention, ablations, the frozen test run, failure analysis.

## Stack

Python 3.11/3.12, FastAPI, Postgres 16 + pgvector (dense) and tsvector (BM25), reciprocal rank fusion, cross-encoder reranker, Docker Compose, GitHub Actions.

Decided by dev-set ablation, not up front: embedding model (bge-small / bge-base / e5), reranker (bge-reranker family), and the small / large LLM pair (provider chosen in Phase 3).

## Run-logging convention

Every eval run writes `eval/runs/<UTC timestamp>.json` (via `eval.runlog.save_run`) with:

- `config`: the full run configuration
- `metrics`: the metric values
- `ops`: latency, tokens, cost
- `git_commit` and `git_dirty`
- `corpus_version`: short SHA-256 of `data/corpus_manifest.json`

Run files are committed. A number in the report without a run file behind it doesn't count.
