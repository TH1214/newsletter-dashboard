#!/usr/bin/env python3
"""
SPEC v1.1 Section 9.1 準拠の hero 画像生成ユニットテスト (TC-01 〜 TC-06)。

TC-01 〜 TC-04: 実 Gemini Flash text API を叩く integration tests。
    - GEMINI_API_KEY が未設定なら自動スキップ
    - 1 ケースあたり API 2-4 call 程度 (無料枠 1,500 RPD に対し誤差範囲)

TC-05 〜 TC-06: mock を使った純粋ユニットテスト (API 呼出なし)。

実行:
    python3 -m unittest tests.test_hero_generation -v
    python3 tests/test_hero_generation.py
"""

import json
import os
import re
import sys
import unittest
from unittest.mock import patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from generate_hero_image import (  # noqa: E402
    ABSTRACT_NOUN_BLACKLIST,
    GeminiTextExtractionError,
    STYLE_DICTIONARY,
    build_hero_prompt,
    extract_visual_concept_with_retry,
    generate_hero_with_fallback,
)


API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()


def _tokens(phrase: str) -> list:
    return [t for t in re.findall(r"[A-Za-z']+", phrase.lower())
            if t not in {"a", "an", "the"}]


def _assert_noun_concrete(testcase, concept: dict) -> None:
    """primary_subject_noun が ABSTRACT_NOUN_BLACKLIST のいずれも含まないことを検証。"""
    noun = concept.get("primary_subject_noun", "")
    tokens = set(_tokens(noun))
    hits = tokens & ABSTRACT_NOUN_BLACKLIST
    testcase.assertFalse(
        hits,
        f"primary_subject_noun='{noun}' contains abstract word(s): {sorted(hits)}"
    )


def _build_prompt_from_concept(concept: dict, media: str) -> str:
    style = STYLE_DICTIONARY[media]
    return build_hero_prompt(
        subject_noun=concept["primary_subject_noun"],
        metaphor=concept["visual_metaphor"],
        context=concept["contextual_detail"],
        style_keywords=style["style_keywords"],
        category=style["category"],
    )


@unittest.skipUnless(
    API_KEY,
    "GEMINI_API_KEY not set — integration tests (TC-01〜04) skipped",
)
class TestIntegration(unittest.TestCase):
    """TC-01 〜 TC-04: 実 Gemini Flash text API を呼ぶ integration tests。"""

    def test_tc01_wsj_boj_rate_hike(self):
        """TC-01: 日銀利上げ→円高 (wsj) で主役名詞が抽象語でないこと。"""
        concept = extract_visual_concept_with_retry(
            "日銀が利上げを示唆、円高が進行", API_KEY
        )
        _assert_noun_concrete(self, concept)

    def test_tc02_skift_jal_okinawa(self):
        """TC-02: JAL City那覇 ADR+15% (skift) → 主役名詞具体 + prompt に 'aspirational'。"""
        concept = extract_visual_concept_with_retry(
            "JAL City那覇、GW期間のADRが前年比+15%", API_KEY
        )
        _assert_noun_concrete(self, concept)
        prompt = _build_prompt_from_concept(concept, "skift")
        self.assertIn(
            "aspirational", prompt,
            f"skift prompt must include 'aspirational'. got: {prompt}"
        )

    def test_tc03_buysiders_marubeni_ss30(self):
        """TC-03: Marubeni 仙台SS30 取得検討 (buysiders) → prompt に 'navy and gold'。"""
        concept = extract_visual_concept_with_retry(
            "Marubeniが仙台SS30の取得を検討", API_KEY
        )
        _assert_noun_concrete(self, concept)
        prompt = _build_prompt_from_concept(concept, "buysiders")
        self.assertIn(
            "navy and gold", prompt,
            f"buysiders prompt must include 'navy and gold'. got: {prompt}"
        )

    def test_tc04_nyt_op_ai_regulation(self):
        """TC-04: AI規制の必要性 (nyt-op) → prompt に 'bold' と 'high-contrast'。"""
        concept = extract_visual_concept_with_retry(
            "AI規制の必要性", API_KEY
        )
        _assert_noun_concrete(self, concept)
        prompt = _build_prompt_from_concept(concept, "nyt-op")
        self.assertIn("bold", prompt, f"nyt-op prompt must include 'bold'. got: {prompt}")
        self.assertIn(
            "high-contrast", prompt,
            f"nyt-op prompt must include 'high-contrast'. got: {prompt}"
        )


