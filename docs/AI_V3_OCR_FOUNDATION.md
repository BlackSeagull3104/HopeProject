# OCR evidence foundation — design only, not an enabled feature

## Observed v2/v3 boundary

`OCRJobs.start` accepts exactly image `name` and base64 `data`, at most 20 images.
It starts a disposable local RapidOCR worker, retains the current job in memory,
and clears the previous document when the next job starts. The user can edit and
export OCR pages. There is no diary/account/media identity in this input or job.

Normalized diary content has media `file_id`, URL and display name; the archive
media manifest resolves downloaded media. Neither structure contains a trusted OCR
result link. Current FTS concatenates diary/title/comment text into one body, so
even `comment_text` is not independently attributed in current citations.

Decision: do not index arbitrary OCR exports or match image filenames to diaries.
Do not invent parent dates or assume that a standalone image came from this archive.
No OCR/VLM model, OCR runtime, normalized schema or source data was changed by v3.
Test coverage rejects invented parent fields and ensures an unrecognized `ocr_text`
field cannot quietly enter the diary index.

## Proposed future evidence record (NOT today's persisted schema)

| Field | Contract |
| --- | --- |
| source kind | `diary_text`, `comment_text`, `ocr_text`; never collapse OCR to authored text |
| account scope | server-resolved archive/account scope, not a client path |
| parent diary identity | existing stable diary identity, resolved in active scope |
| parent date | resolved from normalized diary, never inferred from an image name |
| media identity | server-resolved attachment identity within that diary |
| text | OCR output or explicitly corrected output, stored separately from normalized originals |
| revision | image content digest + OCR model/config version + correction revision |
| chunk identity | hash of scope/diary/media/kind/chunk offset/content revision |
| provenance | local OCR, automatic vs user-corrected, engine version; optional engine confidence, not truth probability |

Before indexing, add an explicit “recognize this diary attachment” entry path.
The server must resolve the selected media ID against the parent diary; never accept
an arbitrary filesystem path. Shared media appearing in two diaries needs two
validated parent associations, not guessed ownership. Recheck association after
deletion/re-download, reject stale IDs and keep errors isolated from diary indexing.

## Storage and invalidation

Derived OCR search chunks go in a separate, versioned internal index per archive,
not `backup/raw`, `backup/normalized`, or human-readable exports. Preserve any
user-corrected OCR derivative separately with explicit user semantics before calling
it rebuildable: an automatic rerun cannot recreate human corrections.

Source image/date/parent deletion removes dependent chunks. Image digest/model or
recognition configuration changes invalidate automatic OCR. A derived index rebuild
reads existing normalized diaries and validated derivative OCR records; it never
re-downloads or overwrites source diaries. Failed OCR leaves diary search usable.
Migration should create separate tables/sidecar and roll back independently; no
schema migration was introduced in v3.

## Citation and uncertainty contract

Future citation: `2026-09-12 · 日记图片文字识别` plus the existing safe diary-detail
link and an attachment identifier resolved on the server. No image paths/URLs,
internal database paths, account IDs or raw request payloads in model context/UI.
Grounding must explicitly label OCR chunks and say recognition can be wrong. An
answer should say “图片识别文字中出现…” rather than “你写道…”. Authored and OCR
sources must retain distinct markers through hierarchical synthesis and exports.

Required future acceptance tests: validated parent/media binding, account/date/type
and selected-source filters, OCR-only retrieval, mixed-source citation distinction,
stale/deleted media removal, engine failure isolation, corrected-text preservation,
safe rebuild/migration, path redaction, and no image transmission to any provider.
VLM/image understanding remains out of scope and disabled.
