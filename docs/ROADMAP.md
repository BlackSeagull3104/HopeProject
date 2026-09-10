# Hope Archive Roadmap

## Target

**Pre-Mid-Autumn Release: 2026-09-24**

Goal:

Build a complete local-first Hope Archive application covering:

- authentication
- diary acquisition
- capsule acquisition
- browsing
- filtering
- search
- Markdown export
- PDF export
- TeX export
- basic AI assistance
- React desktop-oriented UI
- Windows runnable build

Out of scope before this milestone:

- Companion / 同行者 relationship features
- social graph
- advanced analytics
- cloud synchronization
- multi-account system
- complex AI agents

---

# 1. Product Flow

```text
Login
  ↓
Acquire personal Hope data
  ↓
Normalize & store locally
  ↓
Browse / Filter / Search
  ↓
Preview diary
  ↓
Export
  ├── Markdown
  ├── PDF
  └── TeX
  ↓
Optional AI assistance
2. Architecture
React + shadcn/ui
        ↓
Python Local API
        ↓
Application Layer
        ↓
Auth / Download / Normalize / Search / Export
        ↓
Hope API + Local Archive
Desktop packaging later wraps:
Tauri
├── React frontend
└── Python backend sidecar
3. P0 Requirements
Authentication
- SMS verification-code login
- Mobile/password login
- Automatically obtain current user ID
- Verify session behavior in the new React UI
Diary Acquisition
- Basic diary download
- Media download
- Normalization
- Local archive structure
- Reverse engineer all three diary types
- Implement diary type mapping
- Verify each diary type using own account
Capsule
- Reverse engineer capsule API
- Download capsule data
- Download capsule media
- Normalize capsule data
- Browse capsules in UI
- Export capsules
Browsing
- Browse diary by date
- Calendar/date picker
- Diary detail view
- Display text
- Display media
- Display emotion/weather
- Display comments
- Empty state
Filtering
- All diaries
- Diary type A
- Diary type B
- Diary type C
- Date range filter
- Combined type/date filtering
Search
- Keyword search
- Search snippets
- Date filtering
- Type filtering
- Search result → diary detail
Export
Markdown
- Existing Markdown exporter
- Connect exporter to React UI
- Export one diary
- Export date range
- Stable media paths
- Stable naming
PDF
- Stable PDF pipeline
- Image scaling
- Multi-image layout
- Long-image handling
- Page breaks
- Chinese font support
- Comment layout
TeX
- TeX exporter
- Default template
- User-editable .tex
- Media support
- Date/title metadata
- Documentation for XeLaTeX usage
AI
Minimum target:
- Selected diary summarization
Stretch:
- Natural-language archive search
- Semantic retrieval
AI must not block core archive functionality.
Frontend
- Vite + React + TypeScript
- shadcn/ui
- Login UI
- Archive UI
- Export UI
- Diary browser
- Search page
- Capsule page
- Error/empty/loading states
- Final navigation cleanup
Windows Application
- One-command run.ps1
- Fresh-clone reproducibility
- Tauri shell
- Python backend PyInstaller build
- Python sidecar integration
- Windows runnable application
- Optional installer
- GitHub Release
4. Schedule
2026-09-10 — Freeze Current Baseline
- Unify Git repository
- Run complete tests
- Verify frontend build
- Commit & push
- Create this roadmap
- Stop visual/icon iteration
2026-09-11 — Reverse Engineer Diary Types
Goal:
Identify the exact API behavior of all three diary categories.
Tasks:
- Trigger each type in official client
- Compare Charles requests
- Inspect JADX if necessary
- Identify endpoint/parameter differences
- Document mapping
- Implement constants/types
- Add tests
Deliverable:
docs/diary-api.md
2026-09-12 — Capsule Reverse Engineering
- Find capsule endpoints
- Understand pagination
- Identify content/media fields
- Build downloader
- Save raw responses
- Test with authorized personal account
2026-09-13 — Freeze Data Model
- Define normalized diary schema
- Define normalized capsule schema
- Normalize media representation
- Normalize comments
- Stabilize archive directory structure
- Migration compatibility
- Tests
Target:
Data model ~80% frozen by end of day.
2026-09-14 — Date-based Diary Browser
- Calendar/date picker
- Query diary by date
- Diary list
- Diary detail
- Media display
- Comments
- Empty state
2026-09-15 — Diary Type Filters
- All
- Type A
- Type B
- Type C
- Combine with date query
2026-09-16 — Search v1
- Keyword search
- Search snippets
- Highlight match
- Date range
- Diary type
- Result → detail
Do not introduce a complex search engine unless required.
2026-09-17 — Markdown Export
- Stabilize exporter
- React integration
- Single entry export
- Date range export
- Media paths
- Comments
- Naming
- Optional YAML
2026-09-18 — PDF Export
- Stable conversion pipeline
- Image sizes
- Horizontal/vertical images
- Multi-image layout
- Long screenshots
- Page breaks
- Chinese fonts
2026-09-19 — TeX Export
- Generate .tex
- Default editable template
- Assets directory
- Documentation
- XeLaTeX compatibility
Principle:
Hope Archive generates editable TeX;
users may customize templates themselves.
2026-09-20 — AI Minimum Feature
P0:
- Summarize selected diary
If time permits:
- Semantic search
- Natural-language archive query
Do not build an agent system.
2026-09-21 — Capsule UI
- Capsule list
- Capsule detail
- Filtering
- Media
- Export
2026-09-22 — One-command Local Run
Create:
run.ps1
Expected behavior:
1. Start Python local API
2. Start React frontend
3. Open local application
Also verify clean setup instructions.
2026-09-23 — Windows Packaging
Target:
React build
+
Tauri shell
+
PyInstaller Python backend
+
sidecar
Goal:
A Windows application that can be launched without manually starting development servers.
2026-09-24 — Release Candidate
No new features.
Only:
- Bug fixes
- Integration tests
- Fresh-clone test
- Packaging test
- Documentation
- Git audit
- Privacy audit
- GitHub Release
Release:
Hope Archive v0.9 / Pre-Mid-Autumn Release
5. Weekly Work Strategy
Weekdays
Target:
60–90 minutes/day
Structure:
10 min   review roadmap / previous status
45–60    one clearly defined implementation task
10–20    tests + docs + commit
Avoid starting unrelated large tasks.
Weekends
Target:
2 × 90–120 minute sessions
Best for:
- reverse engineering
- schema changes
- PDF
- TeX
- AI
- packaging
6. Priority
P0 — Required
- Login
- Diary archive
- Three diary types
- Capsule archive
- Local normalized storage
- Date browsing
- Keyword search
- Markdown
- PDF
- TeX
- React UI
- Windows runnable build
P1 — Strongly Desired
- AI summarization
- AI-assisted search
- Better export customization
- Installer
- Brand/icon integration
P2 — After Mid-Autumn
- Companion relationships
- Social graph
- Advanced AI agent
- Analytics
- Multi-account
- Cloud sync
7. Scope Rules
Before 2026-09-24:
Do not expand into:
- unrelated Hope APIs
- companion/social systems
- advanced visual design
- complex animation
- cloud infrastructure
- advanced agent architecture
Every new task must answer:
Does this directly help the Pre-Mid-Autumn release?

If not, defer it.
8. Definition of Done
The release is considered complete when a user can:
1. Start Hope Archive on Windows.
2. Login using their own Hope account.
3. Download their own diaries.
4. Download their own capsules.
5. Browse entries by date.
6. Filter the three diary categories.
7. Search their archive.
8. Preview entries before export.
9. Export Markdown.
10. Export PDF.
11. Export editable TeX.
12. Use at least one basic AI-assisted feature.
13. Reproduce the project from the public repository without private developer data.
The Companion/同行者 system is explicitly excluded from this milestone.

这份 roadmap 我建议你真的放进仓库里，而不是只留在聊天里。接下来 Codex 每做一轮，你甚至可以直接告诉它：

> **“Read `docs/ROADMAP.md`, implement only the tasks for 2026-09-11, update checkboxes after verified tests.”**

这样你的投入模式就会从“想到什么做什么”，变成持续的 project execution。