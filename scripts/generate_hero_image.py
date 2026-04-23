#!/usr/bin/env python3
"""
Gemini 2.5 Flash Image (Nano Banana) でニュースレター記事の hero 画像を生成。

処理フロー:
    1. content/<source>/<date>.md から frontmatter (title / summary) を読込
    2. セクション別スタイル + 記事内容で editorial 調のプロンプト生成
    3. Gemini API (generativelanguage.googleapis.com) に POST
    4. レスポンスの base64 画像をデコードして static/images/<source>/<date>.png に保存
    5. content/<source>/<date>.md の frontmatter に
       hero_image: "/images/<source>/<date>.png" を注入 (既存なら上書き)

失敗時は exit 2 を返し、ワークフロー側で non-blocking に扱う。
翻訳 MD が無い/壊れている場合も exit 2 (翻訳成果を上書きしない)。

Usage:
    python scripts/generate_hero_image.py <source> <date>

Env (必須):
    GEMINI_API_KEY         Google AI Studio で発行した API Key (AIza... 形式)

Env (任意):
    GEMINI_MODEL           既定: gemini-2.5-flash-image
    GEMINI_ENDPOINT        既定: https://generativelanguage.googleapis.com/v1beta
    GEMINI_TIMEOUT         既定: 120  秒
    GEMINI_RETRIES         既定: 3

無料枠 (2026 年時点):
    500 画像/日 @ 1024×1024, 250k TPM, クレカ登録不要
    本システムは 7 媒体 × 1 枚/日 = 7 枚/日 で無料枠の 1.4%
"""

import sys
import os
import re
import json
import base64
import time
import struct
import logging
import urllib.request
import urllib.error
from typing import Optional, Tuple


# v1.3: gemini-2.5-flash-image が GS 級 illustration 出力で安定 (Test C 検証済)。
# gemini-3.1-flash-image-preview (Nano Banana 2) は preview で黒画像バグ確認のため
# OPT-IN とする (GEMINI_MODEL=gemini-3.1-flash-image-preview で上書き時のみ使用)。
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-image")
FALLBACK_IMAGE_MODEL = os.environ.get("GEMINI_FALLBACK_IMAGE_MODEL", "gemini-2.5-flash-image")
DEFAULT_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
DEFAULT_ENDPOINT = os.environ.get(
    "GEMINI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta"
)
DEFAULT_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "120"))
DEFAULT_RETRIES = int(os.environ.get("GEMINI_RETRIES", "3"))

# 429 (レート制限) 受信時の backoff (秒)
BACKOFF_DELAYS = [15, 30, 60]


# ---------- 媒体別スタイル辞書 (v1.1 SPEC Section 4) ----------
# 新セクション追加時はこの 1 箇所を編集するだけで対応可能。
# Economist は 2026-04-22 時点で日次配信実績ゼロのため除外。配信開始時に追加する。
STYLE_DICTIONARY = {
    # --- Editorial (エディトリアル風刺画) ---
    "wsj": {
        "category": "editorial",
        "style_keywords": (
            "traditional editorial illustration, sophisticated conceptual metaphor, "
            "muted earth tones, subtle crosshatching texture, "
            "reminiscent of The Wall Street Journal opinion pages"
        ),
        "tone": "serious, weighty, intellectually refined",
    },
    "nyt-bn": {
        "category": "editorial",
        "style_keywords": (
            "modern editorial illustration, bold conceptual metaphor, "
            "limited color palette with one accent color, clean composition, "
            "reminiscent of New York Times front-page art"
        ),
        "tone": "urgent, contemporary, journalistic",
    },
    "nyt-op": {
        "category": "editorial",
        "style_keywords": (
            "bold contemporary satirical illustration, daring conceptual metaphor, "
            "high-contrast color blocks, reminiscent of New York Times Op-Ed section"
        ),
        "tone": "provocative, opinionated, modern",
    },
    "buysiders": {
        "category": "editorial",
        "style_keywords": (
            "financial editorial illustration, M&A metaphor imagery "
            "(handshakes, merging shapes, chessboards), "
            "navy and gold palette, sophisticated minimalism"
        ),
        "tone": "corporate, strategic, high-stakes",
    },

    # --- Lifestyle (モダンフラットアート) ---
    "skift": {
        "category": "lifestyle",
        "style_keywords": (
            "modern flat digital illustration, textured brush strokes, "
            "soft gradients, travel and hospitality scenes, "
            "serene atmosphere, clean and aspirational"
        ),
        "tone": "optimistic, aspirational, polished",
    },
    "business-insider": {
        "category": "lifestyle",
        "style_keywords": (
            "modern flat digital illustration, textured brush strokes, "
            "subtle gradients, contemporary urban or business scenes, "
            "clean composition with tactile detail"
        ),
        "tone": "accessible, contemporary, visually rich",
    },

    # --- Editorial-playful (第3カテゴリ) ---
    "short-squeez": {
        "category": "editorial-playful",
        "style_keywords": (
            "playful financial editorial illustration, Wall Street metaphor imagery, "
            "slightly irreverent tone, clean vector-style with texture accents, "
            "tinted or textured backgrounds (cream, pale navy, warm gray)"
        ),
        "tone": "witty, finance-savvy, slightly irreverent",
    },
}


