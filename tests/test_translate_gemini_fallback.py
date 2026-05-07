"""P1.5: translate_gemini.py のバックエンドフォールバックチェーンの単体テスト。

2026-05-07 incident で実装したフォールバック機構の回帰防止が目的。
実 API は呼ばずに mock で検証する。

Run:
    pytest tests/test_translate_gemini_fallback.py -v
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

spec = importlib.util.spec_from_file_location(
    "translate_gemini", os.path.join(ROOT, "scripts", "translate_gemini.py")
)
tg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tg)


class TestBackendErrorClass(unittest.TestCase):
    """BackendError 例外クラスが期待通り動作することを確認"""

    def test_backend_error_message_format(self):
        e = tg.BackendError("gemini", "HTTP 503: high demand")
        self.assertEqual(e.backend_name, "gemini")
        self.assertEqual(e.message, "HTTP 503: high demand")
        self.assertIn("[gemini]", str(e))
        self.assertIn("HTTP 503", str(e))

    def test_backend_error_is_exception(self):
        self.assertTrue(issubclass(tg.BackendError, Exception))


class TestGeminiApiRaisesBackendError(unittest.TestCase):
    """call_gemini_api が失敗時に BackendError を raise することを確認 (旧 sys.exit ではない)"""

    @patch("translate_gemini.urllib.request.urlopen")
    def test_503_raises_backend_error(self, mock_urlopen):
        import urllib.error

        # HTTP 503 をシミュレート (実際は HTTPError)
        from io import BytesIO
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/...",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=BytesIO(b'{"error":{"message":"high demand"}}'),
        )

        with self.assertRaises(tg.BackendError) as ctx:
            tg.call_gemini_api("FAKE_KEY", "test prompt", max_retries=0)
        self.assertEqual(ctx.exception.backend_name, "gemini")
        self.assertIn("HTTP 503", ctx.exception.message)

    @patch("translate_gemini.urllib.request.urlopen")
    def test_429_with_retries_then_raises(self, mock_urlopen):
        """429 は max_retries を尽くしても回復しない場合 BackendError"""
        import urllib.error
        from io import BytesIO
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="...", code=429, msg="Too Many Requests", hdrs=None,
            fp=BytesIO(b'{"error":{"message":"rate limited"}}'),
        )
        with patch("translate_gemini.time.sleep"):  # backoff スリープを skip
            with self.assertRaises(tg.BackendError):
                tg.call_gemini_api("FAKE_KEY", "test", max_retries=1)


class TestGroqApiRaisesBackendError(unittest.TestCase):
    @patch("translate_gemini.urllib.request.urlopen")
    def test_5xx_raises_backend_error(self, mock_urlopen):
        import urllib.error
        from io import BytesIO
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="...", code=500, msg="Internal Server Error", hdrs=None,
            fp=BytesIO('{"error":{"message":"groq 内部エラー"}}'.encode("utf-8")),
        )
        with self.assertRaises(tg.BackendError) as ctx:
            tg.call_groq_api("FAKE_KEY", "test", max_retries=0)
        self.assertEqual(ctx.exception.backend_name, "groq")


class TestGitHubModelsRaisesBackendError(unittest.TestCase):
    @patch("translate_gemini.urllib.request.urlopen")
    def test_5xx_raises_backend_error(self, mock_urlopen):
        import urllib.error
        from io import BytesIO
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="...", code=500, msg="Internal Server Error", hdrs=None,
            fp=BytesIO('{"error":{"message":"GitHub Models 内部エラー"}}'.encode("utf-8")),
        )
        with self.assertRaises(tg.BackendError) as ctx:
            tg.call_github_models(
                "https://models.github.ai/inference",
                "FAKE_TOKEN",
                "openai/gpt-4.1",
                "test",
                max_retries=0,
            )
        self.assertEqual(ctx.exception.backend_name, "github_models")


class TestChunkSplitting(unittest.TestCase):
    """split_into_chunks のエッジケース回帰テスト"""

    def test_short_text_single_chunk(self):
        text = "短い段落。" * 10
        chunks = tg.split_into_chunks(text, limit=6500)
        self.assertEqual(len(chunks), 1)

    def test_paragraph_boundary(self):
        text = "段落1。\n\n段落2。\n\n段落3。"
        chunks = tg.split_into_chunks(text, limit=8)  # 各段落が limit 超え
        # 段落単位で分割される
        self.assertGreaterEqual(len(chunks), 1)

    def test_empty_input(self):
        chunks = tg.split_into_chunks("", limit=6500)
        self.assertEqual(chunks, [])


class TestFrontMatterExtraction(unittest.TestCase):
    """extract_front_matter のエッジケース"""

    def test_with_front_matter(self):
        text = '---\ntitle: "test"\n---\n\nbody content here.'
        fm, body = tg.extract_front_matter(text)
        self.assertIsNotNone(fm)
        self.assertIn('title:', fm)
        self.assertIn('body content', body)

    def test_without_front_matter(self):
        text = "Just body content, no front matter."
        fm, body = tg.extract_front_matter(text)
        self.assertIsNone(fm)
        self.assertEqual(body, text)


if __name__ == "__main__":
    unittest.main()
