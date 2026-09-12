# Hope Archive v0.1.2-dev

Development / Pre-release · Windows x64

Download the ZIP, extract everything, and run `Hope Archive.exe`. Keep the bundled `hope-archive-backend.exe` beside it. WebView2 is required; Python, Node.js and Rust are not required.

## New since v0.1.1-dev
- Three diary categories and independent time capsule browsing.
- Date-based online diary preview, clear empty/error states and authentication feedback.
- Nickname/date-range combined Markdown, TeX, PDF and Word export.
- Offline SQLite FTS5 archive search with Chinese keywords and filters.
- BYOK provider settings backed by Windows Credential Manager; no archive AI analysis.

## Verification and limitations
- 130 backend tests and 5 frontend tests passed; typecheck/lint/build passed.
- Windows bundle, backend startup, FTS5 smoke and icon checks passed.
- No live AI calls or personal archive data included. Manual native UI and real provider acceptance remain pending.
- Unsigned development build; no auto-update or fresh-machine acceptance claim.
- This ZIP uses the verified build from commit `b39d1125c8552ff6a079b30d179ba68779a021f9`. Embedded Windows version remains 0.1.1; this release tag identifies the newer source milestone.
