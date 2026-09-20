# RC4: cloud preview and portable archives (not yet released)

The authenticated preview calls the existing Hope diary API one page at a time (20 entries) for the selected date/category. It neither fetches the complete range nor writes a backup. Media is fetched only on request using session-scoped opaque references. Authentication, account eligibility and diary type mappings are unchanged.

The desktop primary action is now **归档日记**. It fetches the selected range, retains raw recovery input, merges the current normalized records, reuses verified downloaded media, and generates the selected readable formats. PDF or Word automatically adds exactly one Markdown document. Partial media failures are visible and can be retried; raw snapshots and prior records are retained. Files already generated before a later export failure remain available; the failed stage is reported.

## Directory ownership

```text
User-selected archive root/
  backup/
    README.txt
    metadata/legacy-migration.json       # only when legacy files exist
    <account hash>/
      raw/<timestamp-unique-id>/         # retained API snapshots for recovery
      normalized/diaries.normalized.json # current merged records
      media/                            # original downloaded media, as needed
      media_manifest.json
      <legacy snapshot>/                # copied recovery inputs, if present
  archive/
    Hope日记_<range>_<unique-id>.md/pdf/docx/tex
    assets/                             # portable MD/TeX images, as needed
    capsules/                           # only after capsule export
    ocr/                                # only after OCR export

%LOCALAPPDATA%/HopeArchive/
  settings.json
  search/<root-hash>.sqlite3             # rebuildable FTS5 index
  work/                                 # temporary transport folders, cleaned per operation
  archives/                             # untouched legacy originals, if present
```

AI secrets remain in Windows Credential Manager; existing AI metadata remains app-owned. `HOPE_ARCHIVE_HOME` is the existing test/deployment override. New desktop diary backups are not placed in the application installation folder. The settings validator rejects a root inside the packaged executable's installation directory.

## What `hope-archive-*` actually was

`application.export_archive()` creates it with `tempfile.mkdtemp(prefix='hope-archive-'+datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=root)`. Despite the tempfile function, these were persistent snapshots: no automatic cleanup occurs. The timestamp labels the run; the random suffix avoids collisions and allows exclusive raw-page writes.

In RC2/RC3 desktop use, `root` was `%LOCALAPPDATA%/HopeArchive/archives/<sha256(userId)>`; an explicit `HOPE_ARCHIVE_HOME` replaced the profile prefix. The full normalized path was `<root>/hope-archive-<timestamp>-<random>/processed/diaries.normalized.json`. Legacy CLI use resolves its explicitly selected output root and creates the same snapshot there; it is not intrinsically a TEMP or installer path.

`application.export_archive()` writes normalized JSON after `api.fetch_all_diaries()` stores raw pages and the combined response. `Library` and `SearchIndex` read the normalized files. FTS5 is a separate derived SQLite index, not the primary diary store. The search serializer previously returned its internal relative `source` column, and React rendered it under both results and details. RC4 retains that column solely for internal index management and excludes it from response JSON and UI.

Repeated old runs accumulated snapshots; deleting them could remove the only diary/media copies, and the next index sync would remove affected search rows. RC4 does not delete them. On settings initialization/save, known legacy recovery inputs under the app-owned `archives` root are copied and verified into `backup`, with receipts for idempotence. Existing different destination files are never overwritten; conflicts are reported, and originals remain. Copy failures leave source data intact. Old readable exports are not imported as backup inputs. Arbitrary project/CLI folders are not scanned or removed. The compatibility CLI keeps its old behavior; the desktop no longer calls it for diary archiving.

Current normalized entries are merged by account, diary type and ID. Latest versions replace current records, while raw snapshots remain. Cloud deletions are deliberately not destructive local deletions. Search reconciles logical identities across migrated snapshots/current records so repeated updates do not duplicate results; unchanged source stamps avoid rebuilding the index.

## Canonical document and image policy

RC3's `document.diary_blocks()` remains the canonical ordered presentation stream. Markdown consumes it directly; PDF, Word and TeX use the shared resolving adapter. The disk Markdown file is not the authoritative intermediate. Source paragraphs, metadata, comments and media order remain shared.

