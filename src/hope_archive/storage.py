"""Small persistence helpers; raw response bodies are never reformatted."""

import json
from pathlib import Path


def save_raw_response(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves earlier evidence, including failed responses.
    with path.open("xb") as stream:
        stream.write(body)


def save_diaries(path: Path, entries: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    stream = temporary.open("x", encoding="utf-8")
    try:
        with stream:
            json.dump(entries, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        # Publish only a complete export; a failed fetch never replaces this file.
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
