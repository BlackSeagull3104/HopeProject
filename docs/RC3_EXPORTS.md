# RC3 export corrections

RC2 Markdown resolved media against the internal archive but did not copy it into the export. Moving an export broke its image references. RC3 copies original bytes into `assets/<sha256>.<extension>` and writes relative, URL-encoded links. Identical bytes with the same extension share a file; different files with the same original name cannot collide. Existing conflicting files are never overwritten. Missing media gets a visible placeholder.

The desktop date-range export keeps its existing combined document under `<export-root>/diaries/`, beside `assets/`. Per-entry exports use `YYYY/MM/YYYY-MM-DD_<id>.md`, with a shared top-level `assets/`. Move the entire diaries folder, including assets, to preserve offline viewing. No internal archive path is required.

`document.diary_blocks()` now supplies ordered date, title, metadata, text, images, other media and comments to Markdown and the PDF/DOCX/TeX/TXT adapter. Each format renders this same normalized content. PDF continues using bundled ReportLab; no browser, Pandoc or LaTeX runtime is introduced. It does not parse the generated Markdown or promise pixel-identical styling across Markdown viewers.

## PDF layout

- A4; side margins 56 pt, top/bottom 54 pt. ReportLab's frame padding leaves 471.28 pt usable width.
- Body 10.5/17 pt; date 17/23 pt; title 13/19 pt; comments 9.5/15 pt, gray and indented 12 pt. Paragraph spacing is 9 pt. Chinese uses the existing embedded Windows font, with the existing CID-font fallback.
- Image pixels are interpreted at 96 dpi. Images are never enlarged, cropped, stretched or sliced. EXIF orientation is respected.
- Adjacent images pair only when each width/height ratio is 0.85–2.2 and each intrinsic display width is at least 144 pt. Two columns have a 12 pt gap, with each image bounded by the column width and 200 pt height.
- Long images (height/width >= 2.5): one centered column, at most 38% of body width and 260 pt high.
- Other portraits (width/height < 0.85): one centered column, at most 46% of body width and 300 pt high.
- Other single images: at most 65% of body width for width/height > 1.35, otherwise 55%; at most 260 pt high.
- Three or more images use the same greedy adjacent-pair rule in original order. Rows stay together, with 12 pt after each row. A row moves to the next page if necessary.

Very long screenshots can have small text at whole-page zoom. Markdown assets retain their original bytes for full-resolution viewing. Missing/corrupt media does not abort PDF export. Audio/video embedding remains outside PDF's existing scope.

## Regression coverage

Synthetic tests cover original-byte copying, same-name collisions, shared assets, Chinese paths, missing media, refusal to overwrite conflicting assets, and moving an exported folder after deleting its internal archive. Ten PDF fixtures cover text, Chinese, mixed text, landscape, portrait, long screenshots, compatible pairs, multiple images, comments and missing media. Layout tests check order, bounds and aspect ratios. No real diary data is used.