`image_layout.py` owns image classification and physical rows. Its single-image width fractions match the approved Markdown styling: long 38%, portrait 46%, regular 55%, landscape 65%. Long means height/width >= 2.5; portrait width/height < 0.85; landscape > 1.35. PDF/Word/TeX pair adjacent images when each ratio is 0.85–2.2 and each intrinsic width is at least 144 pt. Pair height is capped at 200 pt with a 12 pt gap. Single portrait height is at most 300 pt, other singles 260 pt. Source pixels use 96 dpi; no enlargement, stretching, cropping or slicing. Markdown retains its previously approved responsive row grouping and CSS max-height, while consuming the shared classification/width policy.

PDF and Word use A4 with 56 pt side margins and 54 pt top/bottom margins. Word uses fixed-width tables for pairs with no cell padding, no row splitting, clear heading levels and subdued indented comments. TeX maps the same rows into explicit point dimensions with `keepaspectratio` and 12 pt pair spacing; its 25 mm margins give 453.54 pt available width. The `ctexart`/Fandol source is LuaLaTeX-compatible. No TeX compiler is needed by the application.

Markdown preserves original image bytes under `archive/assets`; TeX uses oriented PNG assets there. All links are relative to the exported archive. PDF/Word embed images. Copying `archive` without `backup`, AppData or the installed application remains supported.

## PDF engine decision

| Option | Assessment for this application |
|---|---|
| Existing ReportLab | Already bundled/offline; deterministic generation, tested CJK embedding, A4 and controlled shared image rows. Less browser-CSS fidelity, but no new runtime or IPC path. BSD license. Selected. |
| Existing WebView2 HTML/CSS → PDF | Best CSS fidelity without another browser. Native `ICoreWebView2_7::PrintToPdf` supports asynchronous noninteractive output. Tauri 2.11.5 exposes native access through `with_webview`; its ordinary `print()` has no output-file/completion API. Current export jobs live in the Python sidecar. Adoption would require a dedicated document webview, safe HTML/assets protocol, navigation/font/image readiness, COM callbacks, job correlation, timeout/cancellation and app-close handling. Feasible, but not an already reliable export path in this architecture. It also depends on device WebView2 version. Deferred, not claimed to be inherently unsupported. |
| Bundled Chromium | Good HTML/CSS, CJK/system font behavior and offline printing; adds a separate browser runtime, security-update/licensing burden and substantial installer size. Not adopted. |
| Pandoc | Converter alone does not remove the need for a PDF engine; new executable/dependency surface and GPL distribution considerations. No clear gain over the current normalized model. |
| Pandoc + LaTeX | Strong typography, but adds a large font/package/runtime toolchain and maintenance/licensing inventory. Not suitable for this bounded Windows installer change. |
| python-docx / existing dependencies | Appropriate for Word (MIT), not a PDF converter. Retained for DOCX. No Office or LibreOffice dependency. |

Actual PDF pipeline: normalized diary → canonical blocks → resolved images/shared physical rows → ReportLab → PDF. It does not use WebView2 printing, a browser, Pandoc or a TeX compiler. The app UI retains its existing WebView2 runtime requirement; this change adds no runtime or Python/npm dependency. Measured installer delta is recorded in the local RC4 manifest/report rather than estimated here.

Primary API references: [Microsoft PrintToPdf](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2_7), [Tauri webview versions](https://v2.tauri.app/reference/webview-versions/). The installed Tauri 2.11.5 source was also inspected (`webview/mod.rs`, `print` and `with_webview`).

## Validation boundaries

Synthetic tests cover authenticated/unauthenticated cloud preview, filters/pages/errors, migration safety, one-click multi-format generation, media reuse, partial failure, FTS deduplication/path removal, and moving an archive while the backup is unavailable. Packaged verification uses an external, no-forwarding HTTPS fixture server, trusted only by the spawned test process; no test server, CA or synthetic account fixture is included in the installer. Live Hope account acceptance and actual Word/TeX viewer acceptance remain manual QA. Very long screenshots retain full content but may need zoom.
