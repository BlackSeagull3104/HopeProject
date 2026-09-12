"""Read-only personal diary requests and deliberately conservative pagination."""

import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .storage import save_diaries, save_raw_response
from .diary_types import FILTER_VALUES

ENDPOINT = "https://hope.wantexe.com/services/v2/parallellife/period/dairy/list"


class DiaryAPIError(Exception):
    """The request or returned diary data could not be used safely."""


def fetch_diary_page(user_id: str, begin_date: str, end_date: str, *,
                     page_num: int = 1, page_size: int = 20, note_type: int = 0,
                     timeout: float = 30, raw_dir: Path = Path("data/raw/diaries")):
    """POST one page, preserve its body before parsing, then return JSON.

    No authentication or account verification is performed. The caller supplies
    their own backend user ID. There is intentionally no configurable `type`.
    """
    if type(note_type) is not int or note_type not in FILTER_VALUES.values():
        raise ValueError("Unsupported diary filter")
    if not user_id.strip():
        raise ValueError("user_id must not be empty")
    if page_num < 1 or page_size < 1:
        raise ValueError("page_num and page_size must be positive")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    path = Path(raw_dir) / f"page_{page_num:04d}.json"
    if path.exists():
        raise FileExistsError(f"Raw response already exists: {path}. Use a new data directory.")
    payload = dict(beginDate=begin_date, endDate=end_date, noteType=note_type,
                   pageSize=page_size, pageNum=page_num, type="mine", userId=user_id)
    request = Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json", "Accept": "application/json"},
                      method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        # HTTP error bodies are evidence too, even when they contain HTML.
        with exc:
            save_raw_response(path, exc.read())
        raise DiaryAPIError(f"Page {page_num}: HTTP {exc.code}; raw body saved to {path}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise DiaryAPIError(f"Page {page_num}: network request failed or timed out") from exc
    save_raw_response(path, body)
    try:
        return json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise DiaryAPIError(f"Page {page_num}: invalid JSON; raw body saved to {path}") from exc


def fetch_all_diaries(user_id: str, begin_date: str, end_date: str, *,
                      page_size: int = 20, note_type: int = 0, timeout: float = 30,
                      max_pages: int = 10000, data_dir: Path = Path("data")) -> list:
    """Return unchanged entries and publish the combined file only on completion."""
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    entries = []
    expected_total = None
    seen_pages = set()
    for page_num in range(1, max_pages + 1):
        response = fetch_diary_page(
            user_id, begin_date, end_date, page_num=page_num, page_size=page_size,
            note_type=note_type, timeout=timeout,
            raw_dir=Path(data_dir) / "raw/diaries")
        data = response.get("datas") if isinstance(response, dict) else None
        if not isinstance(data, dict):
            raise DiaryAPIError(f"Page {page_num}: missing datas object")
        total, page = data.get("total"), data.get("list")
        if type(total) is not int or total < 0 or not isinstance(page, list):
            raise DiaryAPIError(f"Page {page_num}: expected nonnegative integer total and list")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise DiaryAPIError("Total changed during export; retry in a new data directory")
        # Do not assume an undocumented ID field or silently discard entries.
        signature = json.dumps(page, sort_keys=True, ensure_ascii=False)
        if page and signature in seen_pages:
            raise DiaryAPIError(f"Page {page_num}: repeated page; export incomplete")
        seen_pages.add(signature)
        entries.extend(page)
        if len(entries) > expected_total:
            raise DiaryAPIError("Received more entries than datas.total")
        if len(entries) == expected_total:
            save_diaries(Path(data_dir) / "processed/diaries.json", entries)
            return entries
        if not page:
            raise DiaryAPIError(f"Page {page_num}: empty page before reaching datas.total")
        # Short pages do not prove completion; datas.total is the stopping rule.
    raise DiaryAPIError(f"Reached max_pages={max_pages} before collecting datas.total")
