"""Minimal command-line entry point for the read-only diary exporter."""

import argparse
from datetime import date
from pathlib import Path
import sys

# Support the scaffold's existing direct-script command as well as module usage.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hope_archive.api import DiaryAPIError, fetch_all_diaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Export your own Hope diaries (type=mine).")
    parser.add_argument("--user-id", required=True, help="Your own backend userId")
    parser.add_argument("--begin-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--max-pages", type=int, default=10000)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    args = parser.parse_args()
    if args.begin_date > args.end_date:
        parser.error("begin-date must be on or before end-date")
    try:
        entries = fetch_all_diaries(
            args.user_id, args.begin_date.isoformat(), args.end_date.isoformat(),
            page_size=args.page_size, timeout=args.timeout,
            max_pages=args.max_pages, data_dir=args.data_dir)
    except (DiaryAPIError, OSError, ValueError) as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    print(f"Saved {len(entries)} diaries to {args.data_dir / 'processed/diaries.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
