# 0.2.0-alpha.1 — implementation / release-gate report

2026-09-24. **Local candidate; not published.** Automated checks are not human AI QA.

## A. Recovered starting Git state

Branch `feature/ai-diary-assistant`, starting HEAD `c216adc96d950728f3c37d28d8f3f3e226421f87`.
Local main, origin/main and peeled RC6: `154fd9211cb9bcb1c7a1b63e34059bfdf3453414`.
A read-only remote-ref check independently confirmed main/RC6 and no 0.2.0 tag.
The existing user story edit was preserved, then separately committed after explicit
user confirmation that it could be public. No other existing edits were overwritten.

Actual AI history inspected: `7fecec5`, `d7cc343`, `a5d9809`, `fb5acb5`, `31bb3ab`,
`1bea3bb`, `082c87d`, `061a909`, `6b350a0`, `9947f54`, `e118f3a`, `c216adc`.

## B–H. Experiment audit, model, size, memory and performance

Read the complete v3 report and actual experiment before implementing. Same pinned
official E5 model/quantized artifact, MIT model-card declaration, CPU runtime,
prefixes, pooling and RRF policy. No arbitrary replacement model.

Download/installed model payload: 135,429,554 bytes / 129.16 MiB; direct files, not
a compressed archive. GPU not required, offline after download. Exact model hashes,
source/license links, runtime versions and known CPU-compatibility limits are in
[HYBRID_RETRIEVAL.md](HYBRID_RETRIEVAL.md).

Final concurrent-load run: 1,210 ms cold session, 504 ms/60-diary build, 11.13 ms
unchanged, 29.81 ms one changed entry, 519,352,320-byte peak working set. FTS5
query mean/p95 1.92/2.43 ms; Hybrid 20.88/29.77 ms. Earlier less-contended run:
1,033 ms cold, 284 ms build, Hybrid mean 12.39 ms. Query timing includes retrieval,
not only encoding; historical v3 short-input encoder mean/p95 was 3.67/4.97 ms.
No large-user-archive or every-CPU performance guarantee.

## I–O. Index, FTS5, Hybrid, fusion, lifecycle, integrity, fallback

New persistent SQLite derived index, root/account hash scope, model/schema metadata,
384-float chunk vectors, original chunk text and diary fingerprints. Benchmark
index 180,224 bytes. Incremental add/change/delete; explicit update and corruption
rebuild; transactions preserve previous data on failed indexing. Normalized JSON
and existing stable-ID logic remain authoritative. Long texts use token-aware
480-token windows / 48 overlap, not first-512-token truncation.

FTS5 remains default and requires no semantic component. Hybrid combines at most
200 filtered candidates from each leg with equal RRF `1/(60+rank)`, deterministic
ties. No pure-embedding UI. Component lifecycle and failures are surfaced; no
automatic download on page open/mode selection. Fixed HTTPS downloads, exact size
and SHA-256 verification, staging generation and atomic activation. The real
upstream download succeeded after an initial transient TLS failure, without
disabling certificate checks. Same-size corruption and incomplete vector data
trigger visible FTS5 fallback, not a false Hybrid success.

## P–R. Search, AI integration, development notice

Shared two-mode control with model/size/local-storage/download disclosure. Search
preserves source detail and selected-ID handoff. Ask/Timeline use the wrapper;
Review/Selected/source-locked paths preserve their original restrictions. AI
context limits, privacy consent, provider adapters and Credential Manager remain.

Exact requested Chinese experimental notice appears above provider interaction in
a subtle tinted bordered card; real runtime errors retain destructive styling.
No modal/dismissal/extra confirmation. Found and fixed a directly blocking desktop
IPC integration omission: the Rust allowlist lacked the existing AI workflow
routes; added explicit AI and semantic routes, with a regression test.

## S–T. Privacy and exporter non-regression

All added fixtures/evaluation diaries are synthetic. No live generation/provider
call or real diary upload occurred. Retrieval tests forbid provider/network calls;
metadata has no source paths or credentials. Frozen tests use temporary profiles.
PyInstaller analysis manifests contain no private-project paths or benchmark model
payload; tokenizer appears only in the isolated neural worker, not the backend.
These checks are not a claim to detect every possible secret written into a user's
diary text, nor proof of all future provider behavior.

No HopePrivate source or overlay was read or modified. Used the public build script,
which does not require an overlay. No private material was uploaded.

Both final working-tree diff and branch history relative to main were checked for
`export_markdown.py`, `export_documents.py`, `document.py`, `document_style.py`,
`image_layout.py`, `archive_workflow.py`, `library.py`, `media.py`,
`normalization.py`, `storage.py`, `settings.py`: **no changes**.
RC6 core rendering/archive semantics remain source-identical. OCR packaging gains
an optional worker entry point; existing OCR recognition/export code is unchanged.
AI derivative Markdown output is unchanged.

