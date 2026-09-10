# Repository cleanup — 2026-09-10

## Scope and preservation

Root: `D:\AUniversityLearning\3102\CODING\HopeProject`.

The frontend had a hidden, independent `frontend/vite-app/.git` directory with an initial commit. The root index had no frontend gitlink (mode 160000) and no submodule configuration. A verified Git bundle of the frontend history was saved outside the project before removing only this nested metadata directory. All frontend working files remain in place.

Running `git -C frontend/vite-app rev-parse --show-toplevel` now resolves to HopeProject. Source files are added directly to the root index as regular files. No history rewrite, submodule creation, or source deletion is required.

File hashes before/after cleanup verified that Python source, React source, tests, package manifests, lockfile and frontend configuration did not change. The pending React/local API implementation from the previous task is included as-is. The newly supplied `docs/ROADMAP.md` is retained unchanged; its plans are not implemented in this cleanup.

## Ignore rules

Replaced the broad `/data/*` rule with explicit exclusions for raw, processed, archive, archive_*, architecture_verification, markdown*, media and exports directories. Existing generated hope-archive-* runs remain ignored. The current three data subdirectories contain local archive/verification output and are not needed as checked-in test fixtures. `data/.gitkeep` remains tracked; safe future fixtures/examples can be reviewed and added.

Added `private/` and `tokens*.json`. Existing exclusions cover .env/.env.* (allowing .env.example), sessions/auth/cookies JSON, .venv, Python caches, node_modules, dist, TypeScript caches, APK/APKS/XAPK, HAR/CHLS/CHLSJ, JADX/decompiled/Charles/captures, databases and editor/OS noise. The frontend .gitignore is preserved.

## Content audit

Reviewed tracked and candidate source, docs, tests and configuration, including authentication-related keywords and credential-shaped literals. Checked all four commits reachable from the original main (56 unique historical file blobs). Known local protocol values were compared in memory without printing them. Contextual matches in public protocol identifiers and npm dependency declarations were distinguished from credential assignments; synthetic auth fixtures are not real accounts.

No real account credential, full personal login response, diary export, capture, APK/JADX artifact, large binary or bundled dependency directory was found in the publishable files/history inspected. Notebook cells contain no outputs, execution counts or attachments. Authentication fixtures use fixture-* or other explicitly synthetic values. .env.example has empty configuration values. No actual .env or private archive is staged.

The older publication-audit.md records an abandoned local commit containing protocol values. It is not reachable from the main branch being published; reflogs/unreachable objects are outside the push. Do not publish the entire local .git directory or a ZIP of the working directory. This review covers Git content being published, not every remote ref, GitHub attachment, or every possible secret format.

## Validation

- Python: 80 tests passed, zero failures (including existing UI tests).
- Frontend: npm install completed without changing package.json/package-lock.json.
- npm run build, npm run lint and npm run typecheck passed.
- The existing Vite __dirname future-loader warning and libpng fixture warning are non-blocking; no unrelated code change was made.
- Source preservation was verified with SHA-256 hashes.

## Publication procedure

Review root git status, unstaged diff and staged diff. Verify the index has regular frontend source files, zero mode-160000 entries, no generated/private/artifact paths and no unexpected deletion. Commit the reviewed integration and cleanup on main, then push only main to the configured origin without force. If the remote diverges, stop rather than replacing remote history.

The expected origin is `https://github.com/BlackSeagull3104/HopeProject.git`. Commit hash and actual push result are reported after these operations, outside this document to avoid a self-referential commit hash.