# v1.3: セクション別スタイル — Pattern A (知的風刺) / Pattern B (洗練ライフスタイル) 2 分類
#   Pattern A: WSJ / NYT-BN / NYT-OP / Buysiders / Short-Squeez / Economist
#   Pattern B: Skift / Business-Insider
# 全エントリ illustration 指向 (COMMON_STYLE が photorealistic を禁止しているため合致)
SECTION_STYLES = {
    # ---- Pattern A: 知的風刺 (editorial illustration) ----
    "wsj": (
        "traditional editorial illustration of a Wall Street financial metaphor "
        "(stock ticker, skyline, currency), subtle crosshatching texture, "
        "muted earth tones with navy accents, "
        "reminiscent of WSJ opinion-page illustration"
    ),
    "nyt-bn": (
        "modern editorial illustration of a breaking-news visual metaphor, "
        "bold composition with one accent color against muted palette, "
        "clean lines and decisive shapes, "
        "reminiscent of NYT front-page conceptual art"
    ),
    "nyt-op": (
        "bold satirical editorial illustration, daring conceptual metaphor, "
        "high-contrast color blocks, wry visual wit, "
        "reminiscent of NYT Op-Ed section"
    ),
    "buysiders": (
        "financial editorial illustration of M&A or capital-markets metaphor "
        "(handshake, merging shapes, chess pieces, boardroom), "
        "navy and gold palette, sophisticated minimalism"
    ),
    "short-squeez": (
        "playful editorial illustration of a Wall Street scene, "
        "witty and slightly irreverent tone, vector-style with texture accents, "
        "tinted cream or pale navy background"
    ),
    "economist": (
        "abstract conceptual editorial illustration of an economic theme, "
        "geometric composition, muted editorial palette"
    ),
    # ---- Pattern B: 洗練ライフスタイル (modern flat digital illustration) ----
    "skift": (
        "modern flat digital illustration of a travel or hospitality scene, "
        "soft gradients, textured brush strokes, serene and aspirational atmosphere, "
        "sunlight, positive energy"
    ),
    "business-insider": (
        "modern flat digital illustration of a contemporary urban or business scene, "
        "textured brush strokes, subtle gradients, clean composition, "
        "contemporary positive energy"
    ),
}

# v1.3: 写真調 → illustration 指向に全面書換 (§8.2 で特定された legacy fallback NG を解消)
DEFAULT_STYLE = (
    "editorial illustration, conceptual metaphor, hand-drawn aesthetic, muted palette"
)

# 全セクション共通のスタイル指示 — illustration 強制 (ポジ/ネガ両指定)
COMMON_STYLE = (
    "Editorial illustration hero image in the style of The New Yorker / The Economist / "
    "WSJ Op-Ed cover art. Hand-drawn or vector illustration with textured brush strokes, "
    "bold conceptual metaphor, muted editorial palette "
    "(terracotta / cream / walnut / deep navy / charcoal / soft gold accents). "
    "Composition leaves central negative space for text overlay. "
    "STRICT CONSTRAINTS: illustration ONLY (NOT photorealistic, NOT a photograph, "
    "NOT a 3D render, NOT CGI), hand-drawn aesthetic, "
    "no text, no letters, no words, no logos, no visible human faces, "
    "no watermarks, no signage, no UI elements, no charts with labels."
)


# ---------- Frontmatter パース ----------
def parse_frontmatter(md_text: str) -> dict:
    """軽量 YAML サブセット (文字列のみ抽出)。"""
    m = re.match(r"^---\n(.*?)\n---\n", md_text, re.DOTALL)
    if not m:
        return {}
    fm_text = m.group(1)
    fm: dict = {}
    for line in fm_text.split("\n"):
        mm = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)$", line)
        if not mm:
            continue
        k = mm.group(1)
        v = mm.group(2).strip()
        if v.startswith('"') and v.endswith('"') and len(v) >= 2:
            v = v[1:-1]
        fm[k] = v
    return fm


# ---------- プロンプト生成 ----------
def build_prompt(source: str, fm: dict) -> str:
    title = fm.get("title", "").strip()
    summary = fm.get("summary", "").strip()
    if len(summary) > 260:
        summary = summary[:260]

    base = SECTION_STYLES.get(source, DEFAULT_STYLE)

    parts = [
        COMMON_STYLE,
        base + ".",
    ]
    if title:
        parts.append(f"Article theme: {title}.")
    if summary:
        parts.append(f"Context: {summary}.")

    prompt = " ".join(parts)
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt


# ---------- v1.1: 視覚概念抽出 (2段階プロンプトの 1段目) ----------

class GeminiTextExtractionError(Exception):
    """Gemini text API (JSON 抽出) の呼出・パース失敗を表す。"""


class GeminiImageGenerationError(Exception):
    """Gemini image API の呼出失敗を表す。"""