class TestMocked(unittest.TestCase):
    """TC-05, TC-06: mock による純粋ユニットテスト (API 呼出なし)。"""

    def test_tc05_retry_on_abstract_noun(self):
        """
        TC-05: 1 回目に primary_subject_noun='growth' を返させる。
        → 1 回リトライが実行され、2 回目は具体名詞を返して抽出成功。
        """
        call_messages = []

        def fake_text(user_message, system_instruction, api_key, **_kw):
            call_messages.append(user_message)
            if len(call_messages) == 1:
                return json.dumps({
                    "core_theme": "growth",
                    "visual_metaphor": "upward arrow",
                    "contextual_detail": "Japan economy",
                    "primary_subject_noun": "growth",  # blacklist hit → retry
                })
            return json.dumps({
                "core_theme": "growth",
                "visual_metaphor": "a rising staircase",
                "contextual_detail": "Tokyo financial district",
                "primary_subject_noun": "a rising staircase of golden coins",
            })

        with patch("generate_hero_image._call_gemini_text", side_effect=fake_text):
            concept = extract_visual_concept_with_retry("dummy summary", "FAKE_KEY")

        self.assertEqual(
            len(call_messages), 2,
            f"expected 2 text calls (1 initial + 1 retry), got {len(call_messages)}"
        )
        self.assertIn(
            "Your previous output was too abstract", call_messages[1],
            "retry message must include the SPEC 7.3 extra instruction"
        )
        _assert_noun_concrete(self, concept)

    def test_tc06_fallback_on_text_double_failure(self):
        """
        TC-06: Gemini text を 2 回とも失敗させる。
        → フォールバック (legacy build_prompt → call_gemini_image) が呼ばれ、
          meta['path'] == 'legacy' になる。
        """
        text_calls = {"n": 0}
        image_calls = {"n": 0, "last_prompt": None}

        def fake_text(*_args, **_kw):
            text_calls["n"] += 1
            raise GeminiTextExtractionError(f"simulated text failure #{text_calls['n']}")

        def fake_image(prompt, api_key, **_kw):
            image_calls["n"] += 1
            image_calls["last_prompt"] = prompt
            # 4096 bytes 以上のダミー PNG (main() のサイズチェックは別テスト)
            return b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

        fm = {"title": "Test Title", "summary": "Test Japanese summary article"}

        with patch("generate_hero_image._call_gemini_text", side_effect=fake_text), \
             patch("generate_hero_image.call_gemini_image", side_effect=fake_image):
            png, meta = generate_hero_with_fallback("wsj", fm, "FAKE_KEY")

        self.assertEqual(
            text_calls["n"], 2,
            f"expected 2 text attempts before fallback, got {text_calls['n']}"
        )
        self.assertEqual(image_calls["n"], 1, "legacy path should call image API exactly once")
        self.assertEqual(
            meta["path"], "legacy",
            f"expected fallback path='legacy', got '{meta['path']}'"
        )
        self.assertIsNone(meta["concept"], "fallback path must not carry a concept dict")
        # legacy prompt 特有の文言 (COMMON_STYLE から)
        self.assertIn(
            "Editorial magazine hero photograph", image_calls["last_prompt"] or "",
            "legacy prompt should include the COMMON_STYLE preamble"
        )
        self.assertTrue(png.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
