"""Run normalization without importing the downloader or contacting any server."""

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hope_archive.normalization import normalize_diaries

PROJECT = Path(__file__).resolve().parents[2]


def normalize_file(input_path, output_path):
    source, target = Path(input_path).resolve(), Path(output_path).resolve()
    # Restrict this CLI to a distinct processed artifact, never raw backup files.
    processed = (PROJECT / "data/processed").resolve()
    if source == target or target == processed / "diaries.json":
        raise ValueError("Output must not overwrite the combined downloader input")
    if not target.is_relative_to(processed):
        raise ValueError("Output must be inside the project's data/processed directory")
    if target.exists():
        raise FileExistsError("Output already exists; choose a new --output filename")
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    normalized = normalize_diaries(data)
    # Serialize before opening output: conversion errors leave no partial file.
    text = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    return len(normalized["diaries"])


def main():
    parser = argparse.ArgumentParser(description="Normalize a local Hope diary export offline.")
    parser.add_argument("--input", type=Path, default=PROJECT / "data/processed/diaries.json")
    parser.add_argument("--output", type=Path, default=PROJECT / "data/processed/diaries.normalized.json")
    args = parser.parse_args()
    try:
        count = normalize_file(args.input, args.output)
    except (OSError, ValueError) as exc:
        print(f"Normalization failed: {exc}", file=sys.stderr)
        return 1
    print(f"Normalized entries: {count}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
