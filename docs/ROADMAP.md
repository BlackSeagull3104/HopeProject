# Hope Archive Roadmap

> **Target Release:** 2026-09-24  
> **Milestone:** Pre-Mid-Autumn Release  
> **Version Target:** Hope Archive v0.9

---

## 1. Project Goal

Build a complete **local-first Hope Archive application** that enables users to acquire, preserve, browse, search, manage, and export their own Hope data locally.

### Core Scope

The **Pre-Mid-Autumn Release (v0.9)** should support:

- Authentication
- Diary acquisition
- Capsule acquisition
- Local normalized storage
- Date-based browsing
- Diary-type filtering
- Keyword search
- Markdown export
- PDF export
- TeX export
- Basic AI assistance
- React-based desktop-oriented UI
- Windows runnable build

### Out of Scope

The following features are explicitly deferred until after v0.9:

- Companion / 同行者 relationship features
- Social graph
- Advanced analytics
- Cloud synchronization
- Multi-account support
- Complex AI agents

---

## 2. Product Flow

```text
Login
  ↓
Acquire Personal Hope Data
  ↓
Normalize & Store Locally
  ↓
Browse / Filter / Search
  ↓
Preview Diary / Capsule
  ↓
Export
  ├── Markdown
  ├── PDF
  └── TeX
  ↓
Optional AI Assistance
```

> **Core Principle:** Hope Archive must remain fully usable even when all AI functionality is disabled.

---

## 3. Architecture

```text
React + shadcn/ui
        ↓ HTTP
Python Local API
        ↓
Application Layer
        ↓
Auth / Download / Normalize / Search / Export
        ↓
Hope API + Local Archive
```

The target desktop architecture is:

```text
Tauri
├── React Frontend
└── Python Backend Sidecar
```

### Architectural Principles

1. **Local-First**
   - Personal archive data remains local by default.

2. **Frontend / Backend Separation**
   - React handles presentation and user interaction.
   - Python handles Hope communication, normalization, archive operations, search, export, and AI integration.

3. **Stable Internal Data Model**
   - UI components and exporters consume normalized local data rather than depending directly on raw Hope API responses.

4. **AI Is Optional**
   - Core archive functionality must never depend on an LLM or external AI service.

5. **Reproducibility**
   - A fresh clone of the public repository must be runnable without private developer data.

---

# 4. P0 Requirements

## 4.1 Authentication

- [ ] SMS verification-code login
- [ ] Mobile/password login
- [ ] Automatically obtain the current user ID
- [ ] Persist authenticated sessions appropriately
- [ ] Verify authentication behavior through the React UI
- [ ] Handle authentication errors gracefully
- [ ] Ensure credentials and tokens are never committed to Git

---

## 4.2 Diary Acquisition

- [ ] Download diary metadata
- [ ] Download diary content
- [ ] Download diary media
- [ ] Normalize diary data
- [ ] Store normalized diaries locally
- [ ] Reverse engineer all three diary types
- [ ] Determine the exact mapping between API data and diary types
- [ ] Verify all three types using an authorized personal account
- [ ] Add tests for diary acquisition and normalization

---

## 4.3 Capsule Acquisition

- [ ] Identify capsule API endpoint(s)
- [ ] Understand capsule pagination
- [ ] Identify capsule content fields
- [ ] Identify capsule media fields
- [ ] Download capsule data
- [ ] Download capsule media
- [ ] Normalize capsule data
- [ ] Store normalized capsules locally
- [ ] Browse capsules through the UI
- [ ] Export capsules

---

## 4.4 Browsing

Users should be able to inspect archived content before deciding whether to export it.

- [ ] Browse diaries by date
- [ ] Calendar / date picker
- [ ] Diary list view
- [ ] Diary detail view
- [ ] Display diary text
- [ ] Display media
- [ ] Display emotion
- [ ] Display weather
- [ ] Display comments
- [ ] Loading state
- [ ] Error state
- [ ] Empty state

---

## 4.5 Filtering

Support:

- [ ] All diaries
- [ ] Diary Type A
- [ ] Diary Type B
- [ ] Diary Type C
- [ ] Date range
- [ ] Combined diary-type + date filtering

> Replace `Type A / B / C` with their final semantic names once reverse engineering is complete.

---

## 4.6 Search

### Search v1

- [ ] Keyword search
- [ ] Search-result snippets
- [ ] Highlight matched text
- [ ] Date-range filtering
- [ ] Diary-type filtering
- [ ] Search result → diary detail navigation

