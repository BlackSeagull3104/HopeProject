"""Synthetic preservation tests; no personal diaries or network required."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hope_archive.normalization import normalize_diaries, normalize_diary
from hope_archive.normalize import normalize_file


class NormalizationTests(unittest.TestCase):
    def test_order_text_and_media_preserved(self):
        blocks = [
            {"type": 1, "text": "  中文\n\nTypo!  ", "fileList": None},
            {"type": 2, "text": "", "fileList": [
                {"fileId": 1, "mediaUrl": "a.jpeg", "mediaName": "a"},
                {"fileId": 2, "mediaUrl": "b.jpeg", "mediaName": "b"}]},
            {"type": 1, "text": "\nend ", "fileList": []},
            {"type": 99, "text": "unknown", "fileList": [{"fileId": 3}]},
        ]
        source = {"dairyId": 1, "dairy": "different\n", "dairy2": "secondary ",
                  "noteInfo2": {"richTextInfo": blocks}}
        before = copy.deepcopy(source)
        result = normalize_diary(source)
        self.assertEqual(source, before)
        self.assertEqual(result["original_text"], source["dairy"])
        self.assertEqual(result["original_text_secondary"], source["dairy2"])
        self.assertEqual([b["text"] for b in result["content"]], [b["text"] for b in blocks])
        self.assertEqual([b["kind"] for b in result["content"]], ["text", "image", "text", "unknown"])
        self.assertEqual([f["file_id"] for f in result["content"][1]["media"]], [1, 2])

    def test_comments_and_account_allowlist(self):
        user = {"id": 4, "nickName": "Sample", "mobile": "PRIVATE", "deviceToken": "PRIVATE"}
        source = {"dairyId": 1, "user": user, "commentList": [{"bundleId": "g", "detail": [
            {"commentId": 10, "comments": "\n A ", "fromUser": user},
            {"commentId": 11, "toCommentId": 10, "comments": "reply", "toUser": user}]}]}
        result = normalize_diary(source)
        self.assertEqual(result["author"], {"id": 4, "name": "Sample"})
        items = result["comments"][0]["items"]
        self.assertEqual(items[0]["text"], "\n A ")
        self.assertEqual(items[1]["reply_to_id"], 10)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_missing_null_and_zero(self):
        result = normalize_diary({"dairyId": 0, "noteInfo2": None, "commentList": None, "emotion": 0})
        self.assertEqual(result["content"], [])
        self.assertEqual(result["comments"], [])
        self.assertIsNone(result["original_text"])
        self.assertEqual(result["emotion"]["value"], 0)
        self.assertIsNone(result["created_at"])

    def test_invalid_input_fails_and_duplicates_are_not_deleted(self):
        for entry in [{}, {"dairyId": None}, {"dairyId": True}, {"dairyId": 1, "noteInfo2": []},
                      {"dairyId": 1, "noteInfo2": {"richTextInfo": [None]}}]:
            with self.assertRaises(ValueError):
                normalize_diary(entry)
        self.assertEqual(len(normalize_diaries([{"dairyId": 1}] * 2)["diaries"]), 2)

    def test_file_output_utf8_and_overwrite_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            processed = project / "data/processed"
            processed.mkdir(parents=True)
            source = processed / "diaries.json"
            source.write_text('[{"dairyId":1,"dairy":"中文"}]', encoding="utf-8")
            before = source.read_bytes()
            output = processed / "normalized.json"
            with patch("hope_archive.normalize.PROJECT", project):
                self.assertEqual(normalize_file(source, output), 1)
                self.assertIn("中文", output.read_text(encoding="utf-8"))
                with self.assertRaises(FileExistsError):
                    normalize_file(source, output)
                with self.assertRaises(ValueError):
                    normalize_file(source, source)
                with self.assertRaises(ValueError):
                    normalize_file(source, project / "data/raw/page_0001.json")
            self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
