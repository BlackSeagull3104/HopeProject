# Optional local Hybrid retrieval — 0.2.0-alpha.1 candidate

This is experimental development software. Publication is conditional on the release
gates; this document alone is not release approval. Full human AI/provider QA has
not been performed.

## Two product modes

- **FTS5**: available immediately without download, provider configuration or API key.
  The existing SQLite trigram index and deterministic v3 alias/concept expansion
  provide diary relevance ranking. Short Chinese terms retain literal matching.
  Search's “全部内容” and capsule filters retain original literal/date-sorted search.
- **Hybrid**: optional FTS5 + locally generated semantic vectors. The UI switches
  Search to diary scope; no pure embedding mode is exposed. Ask and Timeline have
  the same two choices. Review, Selected Diaries and source-locked follow-ups keep
  their explicit source scopes, regardless of retrieval mode.

Modes are page/session-local, default FTS5. Switching the AI retrieval mode clears
the previous conversation to avoid carrying evidence between different retrieval
policies. No cloud query rewrite or remote embeddings are used.

## Audited model and runtime

The v3 experiment's model is unchanged:

- Model: `intfloat/multilingual-e5-small`.
- Revision: `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Artifact: `onnx/model_qint8_avx512_vnni.onnx` (downloaded as `model.onnx`).
- License: MIT, as declared in the [pinned official model card](https://huggingface.co/intfloat/multilingual-e5-small/raw/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md).
- Encoder: CPUExecutionProvider, ONNX Runtime 1.30.0, tokenizers 0.22.2,
  NumPy 2.5.3; two intra-op threads, `query:` / `passage:` prefixes,
  masked mean pooling, normalized 384-dimensional float32 vectors.
- No GPU, Torch or vector database. Inference is fully offline after installation.
- The specific quantized graph has been exercised on this Windows x64 Intel CPU;
  this is not validation of every older Intel/AMD processor. Unsupported runtime
  behavior falls back to FTS5. See [ONNX Runtime quantization guidance](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html).

| File | Download / installed payload bytes | SHA-256 |
| --- | ---: | --- |
| model.onnx | 118,346,824 | `dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88` |
| tokenizer.json | 17,082,730 | `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39` |

Total payload: **135,429,554 bytes (129.16 MiB)**. These are two direct files,
not a compressed component archive; no invented ZIP/compressed-size estimate.
Disk use additionally includes indexes and filesystem overhead. Failed staging
directories are cleaned up; successful previous model generations are retained,
so repeated explicit downloads can consume additional disk space.

The model is not in the base installer. The existing OCR runtime already includes
ONNX Runtime and NumPy; its executable gains an explicit `--semantic` worker
entry point and the small tokenizer dependency. Normal OCR invocation is unchanged.
This shares packaged libraries, not an OCR inference session or OCR content.
The lightweight backend imports no neural runtime. Runtime dependency licenses
are collected in the existing third-party notice inventory, including tokenizers.

## Component lifecycle and integrity

Opening Search or selecting Hybrid does **not** download anything. The disclosure
shows model name, approximate bytes, local-only processing and abstract storage
location. Only “下载并启用” posts `confirmed: true` to the install endpoint.

States: not installed → downloading → verifying → installed → indexing → ready;
download failed, verification failed, index failed, and rebuild required are
explicit states. Installation immediately queues initial indexing. Installed is
a transitional state; it may pass between UI polls.

Downloads use fixed, pinned HTTPS URLs with normal certificate verification,
streaming byte limits, per-connection timeout and an overall time bound. They are
written to a separate staging generation, checked for exact length and SHA-256,
then renamed and activated using an atomic pointer replacement. A failed download
never replaces an earlier installed generation. The HTTP primitive is the same
standard-library mechanism used elsewhere; the archive/media downloader itself
is deliberately not reused because it owns archive/assets semantics.

Model files are verified again before loading a worker. File size/mtime changes
invalidate a cached worker and force verification. Runtime failures, invalid
vectors and corrupted indexes cannot be represented as a successful Hybrid result.
The UI reports “语义检索暂时不可用，已使用 FTS5 完成本次搜索。”

## Derived storage and indexing

The desktop runtime home contains `semantic/`, separate from source `archive/`
and `backup/`. Models use immutable generations; indexes use a SHA-256 of the
resolved, case-normalized archive/account root. Metadata includes model identity,
version, pooling/chunk policy, dimension, index schema and root scope hash.
No source filesystem path, provider configuration or API credential is stored in
index metadata or returned by semantic status/search APIs.

SQLite stores fingerprints and per-diary chunk vectors/text. This is a disposable
derived cache, **not encrypted** and potentially sensitive like the FTS cache.
Deleting/rebuilding it does not modify normalized JSON. The existing SearchIndex
is the sole normalized-data reader and stable-ID authority: duplicates and account
scope retain its existing behavior, and capsules never enter semantic indexing.

Each changed/new diary is re-embedded, unchanged fingerprints reuse vectors,
deleted diaries lose their vectors, and model/schema changes cause rebuilding.
Updates are transactional. Explicit rebuild recovers a corrupt scoped database.
Changed archives are detected before retrieval; the UI requests index update and
uses FTS5 until that update completes. Index updates are explicit, not background
jobs that silently read newly selected archives. A diary over 500,000 characters
fails semantic indexing safely rather than allocating unbounded inference work.

Token-aware chunks cover up to 480 original tokens with 48-token overlap. Original
Unicode offsets preserve text; prefixes/special tokens are re-encoded and checked
against the 512-token model cap. The production long-entry test verifies that a
unique tail marker survives beyond the first context. The benchmark's short
diaries are still single chunks.

## Ranking and AI integration

Both lists are date/type filtered before fusion. Per-diary semantic score is the
maximum cosine score of its chunks. Equal reciprocal-rank fusion is exactly the
v3 formula: `sum(1 / (60 + rank))`, deduplicating each list, stable-ID tie breaking.
There are at most 200 candidates from each leg and 200 displayed diary candidates,
paged in groups of 50. No learned weights or new reranker.

The best semantic passage feeds the existing bounded AI chunk builder; citations
retain the full diary's stable ID and source navigation opens the original entry.
Ask retains eight-chunk / 12,000-body-character caps, bounded history and consent.
Timeline sorts the retrieved evidence chronologically. Review and Selected
delegate unchanged to existing range/selected methods and never invoke semantic
retrieval. API metadata tells the frontend whether Hybrid actually ran or fell back.
Provider adapters and Credential Manager are untouched. Only a separately requested,
consented BYOK generation step sends bounded evidence to the configured provider.

Semantic retrieval returns candidate similarities, **not a calibrated relevance or
truth probability**. There is no validated general no-evidence threshold. Negative
questions can retrieve unrelated neighbors, and negations/plans can resemble
completed events. An exploratory synthetic negative-query check confirmed this
limitation. AI retains its grounding/insufficient-evidence contract, but provider
adherence is not guaranteed. Do not treat candidates or generated timelines as
proof that an event occurred. This remains a priority for independent evaluation.

## Experiment versus production measurements

Frozen v3 data: 60 fictional diaries, 80 manually judged questions, dataset SHA-256
`6b508fac6c757fcc44f310a3395fc3940012c589df4c3d21e2d2ede00e8aaa50`.
Same labels, queries, filters and macro-recall/MRR definitions as v3. This is a small
developer-authored diagnostic set, not a held-out claim about user accuracy.
The documented q69 labeling limitation remains unchanged.

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| v3 FTS5 concepts reference | .3567 | .5151 | .5836 | .5421 |
| v3 embedding experiment | .5078 | .7647 | .8353 | .8281 |
| v3 Hybrid experiment | .5533 | .7976 | .9090 | .8663 |
| Production FTS5 | .3567 | .5151 | .5836 | .5421 |
| Production Hybrid | .5933 | .8162 | .9160 | .8983 |

Production uses the actual persisted index and normalized-derived body (including
title/type fields already included by SearchIndex), whereas the experiment encoded
`original_text` only. Stable IDs also differ from short synthetic IDs in tie
breaking. These explain implementation differences; no label or fusion tuning was
performed. Overall Hybrid did not materially regress. Per-query ranks remain in
the generated report; an aggregate improvement is not an every-query guarantee.

Production run on this machine: new model session 1,033 ms; 60-diary index 284 ms;
unchanged index 2.92 ms; one changed diary 8.69 ms; SQLite semantic index 180,224
bytes; peak working set 519,327,744 bytes (495.27 MiB). Warm-query mean/p95:
FTS5 1.36/1.51 ms; Hybrid 12.39/12.13 ms (the mean includes first-query verification).
The benchmark directly hosts the same encoder to measure native RAM; these timings
exclude private-pipe IPC and full desktop UI costs. Frozen-worker smoke separately
tests actual process transport. Cold means a fresh session, not a disk-cache flush.

A final rerun while packaging/tests were running returned the same ranking metrics:
1,210 ms new session; 504 ms build; 11.13 ms unchanged; 29.81 ms one change;
519,352,320-byte peak; FTS5 mean/p95 1.92/2.43 ms and Hybrid 20.88/29.77 ms.
This variation is why these are observations, not product latency guarantees.

Prior experiment: 810 ms cold session; 253 ms/60 diaries; mixed short query/passage
inference mean/p95 3.67/4.97 ms; peak 452.02 MiB; 92,160 bytes of raw vectors only,
not a durable database. Production SQLite overhead and stored text are now included.
Index build scales with changed token count; exact vector scan is O(chunks × 384),
and snapshot/fingerprint validation scans diary evidence. No large-archive latency
guarantee or approximate-nearest-neighbor scaling claim is made.

Reproduce with `benchmarks/retrieval_v3/production.py --model <verified-local-model>
--output <report.json>`. The evaluator only creates synthetic temporary archives.

## Automated checks and outstanding QA

Backend tests cover explicit consent, component failures, integrity, transactional
incremental update, deletion, corruption/version rebuild, filters, account/root
isolation, no provider/network on retrieval, metadata, fallback, AI citations and
Review/Selected isolation. Mounted React smoke covers the two modes, explicit
download, progress/failure states, fallback, source navigation, selected handoff,
provider-empty state and the non-error experimental notice. Frozen tests exercise
actual CPU inference without repository imports, FTS fallback, same-size component
corruption and shutdown. Core exporter files remain identical to RC6/main.

Still requires human QA: AI interactions and live providers; accessibility and
layout across screen scales; older CPU/AMD performance; large personal archives;
download interruption/retry UX on varied networks; clean install/update/uninstall.