# SPEC v1.1 Section 3.3 (v1.3 更新): System Prompt
# v1.3 変更: JSON スキーマを末尾に明示列挙し、"STEP N -" プレフィックスが
#           field 名に混入するのを防止 (2026-04-23 検証で "step_1_core_theme" 等が
#           返されたインシデント対策)
VISUAL_CONCEPT_SYSTEM_PROMPT = """You are a visual concept director for a financial/business newsletter dashboard.
Given an article summary, think through the following in 3 steps, then output ONLY the JSON object specified at the bottom.

THINKING STEPS (internal — do NOT include in output):
1. Core Theme: Identify ONE central topic keyword.
2. Visual Metaphor: Choose ONE concrete object or action that symbolizes the theme.
   - For abstract concepts (inflation, recession, negotiation), use physical metaphors
     (a heavy weight, a stalled engine, a chessboard).
   - For lifestyle/travel/tech, use scene-based imagery (a cyclist on a ridge,
     a traveler with luggage, a modern workspace).
3. Contextual Detail: Add ONE specific element from the article
   (location, industry, character attribute).
4. Primary Subject Noun: the single most important physically drawable object
   that MUST appear as the visual anchor.

RULES:
- Never return abstract concepts as primary_subject_noun. Always a physical,
  drawable object (e.g., "a cyclist", "a skyscraper", "a golden coin", NOT "growth" or "risk").
- All field values must be in English.
- Output ONLY valid JSON, no preamble, no markdown fences, no code blocks.

REQUIRED OUTPUT SCHEMA (use EXACTLY these field names — no prefixes like "step_1_"):
{
  "core_theme": "<one-keyword central topic>",
  "visual_metaphor": "<concrete object or action phrase>",
  "contextual_detail": "<one specific element from the article>",
  "primary_subject_noun": "<the single most important drawable object>"
}"""


