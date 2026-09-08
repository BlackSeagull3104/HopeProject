"""Offline tests: synthetic diaries only; never contact Hope."""

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hope_archive.api import DiaryAPIError, fetch_all_diaries, fetch_diary_page


def body(total, entries):
    return json.dumps({"datas": {"total": total, "list": entries}}, ensure_ascii=False).encode()


class DiaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def fetch(self, **kwargs):
        return fetch_all_diaries("synthetic-user", "2026-01-01", "2026-01-31",
                                 data_dir=self.root, **kwargs)

    @patch("hope_archive.api.urlopen")
    def test_multiple_short_pages_and_exact_raw_bytes(self, post):
        first = body(3, [{"text": "测试 🌱"}])
        post.side_effect = [io.BytesIO(first), io.BytesIO(body(3, [{"text": "b"}, {"text": "c"}]))]
        result = self.fetch(page_size=20, timeout=7)
        self.assertEqual(len(result), 3)
        self.assertEqual((self.root / "raw/diaries/page_0001.json").read_bytes(), first)
        self.assertEqual(json.loads((self.root / "processed/diaries.json").read_bytes()), result)
        for number, call in enumerate(post.call_args_list, 1):
            request = call.args[0]
            self.assertEqual(request.method, "POST")
            self.assertEqual(json.loads(request.data), dict(
                userId="synthetic-user", beginDate="2026-01-01", endDate="2026-01-31",
                type="mine", noteType=0, pageSize=20, pageNum=number))
            self.assertEqual(call.kwargs["timeout"], 7)

    @patch("hope_archive.api.urlopen")
    def test_zero_total(self, post):
        post.return_value = io.BytesIO(body(0, []))
        self.assertEqual(self.fetch(), [])
        self.assertEqual(post.call_count, 1)

    @patch("hope_archive.api.urlopen")
    def test_bad_pagination_preserves_old_output(self, post):
        output = self.root / "processed/diaries.json"
        output.parent.mkdir()
        output.write_text('["previous export"]')
        scenarios = [
            [body(3, [1]), body(3, [])],
            [body(3, [1]), body(3, [1])],
            [body(3, [1]), body(4, [2])],
            [body(1, [1, 2])],
            [b'{"datas":{"list":[]}}'],
            [b'{"datas":{"total":true,"list":[]}}'],
        ]
        for index, pages in enumerate(scenarios):
            with self.subTest(index=index):
                post.side_effect = [io.BytesIO(p) for p in pages]
                run = self.root / str(index)
                with self.assertRaises(DiaryAPIError):
                    fetch_all_diaries("synthetic", "2026-01-01", "2026-01-31", data_dir=run)
                self.assertFalse((run / "processed/diaries.json").exists())
        post.side_effect = [io.BytesIO(body(3, [1])), io.BytesIO(body(3, []))]
        with self.assertRaises(DiaryAPIError):
            self.fetch()
        self.assertEqual(output.read_text(), '["previous export"]')

    @patch("hope_archive.api.urlopen")
    def test_page_cap(self, post):
        post.return_value = io.BytesIO(body(3, [1]))
        with self.assertRaisesRegex(DiaryAPIError, "max_pages"):
            self.fetch(max_pages=1)
        self.assertEqual(post.call_count, 1)

    @patch("hope_archive.api.urlopen")
    def test_invalid_json_saved_before_parse(self, post):
        post.return_value = io.BytesIO(b"not JSON")
        with self.assertRaisesRegex(DiaryAPIError, "invalid JSON"):
            self.fetch()
        self.assertEqual((self.root / "raw/diaries/page_0001.json").read_bytes(), b"not JSON")

    @patch("hope_archive.api.urlopen")
    def test_http_error_body_saved(self, post):
        post.side_effect = HTTPError("https://example.invalid", 503, "Unavailable", {}, io.BytesIO(b"error"))
        with self.assertRaisesRegex(DiaryAPIError, "HTTP 503"):
            self.fetch()
        self.assertEqual((self.root / "raw/diaries/page_0001.json").read_bytes(), b"error")

    @patch("hope_archive.api.urlopen")
    def test_network_errors(self, post):
        for error in [TimeoutError(), URLError("offline")]:
            post.side_effect = error
            with self.assertRaisesRegex(DiaryAPIError, "network request"):
                self.fetch()
        self.assertFalse((self.root / "processed/diaries.json").exists())

    @patch("hope_archive.api.urlopen")
    def test_existing_raw_is_never_overwritten(self, post):
        post.return_value = io.BytesIO(body(0, []))
        self.fetch()
        original = (self.root / "raw/diaries/page_0001.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.fetch()
        self.assertEqual(post.call_count, 1)
        self.assertEqual((self.root / "raw/diaries/page_0001.json").read_bytes(), original)

    @patch("hope_archive.api.urlopen")
    def test_invalid_parameters_do_not_request(self, post):
        for kwargs in [dict(page_size=0), dict(timeout=0), dict(timeout=float("nan")), dict(max_pages=0)]:
            with self.assertRaises(ValueError):
                self.fetch(**kwargs)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