## U. Benchmark

Same frozen 60-diary/80-query diagnostic set and labels; not universal accuracy.

| Implementation | R@1 | R@3 | R@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Production FTS5 | .3567 | .5151 | .5836 | .5421 |
| v3 experimental embedding | .5078 | .7647 | .8353 | .8281 |
| v3 experimental Hybrid | .5533 | .7976 | .9090 | .8663 |
| Production Hybrid | .5933 | .8162 | .9160 | .8983 |

Production encodes the existing normalized-derived FTS body and uses real stable
IDs, rather than just synthetic original_text/short IDs. Aggregate metrics show no
material regression; no labels or RRF weights were changed. Raw local reports:
`build/ai-hybrid/production.json` and `production-final.json` (not release assets).

## V–X. Automated tests and package verification

- **259 Python tests passed** (234 baseline + 25 new).
- **17 frontend tests passed**, TypeScript typecheck and lint passed.
- Mounted React smoke passed two modes, explicit download, lifecycle states,
  fallback, source detail, selected handoff, notice, provider-empty state.
- Production frontend build and PyInstaller/Tauri NSIS packaging passed.
- Frozen backend: startup, owner boundary, FTS5, v3 concepts, AI consent, 11 provider
  presets and clean shutdown passed.
- Actual frozen CPU worker: installed model Hybrid, scoped filters, no-model and
  same-size-corruption fallback, source immutability and shutdown passed.
- Frozen OCR recognition/format/no-text/exit smoke and executable icon check passed.
- Both candidate installer welcome windows actually launched and were cancelled
  before installation. No existing installation was overwritten.
- **Whole desktop startup/interaction verification is incomplete**: an existing
  installed instance initially held the single-instance identity. After it exited,
  the final candidate was launched with a separate synthetic QA profile and its
  exact executable/window identity was observed. However, the automation helper
  repeatedly reported a minimized window and user-input protection, preventing
  content inspection. The computer-use recovery limit was reached; further UI
  input was stopped. No rendered desktop/backend-interaction pass is claimed.

## Y–Z. Files and documentation

Backend: new `semantic.py`, `semantic_model.py`, `semantic_worker.py`; integration
in `product_api.py`, lifecycle cleanup in desktop/local API. UI: shared
`RetrievalControl.tsx`, `lib/retrieval.ts`, SearchPage and AIAssistantPage.
Packaging: OCR entry, dependency/notices collector, semantic license notice,
build script, Tauri version/lockfile and explicit IPC routes.
Verification: backend semantic tests, frontend Hybrid/updated retrieval tests,
production benchmark, frozen Hybrid smoke and mounted React smoke.
Documentation: README development status, SEARCH_AI link, HYBRID_RETRIEVAL and
this report. User-approved WHY_HOPE_ARCHIVE change is separate.

## AA–AC. Commits, integration and tag

- `e232964`: author-approved story revision, separate local commit.
- `38f7013893766fafbfe4f50aa657663cb6a6f03e`: implementation, tests and packaging.
- Documentation/report commit recorded in final handoff.
- **No main integration, push or tag.** Intended candidate identifier is
  `v0.2.0-alpha.1`; no such tag has been created by this task.

## AD–AI. Artifact and publication record

Candidate: `dist/releases/HopeArchive-0.2.0-alpha.1-Setup.exe`.
Public manifest: `dist/releases/HopeArchive-0.2.0-alpha.1-manifest.json`.
Final installer size: **118,307,474 bytes** (112.83 MiB).
SHA-256: `786c9994d9c7b03fa25b0f3a040b4475e71e823e823519380db1ab4ede2fc385`.
The first QA artifact was retained under `build/ai-hybrid/` before rebuilding with
the last integrity test/fix and bundled model-license notice. It is not a release asset.

**No GitHub pre-release URL; no upload or published-asset download/hash verification.**
The release gate is blocked by incomplete whole-desktop startup verification.
Do not interpret passed unit/backend tests as permission to skip that gate.

Existing v1/v2/v3 installers were rehashed unchanged; RC6 tag/release untouched.

## AJ–AL. Final state, limits and manual QA

Remains on `feature/ai-diary-assistant`; main/origin/main remain RC6. Final local
status is checked after the documentation commit. No published history rewritten.

Known limits: uncalibrated semantic abstention; unrelated nearest neighbors and
negation/plan confusions; diagnostic rather than held-out benchmark; exact vector
scan and full fingerprint checks do not promise large-archive latency; cache text
is not encrypted; previous successful model generations retain disk space;
older CPUs/network conditions not comprehensively tested; unsigned pre-release.

Human AI/provider interaction QA, cross-scale visual/accessibility QA, clean
install/update/uninstall, large personal archives and older CPU testing remain.
Automatic installer/window observations are not human QA. Finish the actual desktop
gate in an uninterrupted, targetable QA window before considering any remote change.
