# RC5 rendering specification

Normalized diary → ordered `document.diary_blocks()` → Markdown or resolved
document blocks → PDF / DOCX / TeX. PDF and DOCX never parse the exported
Markdown file. Application cloud preview renders normalized JSON in React,
not Markdown; its CSS is not the exported document's style source.

## Reference and limits

Markdown remains the reference. Its inline HTML provides `.image-group` and
`.image-row`, centered top-aligned flex rows, 2% gaps, 0.5em vertical margins,
intrinsic-width caps and a 480px image height limit. Reader typography is
external. The accepted reader/theme has not been identified; the reproducible
provisional typography reference is VS Code's default Markdown CSS: 14px body,
22px leading, 16px paragraph spacing, 2em date and 1.5em titles, heading rules.
This is an explicit assumption, not a claim to reproduce an unknown theme.
Generated Markdown body text, headings and comment markup are preserved.

`document_style.py` specifies text hierarchy, blank-line paragraph boundaries,
labelled comment runs and A4 layout. CSS lengths map at 0.75 points per pixel.
PDF and Word have 56pt horizontal / 54pt vertical margins. PDF uses an explicit
zero-padding frame. Word computes image width from its saved section geometry
(OOXML rounds dimensions to twips). Both map shared font sizes, leading, spacing,
heading rules and keep-with-next. Multiple diaries have separators.

## Media semantics

`image_layout.py` is the single grouping/classification authority. Long means
height/width ≥ 2.5; portrait width/height < .85; landscape > 1.35; otherwise
regular. Single width fractions remain 38%, 46%, 65%, 55% respectively.
Adjacent known images may pair when neither is long, intrinsic width ≥ 192px
and max/min aspect ratio ≤ 1.5. Exactly three compatible adjacent images retain
the accepted three-column layout; four or more use pairs, with trailing singles.
Pair and triptych cell widths remain 48% and 31%, with 2% gaps. Text and other
media interrupt groups. The grouping compatibility checks intentionally correct
RC4's unconditional Markdown pairing for incompatible images.

All formats preserve order/aspect ratio, never enlarge beyond 96dpi intrinsic
dimensions, and cap image height at 480px / 360pt. Compatible portraits can now
pair. PDF uses fixed zero-padding table cells; Word uses centered fixed-width
tables with every border explicitly disabled, zero margins and unsplittable
rows. These row groups may move to the next page; blank space is preferable to
splitting paired images. No crop or image slicing is performed. Very long
screenshots stay whole, so small text can still require zooming. Original media
bytes are never modified; document image normalization uses derived PNG data.

## Fonts and engines

Word requests Segoe UI for Latin and Microsoft YaHei for CJK, clears inherited
theme font references and explicitly configures styles. PDF embeds subsets of
the corresponding Windows system fonts, including bold. Segoe UI Symbol handles
the generated reply arrow and weather sun. These are OS fonts, not copied into
the installer. If YaHei is unavailable PDF tries SimSun then STSong-Light CID;
the last fallback is viewer-dependent and has lower parity. DOCX font fallback
on non-Windows readers is controlled by that reader; fonts are not embedded.

ReportLab remains: the identified differences were missing layout semantics
and inconsistent renderer mappings, addressed without a new runtime. There is
no Pandoc, bundled Chromium or browser print dependency. Rich arbitrary Markdown
written inside diary text remains literal in PDF/Word; this is not a general
Markdown-to-Word converter. Emoji beyond the explicitly mapped generated
symbols remain font-dependent. Browser and paged outputs need not break lines
or pages identically.

TeX retains ctexart/Fandol, relative `assets/` paths and shared image semantics.
Compile in the export directory with `lualatex file.tex`; no TeX runtime is
bundled. Automatic Markdown retention for PDF/Word is unchanged.

## Verification

Run `python scripts/rendering_fixtures.py <outside-repository-output>` to create
20 deterministic synthetic cases in four formats. No user data is read. The
suite includes text/CJK/Latin/mixed paragraphs, every image shape, compatible
and incompatible groups, comments, metadata, multiple entries and page edges.
`tests/test_rendering_rc5.py` checks grouping, dimensions, styles, paragraphs,
comment runs, borderless tables, separators, determinism and representative
upstream normalized structures. Existing workflow tests preserve automatic MD,
moved-archive portability and prior RC4 behavior.

Actual Word page rendering requires an installed compatible document renderer.
OOXML validation alone is not evidence of Word visual parity. External QA
artifacts record what was and was not visually verified.
