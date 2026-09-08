# Hope Archive

The current prototype exports only the current user's diaries through the
verified read-only list endpoint. It uses Python 3.10+ and the standard library;
no dependency installation is needed.

## Run (Windows PowerShell)

```powershell
Set-Location 'D:\AUniversityLearning\3102\CODING\HopeProject'
.\.venv\Scripts\python.exe src\hope_archive\main.py --user-id 'YOUR_BACKEND_USER_ID' --begin-date '2026-01-01' --end-date '2026-09-08'
```

Replace the placeholder with your own backend userId and choose your date range.
Dates use YYYY-MM-DD. This prototype does not log in, verify accounts, or accept
authentication values. If the service requires authentication, the request fails;
authentication support is outside this stage.

Optional flags: `--page-size 20`, `--timeout 30` (seconds), `--max-pages 10000`,
and `--data-dir PATH`. The default data directory is this project's `data/`,
regardless of the working directory.

## Data flow and design

1. `main.py` reads CLI arguments and checks the date range.
2. `api.fetch_all_diaries(...)` starts at page 1 and calls
   `api.fetch_diary_page(...)` for each page.
3. Each call POSTs JSON to
   `https://hope.wantexe.com/services/v2/parallellife/period/dairy/list` with
   `beginDate`, `endDate`, `noteType`, `pageSize`, `pageNum`, `type`, and `userId`.
   `type` is always `mine` and cannot be overridden.
4. `storage.py` saves the response body bytes in
   `data/raw/diaries/page_0001.json`, `page_0002.json`, etc. **This happens before
   JSON parsing or response validation.** HTTP error bodies are also saved;
   despite the filename they may not be valid JSON. A network failure with no
   complete body has no raw file. Filesystem failures stop processing.
5. Parsed `datas.list` entries are appended without field transformations.
   Only when their count equals `datas.total` is the full list atomically
   published to `data/processed/diaries.json` and returned by the function.

The CLI uses `noteType=0`, following the default recorded in the earlier source
review. Its enum meaning is not established by the verified field list; no
capsule-specific behavior is implemented. Python callers can pass `note_type`.
Date boundary inclusion is also not assumed. Requests have an explicit timeout
(urllib's blocking socket-operation timeout, not an overall export deadline).
There are no automatic retries.

Pagination requires a nonnegative integer `datas.total` and a list `datas.list`.
Empty pages before the total, repeated pages, changed totals, excessive counts,
invalid JSON/schema, and the page cap cause an explicit failure. Short pages alone
do not stop pagination. No undocumented entry ID or business-status convention
is assumed. Exact repeated pages are detected; overlapping entries across different
pages cannot be reliably identified without a verified unique ID contract. This
is a count-based export, not a server snapshot or synchronization implementation.

Raw files are never overwritten. After any previous attempt, use a new directory
for another export, for example append `--data-dir data/run_002` to the command.
That run writes `data/run_002/raw/diaries/` and
`data/run_002/processed/diaries.json`. Partial raw pages remain available after a
failure; a failed fetch does not replace an existing combined output. Resume and
concurrent exports into the same directory are not supported.

## Offline verification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Tests use synthetic responses in temporary directories and never contact Hope.
They cover pagination, raw byte preservation, failure handling, and overwrite
protection. Live API behavior is not established by these tests.

## Structure and scope

```text
src/hope_archive/
  __init__.py
  api.py          # one-page request and full pagination
  storage.py      # raw and combined persistence
  main.py         # CLI
tests/
  test_diaries.py
data/             # private outputs; ignored by Git
docs/             # earlier planning and source-review notes
```

Earlier planning documents describe broader future work; this implementation is
limited to the read-only diary export requested for this stage. No login, account
verification, security testing, other-user access, GUI, AI summary, semantic search,
PDF export, image download, capsule diary feature, or installer is implemented.
Reference repositories are not modified. Real diaries and raw outputs belong in
the Git-ignored `data/` directory. No credentials are hardcoded or required in files.
