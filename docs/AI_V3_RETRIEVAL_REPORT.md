# Hope Archive AI v3 — retrieval quality and OCR foundation

Local development verification, 2026-09-23. **Not a release approval.**
No push, merge, tag, release or upload was performed. Manual QA remains postponed.

## A. Recovered architecture

Started with a clean working tree on `feature/ai-diary-assistant`, HEAD
`061a909`; `main` and published RC6 remain at `154fd92`.
Inspected the actual backend, frontend, OCR, normalization, FTS schema and tests.

Normalized JSON is still authoritative. SearchIndex derives per-root SQLite FTS5
trigram indexes; short Chinese terms use a literal scan. Stable identities include
owner, kind, diary category and original ID; later snapshots win. Account routes
select an account root; offline mode intentionally covers the locally loaded archive.
Index source paths never enter returned search evidence.

Ask uses deterministic query preparation, diary candidates, long-entry chunks,
at most 8 chunks / 12,000 body characters, bounded conversation history and
source-locked follow-ups. Timeline filters for relevance then sorts chronologically.
Review/Selected use the existing session-memory WorkflowManager with bounded
hierarchical batches, progress/cancel/retry and derivative Markdown exports.
Eleven provider families, Credential Manager, privacy confirmation and non-streaming
calls are unchanged. Selected mode still resolves only selected stable source IDs.

## B. Files changed

Production:
- `src/hope_archive/retrieval.py`: small local concept dictionary, coverage confidence,
  development match explanations; no network/provider/model dependency.
- `src/hope_archive/ai_assistant.py`: preserve the frozen lexical policy, wrap it with
  local concept expansion; tighten English alias boundaries.
- `src/hope_archive/search.py`: bounded related-diary result adapter over existing retrieval.
- `src/hope_archive/product_api.py`: validate explicit related-search option and diary scope.
- `frontend/vite-app/src/SearchPage.tsx`: opt-in local related-word search, limit notice;
  existing source-detail and selected-ID handoff retained.
- `scripts/build_windows.ps1`, `scripts/smoke_backend.py`: separate v3 output name and
  synthetic packaged related-search smoke.

Verification and documentation:
- `tests/test_retrieval_v3.py`, `tests/test_ai_workflows.py`.
- `frontend/vite-app/tests/retrieval-v3.test.mjs`.
- `benchmarks/retrieval_v3/`: corpus, evaluator, frozen baseline, concept results,
  isolated embedding/rewrite/performance experiments, reports, sensitivity and reproduction README.
- `docs/AI_V3_OCR_FOUNDATION.md` and this report.

No provider adapters, normalized schema, OCR engine, export renderer, login, capsule,
private overlay or archive directory architecture were redesigned.

## C. Benchmark dataset design

60 fictional diaries; 80 manually judged queries: 26 exact, 8 alias, 13 paraphrase,
33 semantic; 55 Chinese, 18 English and 7 mixed-language; 6 date-filtered cases.
Programming, coursework, travel, sports, food and daily life are represented.
Distractors explicitly include nonparticipation, future plans and mere mentions.

Dataset was committed before production changes. Frozen SHA-256:
`6b508fac6c757fcc44f310a3395fc3940012c589df4c3d21e2d2ede00e8aaa50`.

All strategies use the same queries and labels. Macro recall divides by all relevant
diaries for each query; it is not simply hit rate. MRR uses the full candidate list.
Precision@1/3/5 and per-query ranks are in the JSON reports. Literal baseline means
whole-question literal search with existing diary ranking, not the date-sorted
Local Search UI. Existing v2 alias rankings are reproduced exactly by regression tests.

This is a diagnostic development set, not independent held-out evaluation.
The same developer authored queries and improvements, and the requested motivating
examples are included; generalization must not be inferred from these scores alone.