### Constraint

> Do **not** introduce a complex search engine unless archive scale demonstrates that one is necessary.

---

# 5. Export System

## 5.1 Markdown

Reuse and stabilize the existing Markdown exporter.

- [ ] Connect exporter to the React UI
- [ ] Export a single diary
- [ ] Export a date range
- [ ] Export comments
- [ ] Maintain stable media paths
- [ ] Maintain stable file naming
- [ ] Optional YAML front matter
- [ ] Verify exported archive portability

### Done When

A user can export selected archive content into a self-contained, readable, and portable Markdown archive without broken media references.

---

## 5.2 PDF

Build a stable PDF export pipeline.

- [ ] Chinese font support
- [ ] Consistent typography
- [ ] Image scaling
- [ ] Horizontal image handling
- [ ] Vertical image handling
- [ ] Multi-image layout
- [ ] Long screenshot handling
- [ ] Correct page breaks
- [ ] Comment layout
- [ ] Date/title metadata
- [ ] Export regression tests where practical

### Done When

Representative diary entries—including text-heavy, image-heavy, multi-image, and long-screenshot cases—produce readable PDFs without major layout failures.

---

## 5.3 TeX

Generate an editable TeX archive rather than hiding formatting decisions from advanced users.

- [ ] Generate `.tex`
- [ ] Provide a default template
- [ ] Generate/reference an assets directory
- [ ] Support media
- [ ] Include date/title metadata
- [ ] Support Chinese text
- [ ] Verify XeLaTeX compatibility
- [ ] Document compilation instructions
- [ ] Document basic template customization

### Principle

> Hope Archive generates a usable default TeX document while preserving the `.tex` source so advanced users can customize the final output themselves.

---

# 6. AI Features

AI functionality is secondary to archive reliability.

## P0 Minimum

- [ ] Summarize selected diary content

## Stretch Goals

- [ ] Semantic retrieval
- [ ] Natural-language archive search
- [ ] Natural-language archive query

### Constraints

Do **not** build:

- Multi-agent architecture
- Autonomous agent workflows
- Complex orchestration
- AI-dependent archive operations

> The archive must remain fully usable without AI.

---

# 7. Frontend

### Stack

- Vite
- React
- TypeScript
- shadcn/ui

### Required Interfaces

- [ ] Login UI
- [ ] Main navigation
- [ ] Archive page
- [ ] Diary browser
- [ ] Diary detail
- [ ] Search page
- [ ] Capsule page
- [ ] Export UI
- [ ] Loading states
- [ ] Error states
- [ ] Empty states
- [ ] Final navigation cleanup
- [ ] Brand/icon integration

### UI Principle

Before **2026-09-24**:

> **Functionality and consistency take priority over further visual experimentation.**

---

# 8. Windows Application

## 8.1 Development Run

- [ ] Create `run.ps1`
- [ ] Start Python local API
- [ ] Start React frontend
- [ ] Open the local application
- [ ] Provide clean setup instructions

## 8.2 Desktop Packaging

Target architecture:

```text
Hope Archive.exe
      │
      ▼
    Tauri
   /     \
React   Python Sidecar
             │
             ▼
         PyInstaller
```

### Tasks

- [x] Production React build
- [x] Tauri shell
- [x] PyInstaller Python backend build
- [x] Python sidecar integration
- [x] Application icon integration
- [x] Windows runnable application
- [ ] Fresh-machine / fresh-environment verification
- [x] Optional installer
- [x] GitHub Release

---

### Early infrastructure milestone — 2026-09-10

The v0.1.1-dev installer infrastructure builds a complete Windows x64 NSIS package with bundled backend-only application protocol constants. Installation outside the repository, native React UI, automatic sidecar, communication and relaunch were observed. The user manually confirmed successful login. After closure no application/backend processes remained; duplicate launch did not add another backend group.

This records an early development distribution milestone only. The scheduled 2026-09-23 final packaging milestone and fresh-machine verification remain open. No unrelated product features are marked complete.

# 9. Implementation Schedule

## 2026-09-10 — Freeze Current Baseline

### Goal

Establish a clean, reproducible, and version-controlled starting point.

### Tasks

