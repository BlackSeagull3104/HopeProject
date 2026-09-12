# Local search and secure BYOK

This milestone adds local search and provider settings only. No RAG, vectors, archive chat, summaries, agents, or background AI analysis.

## Offline search

Normalized local JSON → additional SQLite FTS5 index → Python local API → React Search page.

Existing JSON/media remain authoritative and untouched. Select the archive root; no Hope login or Internet is required. Only `diaries.normalized.json` and `capsules.normalized.json` under that root are scanned, not raw responses or arbitrary JSON. Indexes live under `%LOCALAPPDATA%/HopeArchive/search/<root-hash>.sqlite3` (desktop runtime home overrides also apply). They contain private text and are not encrypted; treat them like the source archive. SQLite databases/journals and generated capsule directories are ignored by Git.

Index fields: title, body/rich text, secondary original, comments, diary category label, mood/weather labels; date/category/content type are separate filter columns. Independent time capsules use a separate content type and **creation date**, not an inferred unlock date. Only locally saved opened, non-cleared capsule text is indexed. Unopened/unknown/cleared contents are excluded. Capsule comments not yet present in the archive are not fetched.

FTS5 trigram handles literal keywords of at least three characters, including Chinese substring search. One/two-character queries use local `instr` matching because trigram does not support them. Input is treated as a literal phrase, not SQL or FTS operators. This is substring keyword search, not Chinese linguistic segmentation or semantic search. Date/type filters compose; results page in groups of 50 with snippets and React text-node highlighting (no HTML injection). Clicking a result opens refreshed **local textual detail**, not the online preview. Local media rendering in search details is deferred; use the existing archive files for media.

Initial search creates the index. Later searches scan file metadata (mtime nanoseconds and size), reparse only changed files, and remove entries from missing files. Rebuild refreshes every source transactionally; malformed files cause a clear error instead of false empty results. Archive download and capsule list save attempt an incremental sync; failed indexing never discards a successful archive. Later search/detail sync also detects capsule detail updates. Files changed while preserving both size and modification timestamp require explicit rebuild. Different saved snapshots remain separate results with source paths; there is no destructive cross-snapshot deduplication. Search is scoped to a user-selected local folder, not a remote account.

Local POST routes: `/search/query`, `/search/rebuild`, `/search/detail`. Search and settings intentionally work without a Hope session but retain loopback, Host/Origin/client-header protections and the desktop parent bootstrap credential check. The trusted boundary is the current Windows account; this is not protection from malicious processes running as that same account.

## BYOK and credential boundary

User-entered key → local Python API → Windows Credential Manager → Python provider adapter → configured provider HTTPS endpoint.

`secure_store.py` calls `CredWriteW`, `CredReadW`, `CredDeleteW`, `CredFree` via ctypes. Generic credentials are named `HopeArchive/AI/v1/<provider>` and persist for the current Windows account on this machine. Key, model and base URL are stored together in the OS credential blob, **not in plaintext JSON files**, .env, archives, SQLite, or frontend storage. Non-Windows or unavailable secure storage produces an error and has no plaintext fallback. Replacing overwrites that provider credential; deleting removes its key and settings. This round supports one configuration per preset and one custom configuration.

Newly typed secrets necessarily exist briefly in the masked React input and local request body. The input is cleared on save/test/delete and when switching provider/page. Saved secrets are never fetched into React, prefilled, placed in localStorage/sessionStorage, returned by APIs, or logged. Python retrieves them only for settings operations/provider calls. Python immutable strings cannot promise forensic zeroization of all memory; ctypes native buffers are cleared before release. No crash-report collection was introduced.

Standard preset URLs are fixed; custom URLs must use HTTPS without user-info, query parameters or fragments. Stored keys are bound to provider and base URL: changing the custom endpoint requires a newly entered key. Redirects are disabled so Authorization cannot follow a redirect. All errors are fixed local text, without raw provider messages/request headers. A user-selected custom service is still an external recipient chosen by the user.

Presets: OpenAI, DeepSeek, Gemini OpenAI-compatibility API, OpenRouter, Custom OpenAI-compatible API. `AIProvider` separates config validation, test and future backend chat; `OpenAICompatibleProvider` handles common REST transport. Model hints are centralized in `ai.py`; users can always type a new compatible model. No bundled/public AI key or free shared account exists.

`POST /ai/test` performs only authenticated `GET <base>/models`, checks whether the selected model is listed, and returns fixed success/warning text. This verifies connectivity/list permission, **not generation capability, billing, or model entitlement**. Some custom providers lack `/models`; the test then reports incompatibility even if chat might work. It does not save a newly entered key; after testing an unsaved key, enter it again to save. No generation or paid calls occur in automated tests.

Other routes: `/ai/presets`, `/ai/status`, `/ai/save`, `/ai/delete`. There is no public chat or embed route. A backend-only chat adapter is present for future integration but not wired to diaries or the frontend. Future analysis will send explicitly selected content to the configured provider; cloud AI is not fully local. Hope Archive runs no intermediate AI service; OpenRouter itself may route to downstream providers according to its service terms.

## Official references checked 2026-09-12

- [SQLite FTS5/trigram](https://www.sqlite.org/fts5.html#the_trigram_tokenizer)
- [Windows CredWriteW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew)
- [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [OpenAI model example](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [DeepSeek OpenAI-compatible API](https://api-docs.deepseek.com/)
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [OpenRouter quickstart](https://openrouter.ai/docs/quickstart)

Presets are convenience hints, not a permanent model-availability guarantee. No real cloud provider connection was tested this round.

## Verification / manual checklist

Synthetic tests cover indexing/update/deletion/rollback, Chinese/short/unusual literal queries, filters/snippets/local detail, safe UI highlighting, provider validation, replacement/deletion, endpoint binding, no plaintext writes or returned/logged keys, and mocked network errors. A separate real Windows Credential Manager smoke test used a unique temporary namespace and synthetic non-key values, then removed the credential.

Manual acceptance remains pending:
1. Without logging into Hope, select your local archive and search Chinese keywords; change filters and open local textual details.
2. Modify a test archive or delete a snapshot, search again, and try explicit rebuild.
3. In AI Settings, select your service and model. Enter your own key only in the app, save, restart, and confirm configured state without key refill.
4. Test connection intentionally, replace/delete the key, and check the other providers remain unchanged.

Do not paste API keys into chat or commit private indexes. No GitHub Release is created by this milestone.