An annotation issue was discovered after freezing: q69's August NLP query omitted
d31 (“natural language processing”, August 31). The frozen data and baseline remain
unchanged; `judgment-sensitivity.json` adds that relevant ID without altering rankings.
Corrected overall R@5: v2 0.3865, v3 0.5836, E5 0.8353, v3 hybrid 0.9090.
This does not change the architecture decision. Broad activity labels deserve
independent adjudication before using this benchmark as a release gate.

## D. Frozen baseline and aggregate metrics

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| A: literal FTS | 0.2583 | 0.3104 | 0.3104 | 0.3250 |
| B: frozen v2 aliases | 0.2979 | 0.3844 | 0.3927 | 0.4208 |
| B+: v3 local concepts | 0.3567 | 0.5151 | 0.5836 | 0.5421 |
| C: handwritten replay (NOT LLM quality) | 0.3237 | 0.4706 | 0.5221 | 0.5271 |
| D: local E5 | 0.5078 | 0.7647 | 0.8353 | 0.8281 |
| E: v2 + E5 RRF | 0.5335 | 0.7549 | 0.8415 | 0.8239 |
| E+: v3 + E5 RRF | 0.5533 | 0.7976 | 0.9090 | 0.8663 |

The shipped local policy improves R@5 from 39.27% to 58.36% on the frozen set.
No individual query loses R@5 or a previously correct first result versus v2 in
this set. This does not imply universal precision preservation: broad concept
matches can still retrieve negations and plans. Read the source before making claims.

## E. Query-rewrite experiment

`rewrite.py` is a development-only injected-callback protocol, not a configured
cloud feature. It sends constant instructions plus **only the question**, never
diary content, history, source IDs or credentials. It requires explicit enable and
consent flags, skips strong literal coverage, bounds/parses terms, reruns local FTS
with the original date/type scope and falls back on failure or empty expansion.
Only actual retrieved entries can become evidence.

Measured **handwritten replay**, not actual LLM quality: 12 illustrative nonempty
responses; 54 simulated extra requests across 80 queries; zero live provider calls.
Overall R@5 is 0.5221, semantic R@5 0.3515. This demonstrates that useful added terms
can improve recall, not that any configured provider reliably generates them.

Decision: do not ship a cloud rewrite setting yet. Provider-specific quality,
latency, drift and false expansions remain unmeasured. Mocked timeout, malformed
response, consent, question-only, strong-skip and filter tests pass. No misleading
“local” cloud label or new privacy consent is added to production.

## F. Embedding candidates evaluated

- **Locally measured:** official `intfloat/multilingual-e5-small` quantized ONNX
  variant at pinned revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. It supports multilingual retrieval;
  official usage specifies query/passage prefixes, normalized mean pooling and a
  512-token limit. The card declares MIT. [Official E5 model card](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md).