- [ ] Unify Git repository
- [ ] Verify backend tests
- [ ] Verify frontend build
- [ ] Verify lint
- [ ] Verify typecheck
- [ ] Commit current stable baseline
- [ ] Push to GitHub
- [ ] Add `docs/ROADMAP.md`
- [ ] Freeze further icon / visual iteration

### Deliverable

A clean baseline commit from which all subsequent milestones can proceed.

### Done When

The repository can be cloned, installed, tested, and built from documented instructions without relying on untracked developer state.

---

## 2026-09-11 — Reverse Engineer Diary Types

### Goal

Identify the exact API behavior and representation of all three diary categories.

### Tasks

- [ ] Trigger each diary type in the official client
- [ ] Compare captured requests
- [ ] Compare response structures
- [ ] Inspect JADX if necessary
- [ ] Identify endpoint differences
- [ ] Identify parameter differences
- [ ] Identify response-field differences
- [ ] Document diary-type mapping
- [ ] Implement constants / enums / types
- [ ] Add tests

### Deliverable

```text
docs/diary-api.md
```

### Done When

All three diary categories can be reliably distinguished from acquired data.

---

## 2026-09-12 — Capsule Reverse Engineering

### Goal

Establish a reproducible capsule acquisition pipeline.

### Tasks

- [ ] Find capsule endpoint(s)
- [ ] Determine request parameters
- [ ] Understand pagination
- [ ] Identify content fields
- [ ] Identify media fields
- [ ] Save representative raw responses locally
- [ ] Build capsule downloader
- [ ] Test with an authorized personal account
- [ ] Document findings

### Done When

Capsules can be programmatically acquired from the user's own account and stored for normalization.

---

## 2026-09-13 — Freeze Data Model

### Goal

Reach approximately **80% schema stability** before UI and export integration.

### Tasks

- [ ] Define normalized diary schema
- [ ] Define normalized capsule schema
- [ ] Normalize media representation
- [ ] Normalize comments
- [ ] Normalize metadata
- [ ] Stabilize archive directory structure
- [ ] Consider migration compatibility
- [ ] Add schema / normalization tests

### Principle

> After this milestone, avoid unnecessary schema changes.

### Done When

Browsing, search, and export layers can depend on the normalized schema without routinely requiring structural changes.

---

## 2026-09-14 — Date-Based Diary Browser

- [ ] Calendar / date picker
- [ ] Query diaries by date
- [ ] Diary list
- [ ] Diary detail
- [ ] Media display
- [ ] Comment display
- [ ] Emotion/weather metadata
- [ ] Empty state
- [ ] Loading state
- [ ] Error state

### Done When

A user can select a date and inspect the corresponding archived diary entries entirely through the React UI.

---

## 2026-09-15 — Diary-Type Filters

- [ ] All diaries
- [ ] Type A
- [ ] Type B
- [ ] Type C
- [ ] Combine type filtering with date queries
- [ ] Verify filtering against known examples

### Done When

Each known diary type can be independently selected and combined correctly with date-based browsing.

---

## 2026-09-16 — Search v1

- [ ] Keyword search
- [ ] Search snippets
- [ ] Highlight matches
- [ ] Date-range filtering
- [ ] Diary-type filtering
- [ ] Search result → diary detail navigation

### Constraint

> Keep search simple until archive scale demonstrates a need for more advanced infrastructure.

### Done When

A user can locate a known diary using a keyword and navigate directly from the result to the corresponding entry.

---

## 2026-09-17 — Markdown Export

- [ ] Stabilize existing exporter
- [ ] Connect exporter to React
- [ ] Single-entry export
- [ ] Date-range export
- [ ] Stable media paths
- [ ] Comments
- [ ] Stable naming
- [ ] Optional YAML front matter

### Done When

A user can select content through the UI and obtain a portable Markdown archive with valid media references.

---

## 2026-09-18 — PDF Export

- [ ] Stable PDF conversion pipeline
- [ ] Image sizing
- [ ] Horizontal image handling
- [ ] Vertical image handling
- [ ] Multi-image layout
- [ ] Long screenshot handling
- [ ] Page breaks
- [ ] Chinese fonts
- [ ] Comments
- [ ] Representative export tests

### Done When

Representative archive entries export successfully without broken Chinese text, missing images, or severe layout failures.

---

## 2026-09-19 — TeX Export

- [ ] Generate `.tex`
- [ ] Default editable template
- [ ] Assets directory
- [ ] Media support
- [ ] Metadata
- [ ] Chinese support
- [ ] XeLaTeX compatibility
- [ ] Compilation documentation
- [ ] Customization documentation

