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
| Retrieval | recall@k (k = 1, 3, 5, 10) | Fraction of a question's gold clauses that appear in the top k passages, averaged over answerable questions |
| Retrieval | MRR | Mean of 1 / rank of the first gold clause (0 if none in the top 10) |
| Faithfulness | Faithful-answer rate | % of non-abstained answers where every claim is supported by a cited, retrieved passage. LLM judge, validated against ~40 hand labels; Cohen's kappa reported |
| Citation integrity | Out-of-set citation rate | % of citations whose clause ID is not in the retrieved set. Target: 0 |
| Abstention | Correct refusal rate | Abstentions / unanswerable questions |
| Abstention | Wrongful refusal rate | Abstentions / answerable questions |
| Gap detection | Precision, recall, F1 | Per status (met / partial / missing) against the seeded answer key, plus confusion matrix |
| Operations | Latency, cost | p50 / p95 latency (total and per stage); tokens and USD per query |

Numeric targets are set after the Phase 1 baseline (fixed 500-token chunks, BM25 only, no citation check).

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