- **Desk-screened, not locally benchmarked:** `BAAI/bge-small-zh-v1.5`; the official
  card lists Chinese, 512-dimensional embeddings, CLS pooling and MIT. It is a
  reasonable Chinese-first candidate but was not assumed to have comparable
  English/mixed performance. The official file listing inspected did not provide
  ONNX, so no third-party conversion was silently substituted. [Official BGE card](https://huggingface.co/BAAI/bge-small-zh-v1.5).

No comparative BGE quality, latency, memory or local model-size numbers are claimed.
No remote embedding service, vector database, PyTorch installation or bundled
embedding model was introduced.

## G. Local embedding metrics and experiment boundary

Actual local CPU inference on all 60 diary bodies / 80 queries: R@5 0.8353,
MRR 0.8281, semantic R@5 0.6966. Inputs are synthetic only.
CPUExecutionProvider, two threads, ONNX Runtime 1.30.0, isolated tokenizers 0.22.2.

Each short benchmark diary is one experimental chunk. Session-memory cache keys
use stable synthetic diary IDs plus content digests. New/changed entries encode,
deleted entries disappear, unchanged entries reuse vectors; a fresh cache rebuilds.
Date/type/selected filters apply before ranking; separate index instances isolate
corpora. Invalid vectors or inference errors return caller-supplied FTS fallback.

**Not production-ready:** no persistent semantic index, no production account-key
schema, no long-diary token-aware chunking, no robust no-evidence threshold and no
cross-CPU compatibility validation. The encoder truncates at 512 tokens; that is
acceptable for this short synthetic corpus, not for shipping full-diary embeddings.
The cache prototype and tests are not a claim that persistent index migration is done.

Model SHA-256: `dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88`.
Tokenizer SHA-256: `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39`.
Download/setup instructions are in the benchmark README; inference code has no
download or remote inference path.

## H. Hybrid experiment

Equal reciprocal-rank fusion, `sum(1/(60 + rank))`, deterministic tie-breaking;
no fitted score weights, no learned reranker or parameter sweep.
Both component candidate lists are filtered before fusion.

Frozen v2 + E5 reaches R@5 0.8415 but MRR declines from E5's 0.8281 to 0.8239;
semantic R@5 also drops (0.6966 → 0.6865).
The additional v3-concept + E5 experiment reaches R@5 **0.9090**, MRR **0.8663**.
This justifies further optional-component work, not automatic bundling.
Results include every rank and category; there is no assertion that fusion wins
for every query. Broad nearest-neighbor results still need abstention/precision tests.

## I. Per-category metrics

All figures are fractions, not confidence percentages. Language/date rows overlap
intent classes. The replay rows below remain **handwritten simulation**, not LLM scores.

### A: literal FTS

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| alias | 8 | 0.1667 | 0.1667 | 0.1667 | 0.2500 |
| exact | 26 | 0.7244 | 0.8846 | 0.8846 | 0.8846 |
| paraphrase | 13 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| semantic | 33 | 0.0152 | 0.0152 | 0.0152 | 0.0303 |
| Chinese | 55 | 0.2576 | 0.3000 | 0.3000 | 0.3091 |
| English | 18 | 0.3426 | 0.4444 | 0.4444 | 0.4444 |
| mixed | 7 | 0.0476 | 0.0476 | 0.0476 | 0.1429 |
| date-filtered | 6 | 0.5000 | 0.5833 | 0.5833 | 0.6667 |

### B: frozen v2 aliases

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| alias | 8 | 0.2083 | 0.2917 | 0.2917 | 0.3750 |
| exact | 26 | 0.7628 | 0.9231 | 0.9231 | 0.9231 |
| paraphrase | 13 | 0.1026 | 0.2436 | 0.2949 | 0.2436 |
| semantic | 33 | 0.0303 | 0.0379 | 0.0379 | 0.1061 |
| Chinese | 55 | 0.2455 | 0.3030 | 0.3030 | 0.3152 |
| English | 18 | 0.3704 | 0.4861 | 0.4861 | 0.5833 |
| mixed | 7 | 0.5238 | 0.7619 | 0.8571 | 0.8333 |
| date-filtered | 6 | 0.5000 | 0.5833 | 0.5833 | 0.6667 |

### B+: v3 local concepts

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| alias | 8 | 0.5833 | 0.7500 | 0.7500 | 0.7500 |
| exact | 26 | 0.8013 | 0.9615 | 0.9615 | 0.9615 |
| paraphrase | 13 | 0.1026 | 0.2436 | 0.3205 | 0.2436 |
| semantic | 33 | 0.0515 | 0.2135 | 0.3492 | 0.2788 |
| Chinese | 55 | 0.2945 | 0.4402 | 0.5004 | 0.4491 |
| English | 18 | 0.4815 | 0.6296 | 0.6944 | 0.7130 |
| mixed | 7 | 0.5238 | 0.8095 | 0.9524 | 0.8333 |
| date-filtered | 6 | 0.5833 | 0.9167 | 0.9167 | 0.9167 |

### C: handwritten replay (NOT LLM quality)

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| alias | 8 | 0.2083 | 0.2917 | 0.2917 | 0.3750 |
| exact | 26 | 0.7628 | 0.9231 | 0.9231 | 0.9231 |
| paraphrase | 13 | 0.1026 | 0.2436 | 0.2949 | 0.2436 |
| semantic | 33 | 0.0929 | 0.2468 | 0.3515 | 0.3636 |
| Chinese | 55 | 0.2748 | 0.3887 | 0.4327 | 0.4333 |
| English | 18 | 0.3954 | 0.6074 | 0.6648 | 0.6944 |
| mixed | 7 | 0.5238 | 0.7619 | 0.8571 | 0.8333 |
| date-filtered | 6 | 0.5000 | 0.5833 | 0.5833 | 0.6667 |

### D: local E5

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| alias | 8 | 0.1458 | 0.5833 | 0.8750 | 0.5660 |
| exact | 26 | 0.7628 | 0.9615 | 0.9615 | 0.9436 |
| paraphrase | 13 | 0.6154 | 0.8718 | 0.9103 | 0.8974 |
| semantic | 33 | 0.3524 | 0.6113 | 0.6966 | 0.7733 |
| Chinese | 55 | 0.5305 | 0.7616 | 0.8137 | 0.8121 |
| English | 18 | 0.4509 | 0.7380 | 0.8741 | 0.8472 |
| mixed | 7 | 0.4762 | 0.8571 | 0.9048 | 0.9048 |
| date-filtered | 6 | 0.4167 | 1.0000 | 1.0000 | 0.8056 |

### E: v2 + E5 RRF

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| alias | 8 | 0.2708 | 0.5833 | 0.8750 | 0.6285 |
| exact | 26 | 0.8013 | 0.9615 | 0.9615 | 0.9629 |
| paraphrase | 13 | 0.6282 | 0.8205 | 0.9744 | 0.8590 |
| semantic | 33 | 0.3490 | 0.6079 | 0.6865 | 0.7480 |
| Chinese | 55 | 0.5376 | 0.7596 | 0.8228 | 0.7969 |
| English | 18 | 0.5065 | 0.7380 | 0.8556 | 0.8657 |
| mixed | 7 | 0.5714 | 0.7619 | 0.9524 | 0.9286 |
| date-filtered | 6 | 0.5833 | 1.0000 | 1.0000 | 0.8889 |

### E+: v3 + E5 RRF

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| alias | 8 | 0.5208 | 0.8333 | 1.0000 | 0.8438 |
| exact | 26 | 0.8013 | 0.9615 | 0.9615 | 0.9629 |
| paraphrase | 13 | 0.6282 | 0.8205 | 1.0000 | 0.8590 |
| semantic | 33 | 0.3364 | 0.6508 | 0.8096 | 0.7985 |
| Chinese | 55 | 0.5482 | 0.7990 | 0.8982 | 0.8419 |
| English | 18 | 0.5620 | 0.8074 | 0.9065 | 0.9167 |
| mixed | 7 | 0.5714 | 0.7619 | 1.0000 | 0.9286 |
| date-filtered | 6 | 0.4167 | 1.0000 | 1.0000 | 0.8333 |

## J. Performance measurements

Single-machine observations, not guarantees; Windows 11 build 26200, Python 3.12.10,
Intel Family 6 Model 183. Other local work may affect wall-clock timings.

- 60-diary FTS baseline index build: 16.370 ms, 94,208 bytes.
- Latest 80-query mean / p95: literal 1.431 / 1.526 ms;
  v2 aliases 1.476 / 1.647 ms; v3 concepts 1.582 / 1.942 ms.
- Separate 6,000-entry synthetic scale test: index build 101.626 ms,
  unchanged sync 2.348 ms, one changed normalized file 119.893 ms;
  50-query mean / p95 8.354 / 14.324 ms.
- Existing FTS policy still rebuilds entries on changed normalized files.
  This is not falsely reported as per-diary incremental FTS.
- E5 session initialization 809.717 ms; 60-entry embedding build
  253.095 ms; unchanged cache sync 0.068 ms;
  one changed entry 5.243 ms.
- E5 inference mean / p95 3.672 / 4.970 ms
  (short synthetic inputs); mean 60-vector ranking 0.219 ms.
- Rewrite: zero actual cloud calls; replay simulated 54 additional requests.
  Actual provider latency/currency cost is unmeasured.
- “Cold” means a newly created model session, not an OS cold boot/disk-cache flush.

## K. Memory measurements

Windows process peak working set, including runtime/native allocations:
6,000-diary FTS diagnostic 46,669,824 bytes (44.51 MiB);
embedding experiment 473,976,832 bytes
(452.02 MiB).
The latter is a separate Python experiment, not the shipped application's memory
or an incremental-memory estimate. Hash-file reading is outside the measured inference peak.

## L. Disk and index size

FTS: 94,208 bytes for 60 entries; 4,231,168 bytes for 6,000 entries.
Embedding vectors: 92,160 bytes for 60 × 384 float32 values, excluding Python object
overhead. The experimental vector cache is memory-only; no persistent index size
or database durability claim is made.
Model file: 118,346,824 bytes; tokenizer: 17,082,730 bytes; combined 135,429,554 bytes
(129.16 MiB), before runtime/dependency overhead. These remain under ignored
`build/ai-v3/` and were not committed or copied into packaging.

## M. Installer-size impact

v3 is 116,496,648 bytes (111.10 MiB), 6,605 bytes smaller than the retained v2
installer. Compression/build variation means this is not an exact code-size delta.
No embedding files/tokenizers/benchmark code appear in the packaged backend/OCR
analysis manifests. Bundling E5 would add substantial raw payload; no exact
hypothetical compressed installer size is invented.

## N. Selected production retrieval policy

Ship the existing FTS index plus bounded, transparent local concepts for Ask and
Timeline. Local Search defaults to unchanged literal behavior; an unchecked-by-default
“本地相关词检索（仅日记，不联网）” option uses the same query preparation and
SearchIndex retrieval as AI. It is diary-only, relevant-first, paged in 50s and
capped at 200 candidates with a limit notice. It does not read provider settings.

Concepts cover a deliberately limited set: NLP, HMM, BPE, language models, text
encoding/tokenization, mountains and sports. Broad concepts expand one-way;
an exact nanoGPT query does not silently expand to all models.
This is improved lexical retrieval, **not general semantic understanding**.

## O. Confidence and fallback policy

Development coverage labels only: none = zero candidates; strong = full question
literal occurs in a candidate; otherwise weak. Strong does not mean a factual claim
is true or a negation is absent. No fake percentage is displayed.
Development diagnostics require explicit HOPE_AI_DEBUG and reject frozen builds;
there is no public diagnostic API or production score UI. They expose bounded
query terms/match explanations and counts, not source bodies or paths.

Production has no semantic dependency to fail: local FTS remains available offline.
Optional experimental rewrite and vector ranking fall back to existing filtered
FTS on failures. Existing FTS corruption behavior remains an explicit search error;
v3 does not pretend to repair arbitrary corrupt SQLite files with new semantics.

## P. OCR architecture discovered

Manual local OCR accepts name/data, not diary/media identity, and keeps only current
job output. Normalized media and OCR jobs have no validated association.
Current diary text and comments already share a combined FTS body; they are not
independent provenance kinds.

## Q. OCR implemented or deferred

Actual OCR indexing is **deferred**. The implemented foundation is a design contract
in [AI_V3_OCR_FOUNDATION.md](AI_V3_OCR_FOUNDATION.md), documenting validated linkage,
source kinds, revision/invalidation, separate derivative storage and future tests.
No guessed filename/date relationship, new normalized OCR field or automatic OCR scan.

## R. OCR citation behavior

No OCR evidence enters current answers. Future citations must say
“日记图片文字识别”, preserve parent diary navigation, and distinguish recognized
text from authored words. The design covers uncertainty, corrected text and
hierarchical citation propagation. This behavior is not falsely presented as shipped.

## S. Privacy and security verification

Synthetic-only fixtures and model experiments. No live AI calls or diary upload.
Tests cover account roots, selected-ID restrictions, local-only query routes,
safe returned IDs, no path metadata, no-evidence/no-model behavior, source immutability,
deduplication, bounded context, consent and provider-secret metadata boundaries.
The existing 11-provider/Credential Manager tests still pass.

Experiment rewrite receives only constant instructions and the question; rewritten
terms are never returned as evidence. Models run on CPU locally; no remote embedding
API, image upload or VLM code exists. Added OCR fields cannot quietly enter search.
Dev diagnostic gating is tested with frozen mode and default-off environment.

These tests do not claim to sanitize arbitrary secret/path strings a user themselves
typed into diary content, or prove actual provider answers faithful. They verify the
application metadata/request boundaries exercised by the suite.

## T. Migration and rebuild

No production schema change and no new semantic/OCR persisted index.
Existing v1/v2 FTS tables continue to work; tests compare schemas and verify rebuild
preserves stable IDs and source bytes. Search rebuild uses normalized data only.
Experimental memory cache supports update/delete/rebuild, but persistent semantic
migration and download integrity/recovery UX remain future work.

## U. Existing AI v1/v2 regression

Ask/history/source-lock, Review batching/citations, Timeline ordering, Selected
isolation, Search→AI, topic evidence and Markdown exports retain the existing tests.
The old three-case semantic-failure test now checks both the preserved v2 failures
and successful v3 candidate retrieval; it was not deleted or simply weakened.
No unrelated renderer/login/OCR/capsule changes were made.

## V. Python tests

234 tests passed (212 existing + 22 new); full suite ran successfully.
New cases cover frozen rankings/metrics, aliases/paraphrases/Chinese/English/mixed,
filters, account and selected isolation, dedup/long text, rebuild/source immutability,
old schema, no evidence, diagnostics, OCR nonassociation, route validation,
rewrite privacy/failure and experimental vector cache/fusion boundaries.
After experiment-only fallback hardening, the 22-test v3 suite also passed.

## W. Frontend tests

12 tests passed (10 existing + 2 new). Added checks cover default-off/local/diary-only
related search, bounded-result notices and preserved source/selection navigation.
These are the project's existing lightweight source-contract/pure-function tests,
**not mounted-browser interaction or visual UX tests**.

## X. Build checks

Frontend lint, TypeScript typecheck and production build passed.
Full Windows PyInstaller/Tauri NSIS build passed; exact executable icon resources
verified. Non-blocking existing Vite warning concerns future native configuration
loader support for __dirname; not changed as unrelated. Optional TensorRT import
warning during CPU OCR packaging did not prevent bundled OCR verification.

## Y. Packaged verification

Real frozen backend launched under an isolated temporary profile: startup,
authenticated loopback HTTP, owner boundary, writable profile, FTS search,
new local concept route, 11-provider presets, missing-consent rejection and clean
shutdown passed. No real stored keys or live provider were used.
Frozen OCR smoke passed bundled-model Chinese/English/mixed recognition, PNG/JPEG/WEBP,
ordered pages, no-text behavior and worker exit. Both were rerun after packaging.
No installation/launch visual QA was performed; that remains human QA.

## Z. HopePrivate and published release

HopePrivate was not accessed or modified. No push, merge, tag, release, upload,
or change/rebuild of published RC6 was performed. Only local development artifacts
were built. Existing v1/v2 installer sizes and SHA-256 values were rechecked unchanged.

## AA. Installer path

`D:\AUniversityLearning\3102\CODING\HopeProject\dist\releases\HopeArchive-0.2.0-ai-v3-dev-Setup.exe`

## AB. Installer size

116,496,648 bytes — 111.10 MiB.

## AC. SHA-256

`464251A5F40282340A2692ADD5DD25051B01E2021BE9243C841FA1DBBADAB5C2`

Preserved v1:
`8120D9BF7FF820E2190E6C25F4875B55890FACB7A88BAE198735B149A77C84F6`

Preserved v2:
`C295695EE0FD4AF1E392EC33D0FED436FBA63D153C73BE4AF0BF70A50521A365`

## AD. Branch

`feature/ai-diary-assistant`. Main/RC6 was not moved.

## AE. Local commits

- `6b350a0` — freeze synthetic corpus and v2 baseline before retrieval changes.
- `9947f54` — measured local concept improvement, isolated experiments, tests and build integration.
- This report is committed separately after artifact verification; its commit ID is
  reported in the task handoff (a file cannot include its own Git commit hash).

## AF. Known limitations

Natural-language recall is still incomplete. Seven local concept families are not
a replacement for semantic retrieval. Broad terms can match negations/plans; no
new model-answer factuality guarantee is implied. The benchmark is small,
development-authored and mostly short positive-query examples, with an explicit
judgment erratum; independent negative/no-evidence sets and long-entry evaluation
are required before shipping embeddings.

Cloud rewrite quality/latency remains unmeasured; only replay and protocol tests
ran. Only E5 was actually benchmarked; BGE was desk-screened. Embedding experiments
lack persistent index migration, token-aware long chunking, calibrated abstention,
optional-download UX and older-CPU tests. No OCR-to-diary association exists.
Frontend visual/interactivity testing and signed-in live-provider QA are postponed.
No fake model pricing, confidence probability or inferred OCR provenance is provided.

## AG. SHIP / EXPERIMENTAL / DEFER

**SHIP in the local v0.2.0 development candidate:** existing FTS + bounded local
concept expansion; optional related-word Search using the shared candidates.
This is a recommendation, not authorization to publish.

**EXPERIMENTAL:** pinned local E5 and both RRF comparisons; question-only rewrite
protocol/replay. Keep them outside the installer and off the production API.

**DEFER:** automatic cloud rewrite, bundled embeddings, persistent semantic index
and model download UI, OCR indexing until validated attachment linkage; all VLM work.

Seven explicit decisions:
1. **Is FTS + aliases enough?** No for general natural questions. Even expanded
   local concepts reach only 0.5836 R@5; they are a safe near-term improvement.
2. **Does query rewrite materially improve recall?** Useful supplied terms do in
   replay; actual configured-LLM benefit is unproven. Do not claim otherwise.
3. **Are embeddings better?** Yes on this synthetic set: E5 R@5 0.8353 versus
   v3 local 0.5836, with the stated limitations.
4. **Is hybrid worth the cost?** V3+E5 at 0.9090 warrants further work, but not
   mandatory runtime/package cost yet. V2 fusion also demonstrated regressions.
5. **Bundle, optional download, or not yet?** Not bundled now; pursue a verified
   optional component after threshold, lifecycle and CPU compatibility work.
6. **Can OCR safely join now?** No: missing validated diary/media linkage.
7. **AI v4 focus?** Independent retrieval/negative-query evaluation, long-diary
   token-aware chunks, no-evidence abstention and a small optional local semantic
   component with download integrity and derived-index lifecycle. Then explicit
   attachment-bound OCR provenance. No psychological profiling or autonomous agents.

## AH. Later human QA checklist — intentionally not performed

- Install v3 separately; verify launch, layout/scaling and update/uninstall behavior.
- Compare literal and local-related search; dates/types, 200-result notice, pagination.
- Try natural questions and inspect plans/negations among retrieved candidates.
- Select exact diaries from both search modes; ensure the AI context remains selected-only.
- Exercise Ask, Review, Timeline, selected mode switching and source-detail navigation.
- Verify privacy disclosure with each configured provider, then cancellation/retry
  and Markdown export under a user-selected root.
- Check offline search/OCR/export and no unwanted network request during local search.
- Confirm existing v1/v2/RC6 artifacts remain untouched.
- Do not publish based solely on automated verification.