### Done When

A generated archive compiles successfully with XeLaTeX and remains straightforward for advanced users to edit.

---

## 2026-09-20 — AI Minimum Feature

### P0

- [ ] Summarize selected diary content

### If Time Permits

- [ ] Semantic search
- [ ] Natural-language archive query

### Constraint

> Do **not** build an agent system.

### Done When

A user can explicitly select archive content and request a useful summary without making AI a dependency of the archive workflow.

---

## 2026-09-21 — Capsule UI

- [ ] Capsule list
- [ ] Capsule detail
- [ ] Date/filter controls
- [ ] Media display
- [ ] Capsule export
- [ ] Empty/error/loading states

### Done When

Capsules can be browsed and exported through the same application without requiring command-line interaction.

---

## 2026-09-22 — One-Command Local Run

Create:

```text
run.ps1
```

Expected behavior:

```text
run.ps1
   ↓
Start Python Local API
   ↓
Start React Frontend
   ↓
Open Hope Archive
```

### Verification

- [ ] Clean-environment setup documented
- [ ] Dependencies install correctly
- [ ] Backend starts
- [ ] Frontend starts
- [ ] Frontend connects to backend
- [ ] Application opens successfully

### Done When

A developer can launch the complete application using a single documented command after completing initial dependency installation.

---

## 2026-09-23 — Windows Packaging

Target:

```text
React Production Build
        +
      Tauri
        +
PyInstaller Backend
        +
 Python Sidecar
        ↓
Windows Application
```

### Tasks

- [ ] React production build
- [ ] Tauri shell
- [ ] PyInstaller backend
- [ ] Sidecar integration
- [ ] Application icon
- [ ] Runtime path handling
- [ ] Windows launch test
- [ ] Optional installer

### Done When

The application launches as a Windows application without manually starting development servers.

---

## 2026-09-24 — Release Candidate

> **FEATURE FREEZE**

Do **not** add new features.

Only:

- [ ] Bug fixes
- [ ] Integration tests
- [ ] Fresh-clone test
- [ ] Packaging test
- [ ] Documentation cleanup
- [ ] Git audit
- [ ] Privacy audit
- [ ] Remove test credentials / personal data
- [ ] Verify `.gitignore`
- [ ] Final README
- [ ] GitHub Release

### Release

```text
Hope Archive v0.9
Pre-Mid-Autumn Release
```

### Done When

The release satisfies the project-wide **Definition of Done** and can be reproduced from the public repository without private developer data.

---

# 10. Work Strategy

## Weekdays

**Target: 60–90 minutes/day**

Recommended structure:

```text
10 min     Review roadmap and previous status
45–60 min  One clearly defined implementation task
10–20 min  Tests + documentation + commit
```

### Rule

Do not start unrelated large tasks during weekday sessions.

A weekday session should ideally end with:

```text
Implementation
      ↓
    Test
      ↓
  Document
      ↓
   Commit
```

---

## Weekends

**Target: 2 × 90–120 minute sessions**

Reserve longer sessions for tasks with higher context-switching costs:

- Reverse engineering
- Schema changes
- PDF pipeline
- TeX pipeline
- AI integration
- Desktop packaging
- Integration debugging

---

# 11. Priority

## P0 — Required for Release

- [ ] Login
- [ ] Diary archive
- [ ] Three diary types
- [ ] Capsule archive
- [ ] Local normalized storage
- [ ] Date browsing
- [ ] Keyword search
- [ ] Markdown export
- [ ] PDF export
- [ ] TeX export
- [ ] React UI
- [ ] Windows runnable build

## P1 — Strongly Desired

- [ ] AI summarization
- [ ] AI-assisted search
- [ ] Better export customization
- [ ] Installer
- [ ] Brand/icon integration

## P2 — After Mid-Autumn

- [ ] Companion / 同行者 relationships
- [ ] Social graph
- [ ] Advanced AI agent
- [ ] Analytics
- [ ] Multi-account support
- [ ] Cloud synchronization

---

# 12. Scope Control

Before **2026-09-24**, do not expand into:

- Unrelated Hope APIs
- Companion / social systems
- Advanced visual design
- Complex animation
- Cloud infrastructure
- Advanced agent architecture
- Premature performance optimization
- Large architectural rewrites without demonstrated need

For every newly proposed task, ask:

> **Does this directly help the Pre-Mid-Autumn Release?**

If **yes**, evaluate its priority against the current milestone.

If **no**, add it to the post-release backlog instead of implementing it now.

### Scope Rule

> A feature being interesting, elegant, or technically impressive is **not** sufficient justification for including it in v0.9.

---

# 13. Definition of Done

Hope Archive v0.9 is considered complete when a user can:

1. Start Hope Archive on Windows.
2. Log in using their own Hope account.
3. Download their own diaries.
4. Download their own capsules.
5. Store acquired data locally.
6. Browse diary entries by date.
7. Filter all three diary categories.
8. Search their archive by keyword.
9. Preview entries before export.
10. Export Markdown.
11. Export PDF.
12. Export editable TeX.
13. Use at least one basic AI-assisted feature.
14. Reproduce the project from the public repository without private developer data.

The **Companion / 同行者 system is explicitly excluded** from this milestone.

---

# 14. Codex Execution Protocol

For each implementation session, Codex should first read this roadmap and implement **only the currently assigned milestone**.

### Standard Session Prompt

```text
Read docs/ROADMAP.md first.

Implement only the tasks under:
"<CURRENT MILESTONE>".

Before modifying code:

1. Inspect the existing repository structure.
2. Identify existing implementations that can be reused.
3. Do not rewrite working components unnecessarily.
4. Do not expand the milestone scope.
5. Identify the verification criteria before implementation.

After implementation:

1. Run all relevant tests.
2. Run frontend build/lint/typecheck if frontend code changed.
3. Update only checkboxes that have actually been verified.
4. Document unresolved issues.
5. Summarize every modified, created, or deleted file and explain why it changed.
6. Do not mark a task complete merely because code was written; verify its behavior first.
7. If verification fails, leave the corresponding checkbox unchecked.
```

### Completion Rule

```text
Code Written ≠ Task Complete

Task Complete =
Implementation
+ Verification
+ Tests
+ Documentation
```

---

# 15. Release Principle

> **Archive first. AI second. Packaging third. Polish last.**

The core value of Hope Archive is the reliable **ownership, preservation, browsing, search, and export of personal archive data**.

AI should enhance that archive—not become a dependency of it.

## 2026-09-10 — Export/UI implementation increment

- [x] Four-format export API and typed frontend choices (Markdown/TeX/PDF/DOCX).
- [x] Shared date validation: start <= end <= today; past end dates selectable.
- [x] Session display name from the existing authentication nickname, with safe fallback.
- [x] Native folder dialog integration and browser-mode fallback; Tauri compilation verified.
- [x] Synthetic export/API/date/image regression tests and PDF page rendering checks.
- [ ] Manual native folder selection/cancellation and full four-format UI workflow acceptance.
- [ ] Word reader layout acceptance across target environments.

This is a source implementation milestone, not a new GitHub release or completion of all scheduled export/release requirements. See docs/EXPORTS.md for verification boundaries.


## 2026-09-12 — Diary categories and independent time capsules

- [x] Separate semantic diary request filters from entry category values; legacy archive fallback.
- [x] React diary selection and local API integration, covered with synthetic transport tests.
- [x] Independent Capsule query client, offset pagination, normalization and separate local snapshot storage.
- [x] Session-scoped list/detail/media routes; unopened content is not fetched through detail.
- [x] Minimal Capsule page with state filters, details and on-demand local media previews; frontend checks passed.
- [ ] Authorized live diary category/server mapping and Capsule verification.
- [ ] Native UI acceptance of all media formats and real-world Capsule states.

This does not mark the broader complete Capsule acquisition/export milestone done. See [implementation scope](CATEGORIES_AND_CAPSULES.md).


## 2026-09-12 — Online preview and export UX

- [x] Fixed authentication error codes/messages, exact semantic allowlist and network fallback, synthetic tests passed.
- [x] No-write single-date diary preview through Python, category filtering and normalized content/media/comments.
- [x] React date preview with loading/error/empty/success states; typecheck, lint and build passed.
- [x] Nickname/date-range combined export for md/tex/pdf/docx; safe filename and same-line Markdown metadata tests.
- [ ] Actual Hope failure-message compatibility and live diary preview acceptance.
- [ ] Manual native directory selection/cancellation and four-format export acceptance.
- [ ] Independent Capsule date semantics and combined date preview.

See [scope and manual checklist](PREVIEW_UX.md). No new GitHub Release is implied.