def _call_gemini_text(user_message: str, system_instruction: str, api_key: str,
                      model: str = DEFAULT_TEXT_MODEL,
                      endpoint: str = DEFAULT_ENDPOINT,
                      timeout: int = DEFAULT_TIMEOUT,
                      retries: int = DEFAULT_RETRIES) -> str:
    """
    Gemini 2.5 Flash (text) に POST し、生成テキスト (JSON 文字列想定) を返す。
    HTTP 429 / 5xx は exponential backoff で最大 retries 回リトライ。
    SPEC v1.1 Section 3.4 のパラメータ準拠。
    """
    url = f"{endpoint.rstrip('/')}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": user_message}],
        }],
        "systemInstruction": {
            "parts": [{"text": system_instruction}],
        },
        "generationConfig": {
            "temperature": 0,
            # v1.3: 300 では thinking mode (thoughtsTokenCount≈285) で枯渇するため 1024 に増量
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
            # v1.3: thinking mode を完全にオフにして出力 token 枠を確保
            # (2026-04-22 検証で finishReason=MAX_TOKENS / thoughtTokens=285 を確認)
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_text = resp.read().decode("utf-8")
            data = json.loads(resp_text)

            for candidate in data.get("candidates", []):
                content = candidate.get("content", {}) or {}
                for part in content.get("parts", []) or []:
                    text = part.get("text")
                    if text:
                        return text

            finish = data.get("candidates", [{}])[0].get("finishReason", "UNKNOWN")
            raise GeminiTextExtractionError(
                f"no text in response (finishReason={finish}); raw={resp_text[:400]}"
            )

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            last_error = f"HTTP {e.code}: {e.reason}; body={err_body}"
            if e.code == 429 and attempt < retries:
                wait = BACKOFF_DELAYS[min(attempt, len(BACKOFF_DELAYS) - 1)]
                print(f"[gemini-text] 429 rate limit, attempt {attempt + 1}/{retries + 1}. "
                      f"backing off {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code >= 500 and attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"[gemini-text] HTTP {e.code}, attempt {attempt + 1}/{retries + 1}. "
                      f"retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise GeminiTextExtractionError(last_error)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = f"network error: {e}"
            if attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"[gemini-text] {last_error}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise GeminiTextExtractionError(last_error)

    raise GeminiTextExtractionError(f"all {retries + 1} attempts failed: {last_error}")


_REQUIRED_CONCEPT_FIELDS = (
    "core_theme",
    "visual_metaphor",
    "contextual_detail",
    "primary_subject_noun",
)


def _parse_concept_json(raw_text: str) -> dict:
    """
    Gemini の返す JSON 文字列を dict に変換し、必須フィールドを検証。
    JSON パース失敗 / 必須キー欠落で GeminiTextExtractionError を raise。

    v1.3: Gemini がしばしば以下のような prefix / code fence を付加するため堅牢化:
      1. "Here is the JSON requested:\n```json\n{...}\n```"
      2. "```json\n{...}\n```"
      3. "```\n{...}\n```"
    対策: (a) 先頭の非 JSON prefix を削除 → (b) markdown fence を剥ぐ
         → (c) それでも失敗したら最初の {...} ブロックを正規表現で抽出
    """
    text = raw_text.strip()
    # (a) markdown code fence を剥ぐ
    text = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```\s*$", "", text)
    text = text.strip()
    # (b) 冒頭に "Here is the JSON:" 等の prefix がある場合、最初の { から抽出
    if not text.startswith("{"):
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            text = m.group(0)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise GeminiTextExtractionError(f"JSON parse failed: {e}; raw={raw_text[:300]}")

    # v1.3: Gemini が "step_1_core_theme" のような prefixed field を返すケースに対応
    # (system prompt の "STEP 1 -" を文字通り field 名に反映してしまう現象)
    if isinstance(obj, dict):
        normalized = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                continue
            # step_1_, step_2_, step_3_, step_N_ のプレフィックスを剥ぐ
            nk = re.sub(r"^step_\d+_", "", k.strip().lower())
            # camelCase → snake_case 的に軽く正規化 (coreTheme → core_theme)
            nk = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", nk).lower()
            if nk not in normalized:
                normalized[nk] = v
        # 元キーも残す (defensive: _parse_concept_json の既存バリデーションで使用)
        for orig_k in list(obj.keys()):
            if isinstance(orig_k, str) and orig_k not in normalized:
                normalized.setdefault(orig_k, obj[orig_k])
        obj = normalized

    if not isinstance(obj, dict):
        raise GeminiTextExtractionError(
            f"expected object, got {type(obj).__name__}; raw={raw_text[:300]}"
        )

    missing = [k for k in _REQUIRED_CONCEPT_FIELDS if not obj.get(k)]
    if missing:
        raise GeminiTextExtractionError(
            f"missing fields {missing}; raw={raw_text[:300]}"
        )

    return {k: str(obj[k]).strip() for k in _REQUIRED_CONCEPT_FIELDS}


# SPEC v1.1 Section 7.1: 抽象名詞ブラックリスト (強化版)
ABSTRACT_NOUN_BLACKLIST = {
    # v1.0 からの引き継ぎ
    "growth", "risk", "trend", "market", "economy", "strategy",
    "future", "change", "impact",
    # v1.1 追加 (金融・ビジネスニュースで頻出)
    "innovation", "disruption", "transformation", "opportunity", "challenge",
    "landscape", "dynamics", "ecosystem", "momentum", "outlook",
    # さらなる抽象語
    "potential", "value", "performance", "competition", "advantage",
}

# SPEC v1.1 Section 7.3: リトライ時の追加指示
RETRY_EXTRA_INSTRUCTION = (
    "Your previous output was too abstract. The primary_subject_noun must be "
    "a physically drawable object that a child could recognize. "
    'Examples of GOOD nouns: "a cyclist", "a skyscraper", "a golden coin", '
    '"a chess piece", "a suitcase". Retry with a more concrete noun.'
)

_ARTICLES = {"a", "an", "the"}


def _strip_articles_and_split(phrase: str) -> list:
    """冠詞 (a/an/the) を除外した単語リストを返す。"""
    tokens = re.findall(r"[A-Za-z']+", phrase.lower())
    return [t for t in tokens if t not in _ARTICLES]


def _needs_retry(concept: dict) -> tuple:
    """
    SPEC v1.1 Section 7.2 のリトライ判定。
    Returns: (needs_retry: bool, reason: str)
    """
    noun = concept.get("primary_subject_noun", "") or ""
    words = _strip_articles_and_split(noun)

    # (1) ブラックリストのいずれかを含む (小文字比較)
    noun_lower_words = set(words)
    hit = noun_lower_words & ABSTRACT_NOUN_BLACKLIST
    if hit:
        return True, f"abstract_word={sorted(hit)}"

    # v1.3: SPEC v1.1 §7.2 の "2 語以下で retry" は
    #       SPEC §7.3 の GOOD 例 ("a cyclist", "a suitcase" = 1 語) と矛盾。
    #       冠詞を除いて 1 語 (concrete single-noun) は十分 drawable なので
    #       "0 語 (空文字)" のみを再試行対象とする。
    if len(words) < 1:
        return True, f"too_short={len(words)}_words"

    return False, ""


def extract_visual_concept_with_retry(summary: str, api_key: str) -> dict:
    """
    SPEC v1.1 Section 7.2 / 7.3 準拠の視覚概念抽出。
    - 1 回目: 通常の system prompt で抽出
    - 抽象名詞 / 語数不足 / JSON パース失敗のいずれかで 1 回だけリトライ
    - リトライも失敗したら GeminiTextExtractionError を raise
      (呼出側で Section 7.4 のフォールバックに誘導)
    """
    # 1 回目
    try:
        concept = extract_visual_concept(summary, api_key)
        needs, reason = _needs_retry(concept)
        if not needs:
            return concept
        print(f"[gemini-text] retry triggered: {reason}", file=sys.stderr)
    except GeminiTextExtractionError as e:
        print(f"[gemini-text] first attempt failed ({e}); retrying once", file=sys.stderr)

    # 2 回目 (リトライ指示付き)
    concept = extract_visual_concept(
        summary, api_key, extra_instruction=RETRY_EXTRA_INSTRUCTION
    )
    needs, reason = _needs_retry(concept)
    if needs:
        raise GeminiTextExtractionError(
            f"retry still produced unusable concept: {reason}; concept={concept}"
        )
    return concept


def extract_visual_concept(summary: str, api_key: str,
                           extra_instruction: str = "") -> dict:
    """
    summary から視覚概念を JSON 抽出する (SPEC v1.1 Section 3.2 / 3.3 / 3.4 / 3.5)。

    Returns: dict with keys
      - core_theme
      - visual_metaphor
      - contextual_detail
      - primary_subject_noun

    Raises: GeminiTextExtractionError on API failure or JSON parse failure.

    Note: ABSTRACT_NOUN_BLACKLIST / リトライロジックは呼出側 (Step 5) で扱う。
    """
    # SPEC 3.5: prompt injection 防御のため summary を """ で囲む
    user_message = (
        "Extract the visual concept from the following article summary:\n\n"
        '"""\n'
        f"{summary}\n"
        '"""\n\n'
        "Output JSON only."
    )
    if extra_instruction:
        user_message += "\n\n" + extra_instruction

    raw = _call_gemini_text(user_message, VISUAL_CONCEPT_SYSTEM_PROMPT, api_key)
    return _parse_concept_json(raw)


# ---------- v1.1: 最終プロンプト組み立て (2段階プロンプトの 2段目) ----------

def build_hero_prompt(subject_noun: str, metaphor: str, context: str,
                      style_keywords: str, category: str) -> str:
    """
    Gemini 2.5 Flash Image 向けの最終プロンプトを組み立てる (SPEC v1.1 Section 5)。

    CRITICAL: 名詞の順序厳守 (先頭が最も強く描画に反映される)
      1. PRIMARY SUBJECT (主役の物体) - 最優先
      2. METAPHORICAL CONTEXT (比喩の文脈)
      3. CONTEXTUAL DETAIL (固有の詳細)
      4. STYLE (媒体固有のスタイル)
      5. CONSTRAINTS (共通制約)
    """
    if category == "editorial":
        composition = "a conceptual metaphor illustration featuring"
        background_directive = ""  # editorial は白背景 OK (意図的スタイル)
    elif category == "editorial-playful":
        composition = "a playful conceptual illustration featuring"
        background_directive = (
            "avoid pure white backgrounds; "
            "use tinted or textured backgrounds (cream, pale navy, warm gray). "
        )
    else:  # lifestyle
        composition = "a refined lifestyle scene featuring"
        background_directive = (
            "avoid pure white backgrounds; "
            "use tinted or textured backgrounds (cream, pale navy, warm gray). "
        )

    prompt = (
        f"{composition} {subject_noun}, "
        f"symbolizing {metaphor}, "
        f"with contextual elements of {context}. "
        f"Style: {style_keywords}. "
        f"Composition: 16:9 aspect ratio, centered focal point, "
        f"room for overlay text on the lower third (but do NOT include any text). "
        f"{background_directive}"
        f"STRICT CONSTRAINTS: illustration only (NOT photorealistic), "
        f"absolutely no text, no letters, no words, no logos, no watermarks, "
        f"no UI elements, no charts with labels."
    )
    return prompt


# ---------- Gemini API 呼出 ----------
def call_gemini_image(prompt: str, api_key: str,
                      model: str = DEFAULT_MODEL,
                      endpoint: str = DEFAULT_ENDPOINT,
                      timeout: int = DEFAULT_TIMEOUT,
                      retries: int = DEFAULT_RETRIES,
                      _fallback_attempted: bool = False) -> bytes:
    """
    Gemini Image API に POST し、PNG バイト列を返す。
    HTTP 429 は exponential backoff で最大 retries 回リトライ。
    その他のエラーは即 raise。

    v1.3: DEFAULT_MODEL (Nano Banana 2 preview) が HTTP 404 (モデル無効) を返したら
          FALLBACK_IMAGE_MODEL (gemini-2.5-flash-image) に 1 度だけ自動切替して再試行。
    """
    url = f"{endpoint.rstrip('/')}/models/{model}:generateContent?key={api_key}"
    # SPEC v1.1 Section 6.2: imageConfig.aspectRatio で 16:9 を API 側から強制。
    # prompt テキストだけでは Gemini はデフォルト 1024x1024 を返す傾向が実証済み。
    payload = {
        "contents": [{
            "parts": [{"text": prompt}],
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": "16:9",
            },
        },
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_text = resp.read().decode("utf-8")
            data = json.loads(resp_text)

            # candidates[].content.parts[].inlineData.data に base64 PNG
            for candidate in data.get("candidates", []):
                content = candidate.get("content", {}) or {}
                for part in content.get("parts", []) or []:
                    # snake_case と camelCase 両対応
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        return base64.b64decode(inline["data"])

            # 画像 part が見つからない → プロンプトがポリシー違反の可能性
            finish = data.get("candidates", [{}])[0].get("finishReason", "UNKNOWN")
            raise GeminiImageGenerationError(
                f"no image in response (finishReason={finish}); "
                f"raw={resp_text[:400]}"
            )

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            last_error = f"HTTP {e.code}: {e.reason}; body={err_body}"
            # v1.3: 404 (model not found) のみ、FALLBACK_IMAGE_MODEL に 1 度だけ自動切替
            if e.code == 404 and not _fallback_attempted and model != FALLBACK_IMAGE_MODEL:
                print(
                    f"[gemini] ⚠ model '{model}' returned 404; "
                    f"falling back to '{FALLBACK_IMAGE_MODEL}'",
                    file=sys.stderr,
                )
                return call_gemini_image(
                    prompt, api_key,
                    model=FALLBACK_IMAGE_MODEL,
                    endpoint=endpoint,
                    timeout=timeout,
                    retries=retries,
                    _fallback_attempted=True,
                )
            if e.code == 429 and attempt < retries:
                wait = BACKOFF_DELAYS[min(attempt, len(BACKOFF_DELAYS) - 1)]
                print(f"[gemini] 429 rate limit, attempt {attempt + 1}/{retries + 1}. "
                      f"backing off {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code >= 500 and attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"[gemini] HTTP {e.code}, attempt {attempt + 1}/{retries + 1}. "
                      f"retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise GeminiImageGenerationError(last_error)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = f"network error: {e}"
            if attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"[gemini] {last_error}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise GeminiImageGenerationError(last_error)

    raise GeminiImageGenerationError(f"all {retries + 1} attempts failed: {last_error}")


# ---------- v1.1: 2段階プロンプト + フォールバック経路 (SPEC Section 7.4) ----------

def generate_hero_with_fallback(
    source: str, fm: dict, api_key: str
) -> Tuple[bytes, dict]:
    """
    SPEC v1.1 Section 7.4 のオーケストレーション関数。

    1. STYLE_DICTIONARY に source が登録されていれば 2 段階プロンプト経路:
         extract_visual_concept_with_retry → build_hero_prompt → call_gemini_image
    2. Gemini text (JSON抽出) が 2 回失敗したら current legacy 経路にデグレード:
         build_prompt (SECTION_STYLES) → call_gemini_image
    3. Gemini image 生成が失敗したら GeminiImageGenerationError を raise
       (main() 側で exit 2 として hero 無しで記事配信を継続)

    Returns:
      (png_bytes, meta): meta = {"path": "2-stage"|"legacy", "concept": dict|None}
    Raises:
      GeminiImageGenerationError
    """
    summary = (fm.get("summary") or "").strip()
    meta: dict = {"path": "", "concept": None}

    # 1. Primary path (2-stage prompt)
    if source in STYLE_DICTIONARY and summary:
        try:
            concept = extract_visual_concept_with_retry(summary, api_key)
            style = STYLE_DICTIONARY[source]
            prompt = build_hero_prompt(
                subject_noun=concept["primary_subject_noun"],
                metaphor=concept["visual_metaphor"],
                context=concept["contextual_detail"],
                style_keywords=style["style_keywords"],
                category=style["category"],
            )
            log_hero_debug(f"2-stage concept: {concept}")
            log_hero_debug(f"2-stage final prompt: {prompt}")
            print(
                f"[hero] v1.1 2-stage path: core_theme='{concept['core_theme']}' "
                f"subject='{concept['primary_subject_noun']}'",
                file=sys.stderr,
            )
            png = call_gemini_image(prompt, api_key)
            meta["path"] = "2-stage"
            meta["concept"] = concept
            return png, meta
        except GeminiTextExtractionError as e:
            print(
                f"[hero] ⚠ Gemini text failed ({e}); "
                f"falling back to direct-summary prompt",
                file=sys.stderr,
            )
            log_hero_debug(f"2-stage text extraction failed: {e}")
            # fall through to legacy path

    # 2. Fallback path (legacy direct summary)
    prompt = build_prompt(source, fm)
    log_hero_debug(f"legacy prompt: {prompt}")
    print(f"[hero] legacy direct-summary path (source={source})", file=sys.stderr)
    png = call_gemini_image(prompt, api_key)
    meta["path"] = "legacy"
    return png, meta


# ---------- v1.1: PNG 寸法検知 (aspect ratio 16:9 の結果監視) ----------

# 16:9 からの許容乖離率 (±5%)
ASPECT_RATIO_TOLERANCE = 0.05
TARGET_ASPECT_RATIO = 16.0 / 9.0


def detect_image_dimensions(img_bytes: bytes) -> tuple:
    """
    画像ヘッダから (width, height, format) を返す。対応: PNG / JPEG / WebP。
    v1.3: Nano Banana 2 が PNG 以外 (JPEG / WebP) を返すケースに対応。
    未対応 / 破損の場合は (0, 0, "unknown") を返す。stdlib のみ依存。
    """
    if len(img_bytes) < 24:
        return (0, 0, "too_short")
    # ---- PNG: signature \x89PNG\r\n\x1a\n + IHDR ----
    if img_bytes[:8] == b"\x89PNG\r\n\x1a\n" and img_bytes[12:16] == b"IHDR":
        try:
            width, height = struct.unpack(">II", img_bytes[16:24])
            return (width, height, "png")
        except struct.error:
            return (0, 0, "png_corrupt")
    # ---- JPEG: SOI (FF D8 FF) ... SOFn marker で dimensions 取得 ----
    if img_bytes[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(img_bytes):
            if img_bytes[i] != 0xFF:
                i += 1
                continue
            # marker
            marker = img_bytes[i + 1]
            # Skip padding 0xFF bytes
            while marker == 0xFF and i + 1 < len(img_bytes):
                i += 1
                marker = img_bytes[i + 1]
            # SOFn markers: C0-C3, C5-C7, C9-CB, CD-CF (frame start)
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                try:
                    height, width = struct.unpack(">HH", img_bytes[i + 5:i + 9])
                    return (width, height, "jpeg")
                except struct.error:
                    return (0, 0, "jpeg_corrupt")
            # Skip this segment: length is next 2 bytes (big-endian), includes the length bytes themselves
            try:
                seg_len = struct.unpack(">H", img_bytes[i + 2:i + 4])[0]
                i += 2 + seg_len
            except struct.error:
                return (0, 0, "jpeg_corrupt")
        return (0, 0, "jpeg_no_sof")
    # ---- WebP: "RIFF....WEBP" + VP8/VP8L/VP8X chunk ----
    if img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
        chunk = img_bytes[12:16]
        try:
            if chunk == b"VP8 ":
                # lossy: after "VP8 " (4) + chunk size (4) + 3 bytes frame tag = offset 23
                width, height = struct.unpack("<HH", img_bytes[26:30])
                return (width & 0x3FFF, height & 0x3FFF, "webp")
            elif chunk == b"VP8L":
                # lossless: bitstream starts at offset 20, signature 0x2F + 4 bytes dim packed
                b = img_bytes[21:25]
                width = ((b[1] & 0x3F) << 8) | b[0]
                height = ((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6)
                return (width + 1, height + 1, "webp")
            elif chunk == b"VP8X":
                # extended: width/height are 24-bit little-endian at offset 24/27
                width = img_bytes[24] | (img_bytes[25] << 8) | (img_bytes[26] << 16)
                height = img_bytes[27] | (img_bytes[28] << 8) | (img_bytes[29] << 16)
                return (width + 1, height + 1, "webp")
        except (struct.error, IndexError):
            return (0, 0, "webp_corrupt")
    return (0, 0, "unknown")


# v1.3: 後方互換のため旧関数名も残す
def detect_png_dimensions(png_bytes: bytes) -> tuple:
    """Deprecated: use detect_image_dimensions. Returns (width, height) only."""
    w, h, _ = detect_image_dimensions(png_bytes)
    return (w, h)


def warn_if_not_16x9(png_bytes: bytes, label: str) -> None:
    """
    画像の実寸を検出し、16:9 ±5% から外れていれば stderr に warning を出す。
    v1.3: PNG / JPEG / WebP に対応 (Nano Banana 2 は PNG 以外を返すことがある)。
    """
    width, height, fmt = detect_image_dimensions(png_bytes)
    if width == 0 or height == 0:
        print(f"[hero] ⚠ {label}: could not detect image dimensions (format={fmt})", file=sys.stderr)
        return

    actual_ratio = width / height
    deviation = abs(actual_ratio - TARGET_ASPECT_RATIO) / TARGET_ASPECT_RATIO
    if deviation > ASPECT_RATIO_TOLERANCE:
        print(
            f"[hero] ⚠ {label}: aspect ratio off-target "
            f"(got {width}x{height} = {actual_ratio:.3f}, "
            f"expected 16:9 = {TARGET_ASPECT_RATIO:.3f}, "
            f"deviation={deviation*100:.1f}%, format={fmt})",
            file=sys.stderr,
        )
    else:
        print(
            f"[hero] ✓ {label}: {width}x{height} (aspect OK, deviation={deviation*100:.1f}%, format={fmt})",
            file=sys.stderr,
        )


# ---------- Frontmatter 注入 ----------
def inject_hero_image(md_path: str, image_path: str) -> bool:
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", content, re.DOTALL)
    if not m:
        print(f"[inject] no frontmatter in {md_path}", file=sys.stderr)
        return False
    open_tag, fm, close_tag, body = m.groups()

    if re.search(r"^hero_image:", fm, re.MULTILINE):
        new_fm = re.sub(
            r"^hero_image:.*$",
            f'hero_image: "{image_path}"',
            fm,
            flags=re.MULTILINE,
        )
    else:
        new_fm = fm.rstrip() + f'\nhero_image: "{image_path}"'

    new_content = f"{open_tag}{new_fm}{close_tag}{body}"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


# ---------- v1.1 Section 8: ログ出力 ----------

# logs/ は ~/newsletter-dashboard/logs/ 固定 (SPEC 8.1)
_LOG_ROOT = os.path.join(os.path.expanduser("~"), "newsletter-dashboard", "logs")
_LOG_PATH = os.path.join(_LOG_ROOT, "hero_generation.log")

# SPEC 2.3: 1,000 RPD 超過で警告
_LOG_DAILY_WARN_THRESHOLD = 1000
_LOG_DAILY_QUOTA = 1500  # Gemini 無料枠

_logger_initialized = False


def _mask_home(p: str) -> str:
    """ホームディレクトリのパスを ~ に置換 (SPEC 8.4)。"""
    home = os.path.expanduser("~")
    return p.replace(home, "~") if home and home in p else p


def _get_logger() -> logging.Logger:
    """hero_generation ロガーを一度だけ初期化して返す。"""
    global _logger_initialized
    logger = logging.getLogger("hero_generation")
    if _logger_initialized:
        return logger

    os.makedirs(_LOG_ROOT, exist_ok=True)
    logger.setLevel(logging.DEBUG)

    debug_enabled = bool(os.environ.get("HERO_LOG_DEBUG"))

    fh = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    fh.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    fh.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)
    logger.propagate = False
    _logger_initialized = True
    return logger


def _count_daily_calls(log_path: str) -> int:
    """今日の INFO ログ行数を数える (daily_calls 計測用)。"""
    today = time.strftime("%Y-%m-%d")
    if not os.path.exists(log_path):
        return 0
    try:
        count = 0
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(f"[{today}") and " INFO " in line:
                    count += 1
        return count
    except OSError:
        return 0


def log_hero_event(
    media: str,
    slug: str,
    result: str,
    duration_sec: float,
    concept: Optional[dict] = None,
    path_taken: str = "",
    error: str = "",
) -> None:
    """
    SPEC v1.1 Section 8.3 形式の INFO ログを 1 行で出力。
    呼出毎に daily_calls を再計算し、1,000 件超で WARN を追加出力。

    SPEC 8.4: GEMINI_API_KEY はここで受け取らない / summary 本文も INFO に出さない。
    """
    logger = _get_logger()
    daily_calls = _count_daily_calls(_LOG_PATH) + 1

    parts = [
        f"article_slug={slug}",
        f"media={media}",
    ]
    if path_taken:
        parts.append(f"path={path_taken}")
    if concept:
        core = (concept.get("core_theme") or "").replace(" ", "_")
        subj = (concept.get("primary_subject_noun") or "").replace('"', "'")
        parts.append(f"core_theme={core}")
        parts.append(f'subject_noun="{subj}"')
    parts.append(f"result={result}")
    parts.append(f"duration={duration_sec:.1f}s")
    parts.append(f"daily_calls={daily_calls}/{_LOG_DAILY_QUOTA}")
    if error:
        # エラー文字列に API key が含まれないよう念のためマスク
        safe_error = error.replace(os.environ.get("GEMINI_API_KEY", ""), "***") \
            if os.environ.get("GEMINI_API_KEY") else error
        parts.append(f"error={safe_error!r}")

    logger.info(" ".join(parts))

    if daily_calls > _LOG_DAILY_WARN_THRESHOLD:
        logger.warning(
            f"daily_calls={daily_calls} exceeds warning threshold "
            f"{_LOG_DAILY_WARN_THRESHOLD}/{_LOG_DAILY_QUOTA}"
        )


def log_hero_debug(msg: str) -> None:
    """HERO_LOG_DEBUG=1 の時のみログに全文を残す (SPEC 8.2 DEBUG レベル)。"""
    if not os.environ.get("HERO_LOG_DEBUG"):
        return
    _get_logger().debug(msg)


# ---------- main ----------
def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: generate_hero_image.py <source> <date>", file=sys.stderr)
        return 2
    source, date = sys.argv[1], sys.argv[2]

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[hero] GEMINI_API_KEY not set", file=sys.stderr)
        return 2

    md_path = f"content/{source}/{date}.md"
    if not os.path.exists(md_path):
        print(f"[hero] missing translated MD: {md_path}", file=sys.stderr)
        return 2

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    fm = parse_frontmatter(md_text)
    if not fm.get("title"):
        print(f"[hero] no title in frontmatter of {md_path}", file=sys.stderr)
        return 2

    print(f"[hero] {source}/{date}: starting (v1.1 2-stage prompt)", file=sys.stderr)

    slug = f"{source}-{date}"
    t0 = time.monotonic()
    meta: dict = {"path": "", "concept": None}

    try:
        png_bytes, meta = generate_hero_with_fallback(source, fm, api_key)
    except GeminiImageGenerationError as e:
        duration = time.monotonic() - t0
        print(f"[hero] ❌ Gemini image generation failed for {source}/{date}: {e}",
              file=sys.stderr)
        log_hero_event(source, slug, "failure_image", duration,
                       concept=None, path_taken=meta.get("path", ""),
                       error=str(e))
        return 2
    except Exception as e:
        duration = time.monotonic() - t0
        print(f"[hero] ❌ unexpected error for {source}/{date}: {e}", file=sys.stderr)
        log_hero_event(source, slug, "failure_unexpected", duration,
                       concept=None, path_taken=meta.get("path", ""),
                       error=str(e))
        return 2

    duration = time.monotonic() - t0

    if not png_bytes or len(png_bytes) < 4096:
        print(f"[hero] ❌ suspiciously small image ({len(png_bytes)} bytes) for "
              f"{source}/{date}", file=sys.stderr)
        log_hero_event(source, slug, "failure_small_image", duration,
                       concept=meta.get("concept"), path_taken=meta.get("path", ""),
                       error=f"size={len(png_bytes)}")
        return 2

    # SPEC v1.1 Section 6.2: 16:9 の結果寸法をチェック (検知のみ、クロップなし)
    warn_if_not_16x9(png_bytes, f"{source}/{date}")

    # プレビュー用に出力先ディレクトリを差し替えられる (static/images/ を上書きしない)
    out_root = os.environ.get("HERO_OUTPUT_DIR", "static/images").rstrip("/")
    out_path = f"{out_root}/{source}/{date}.png"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    print(f"[hero] saved {len(png_bytes):,} bytes → {_mask_home(os.path.abspath(out_path))}",
          file=sys.stderr)

    # プレビュー時は frontmatter を書き換えない
    if os.environ.get("HERO_SKIP_FRONTMATTER_INJECT"):
        log_hero_event(source, slug, "success_preview", duration,
                       concept=meta.get("concept"), path_taken=meta.get("path", ""))
        print(f"[hero] ✅ {source}/{date} → {_mask_home(os.path.abspath(out_path))} "
              f"(frontmatter inject skipped)", file=sys.stderr)
        return 0

    image_url = f"/images/{source}/{date}.png"
    if not inject_hero_image(md_path, image_url):
        print(f"[hero] ❌ frontmatter injection failed for {source}/{date}",
              file=sys.stderr)
        log_hero_event(source, slug, "failure_inject", duration,
                       concept=meta.get("concept"), path_taken=meta.get("path", ""),
                       error="frontmatter inject failed")
        return 2

    log_hero_event(source, slug, "success", duration,
                   concept=meta.get("concept"), path_taken=meta.get("path", ""))
    print(f"[hero] ✅ {source}/{date} → {_mask_home(os.path.abspath(out_path))} "
          f"(+ frontmatter updated)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
