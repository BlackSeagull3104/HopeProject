"""Thin CLI adapter for the same archive service used by the UI."""
import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hope_archive import application


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive your own Hope diaries as Markdown (type=mine).")
    parser.add_argument("--user-id", required=True, help="Your own backend userId")
    parser.add_argument("--begin-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--note-type", type=int, choices=sorted(set(application.NOTE_TYPE_OPTIONS.values())), default=0)
    # Legacy spelling remains an alias; both select a root, not a run directory.
    parser.add_argument("--output-dir", "--data-dir", dest="output_dir", type=Path,
                        default=Path(__file__).resolve().parents[2] / "data",
                        help="Archive root; each invocation creates a new run directory")
    args = parser.parse_args()
    try:
        result = application.export_archive(
            args.user_id, args.begin_date, args.end_date, args.note_type,
            args.output_dir, on_progress=lambda message: print(message, flush=True))
    except application.ArchiveError as exc:
        print(f"Archive failed: {exc}", file=sys.stderr)
        if exc.output_dir:
            print(f"Saved files / diagnostics: {exc.output_dir}", file=sys.stderr)
        return 1
    print(f"Diaries: {result.diary_count}")
    print(f"Media: downloaded={result.media['downloaded']}, skipped={result.media['skipped']}, failed={result.media['failed']}")
    print(f"Markdown: generated={result.markdown['generated']}, skipped={result.markdown['skipped']}, failed={result.markdown['failed']}")
    print(f"Output: {result.output_dir}")
    return 0 if result.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
