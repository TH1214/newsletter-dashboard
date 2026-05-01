# SPEC v1.1: `scripts/generate_hero_image.py` ヒーロー画像生成ロジック刷新

**作成日:** 2026-04-22
**対象:** Claude Code 実装用決定版仕様書
**前提条件:** 完全無料運用 (Gemini 2.5 Flash 無料枠のみ使用)
**改版:** v1.0 → v1.1 (12点の review 指摘を反映 + Claude API → Gemini Flash text 差し替え)

---

## 0. TL;DR

- 現行 `scripts/generate_hero_image.py` は summary 直接 → Gemini 2.5 Flash Image の 1 段階プロンプト。
- 本 spec は **2 段階プロンプト (Gemini text → Gemini image)** に刷新する。
- 中間段階で **視覚概念を JSON 抽出** し、**媒体別スタイル辞書** で最終プロンプトを組み立てる。
- **コスト: $0/年**（Gemini 2.5 Flash text / image の両方とも無料枠内で完結）。

---

## 1. 背景

現行実装の問題点:

1. **関連性の欠如** — summary の表面的キーワードから画像生成するため、記事の核心と画像がズレる。
2. **スタイルの不統一** — 媒体ごとのブランド性 (WSJ のエディトリアル風 / Skift のライフスタイル調) が反映されない。
3. **主題の抽象化** — "growth", "market" のような抽象語が主語になり、描画不能な画像が生成される。

解決策: **思考プロセスの明示化 (2 段階プロンプト)** と **媒体別スタイル辞書**。

---

## 2. API Key / 環境変数

### 2.1 使用する API Key (全て無料枠)

| 変数名 | 用途 | 取得元 | 無料枠 | 日次使用見込み |
|---|---|---|---|---|
| `GEMINI_API_KEY` | Text (JSON抽出) + Image (画像生成) 両方 | Google AI Studio | 1,500 RPD / 15 RPM | 最大 16 calls/日 (8 sec × 2) |

### 2.2 新規 Secret 追加

**不要。** 既存の `GEMINI_API_KEY` (`.env` および GitHub Actions Secrets) をそのまま流用する。

### 2.3 無料枠の利用状況モニタリング

ログ出力に daily call count を記録し、1,000 RPD 超過で警告を出す (`logs/hero_generation.log`)。

---

## 3. 実装要件

### 3.1 プロンプト生成を 2 段階に分離

```
[現行]
summary → (Gemini 2.5 Flash Image) → hero.png

[新設]
summary → (Gemini 2.5 Flash text, JSON mode) → visual_concept (JSON)
         → build_hero_prompt() → (Gemini 2.5 Flash Image) → hero.png
```

### 3.2 中間 JSON スキーマ

```json
{
  "core_theme": "記事の核心トピック (1キーワード、英語)",
  "visual_metaphor": "そのトピックを象徴する具体的な物体/動作 (英語、1フレーズ)",
  "contextual_detail": "ニュース固有の要素 (場所/産業/人物属性のいずれか1つ、英語)",
  "primary_subject_noun": "画像の主役となる具体名詞 (英語、最優先で描かせる対象)"
}
```

### 3.3 Gemini 2.5 Flash (text) への System Prompt

**必ずこの文言を使用。変更禁止。**

```
You are a visual concept director for a financial/business newsletter dashboard.
Given an article summary, extract the following in 3 strict steps:

STEP 1 - Core Theme: Identify ONE central topic keyword.
STEP 2 - Visual Metaphor: Choose ONE concrete object or action that symbolizes the theme.
  - For abstract concepts (inflation, recession, negotiation), use physical metaphors
    (a heavy weight, a stalled engine, a chessboard).
  - For lifestyle/travel/tech, use scene-based imagery (a cyclist on a ridge,
    a traveler with luggage, a modern workspace).
STEP 3 - Contextual Detail: Add ONE specific element from the article
  (location, industry, character attribute).

Also extract the PRIMARY SUBJECT NOUN — the single most important object
that MUST appear as the visual anchor.

Rules:
- Never return abstract concepts as primary_subject_noun. Always a physical,
  drawable object (e.g., "a cyclist", "a skyscraper", "a golden coin", NOT "growth" or "risk").
- All fields in English.
- Output ONLY valid JSON, no preamble, no markdown fences.
```

### 3.4 Gemini API 呼び出しパラメータ (text)

```python
GEMINI_TEXT_MODEL = "gemini-2.5-flash"

generation_config = {
    "temperature": 0,              # 決定論的抽出
    "max_output_tokens": 300,      # JSON は 200 tok 程度で収まる
    "response_mime_type": "application/json",  # JSON モード強制
}
```

### 3.5 Summary の境界明示 (prompt injection 防御)

User message 側で summary を `"""` で囲む:

```python
user_message = f'''Extract the visual concept from the following article summary:

"""
{summary}
"""

Output JSON only.'''
```

---

## 4. 媒体別スタイル辞書

`scripts/generate_hero_image.py` の先頭に以下を追加:

```python
STYLE_DICTIONARY = {
    # --- Editorial (エディトリアル風刺画) ---
    "wsj": {
        "category": "editorial",
        "style_keywords": "traditional editorial illustration, sophisticated conceptual metaphor, "
                          "muted earth tones, subtle crosshatching texture, "
                          "reminiscent of The Wall Street Journal opinion pages",
        "tone": "serious, weighty, intellectually refined",
    },
    "nyt-bn": {
        "category": "editorial",
        "style_keywords": "modern editorial illustration, bold conceptual metaphor, "
                          "limited color palette with one accent color, clean composition, "
                          "reminiscent of New York Times front-page art",
        "tone": "urgent, contemporary, journalistic",
    },
    "nyt-op": {
        "category": "editorial",
        "style_keywords": "bold contemporary satirical illustration, daring conceptual metaphor, "
                          "high-contrast color blocks, reminiscent of New York Times Op-Ed section",
        "tone": "provocative, opinionated, modern",
    },
    "buysiders": {
        "category": "editorial",
        "style_keywords": "financial editorial illustration, M&A metaphor imagery "
                          "(handshakes, merging shapes, chessboards), "
                          "navy and gold palette, sophisticated minimalism",
        "tone": "corporate, strategic, high-stakes",
    },
    # Economist は配信実績確認後に有効化 (2026-04-22 時点で日次配信未実装)
    # "economist": { ... },

    # --- Lifestyle (モダンフラットアート) ---
    "skift": {
        "category": "lifestyle",
        "style_keywords": "modern flat digital illustration, textured brush strokes, "
                          "soft gradients, travel and hospitality scenes, "
                          "serene atmosphere, clean and aspirational",
        "tone": "optimistic, aspirational, polished",
    },
    "business-insider": {
        "category": "lifestyle",
        "style_keywords": "modern flat digital illustration, textured brush strokes, "
                          "subtle gradients, contemporary urban or business scenes, "
                          "clean composition with tactile detail",
        "tone": "accessible, contemporary, visually rich",
    },

    # --- Editorial-playful (第3カテゴリ) ---
    "short-squeez": {
        "category": "editorial-playful",
        "style_keywords": "playful financial editorial illustration, Wall Street metaphor imagery, "
                          "slightly irreverent tone, clean vector-style with texture accents, "
                          "tinted or textured backgrounds (cream, pale navy, warm gray)",
        "tone": "witty, finance-savvy, slightly irreverent",
    },
}
```

**運用上の注意:**
- `economist` は 2026-04-22 時点で日次配信実績ゼロ。実装後、配信が始まった段階で追加する。
- 新セクション追加時は、このファイル 1 箇所を編集するだけで対応可能な設計にすること。

---

## 5. 最終プロンプト組み立てロジック

```python
def build_hero_prompt(subject_noun: str, metaphor: str, context: str,
                      style_keywords: str, category: str) -> str:
    """
    Gemini 2.5 Flash Image 向けの最終プロンプトを組み立てる。

    CRITICAL: 名詞の順序厳守 (先頭が最も強く描画に反映される)
    1. PRIMARY SUBJECT (主役の物体) - 最優先
    2. METAPHORICAL CONTEXT (比喩の文脈)
    3. CONTEXTUAL DETAIL (固有の詳細)
    4. STYLE (媒体固有のスタイル)
    5. CONSTRAINTS (共通制約)
    """
    if category == "editorial":
        composition = "a conceptual metaphor illustration featuring"
        background_directive = ""  # editorial は白背景OK (意図的スタイル)
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
```

---

## 6. Aspect Ratio (16:9) の強制

### 6.1 プロンプト内テキストだけでは不十分

Gemini 2.5 Flash Image は自然言語の `16:9 aspect ratio` 指示を弱く扱い、デフォルトで 1024×1024 (正方形) を返す傾向がある (現状の実配信が 1024×1024 である実証済み)。

### 6.2 API パラメータでの明示指定

```python
from google.generativeai.types import GenerationConfig

image_config = GenerationConfig(
    response_modalities=["IMAGE"],
    # Gemini 2.5 Flash Image の aspect ratio 指定方式
    # (SDK バージョンにより API 名が異なる場合あり、実装時に google-generativeai の
    #  最新ドキュメントで確認)
    image_config={
        "aspect_ratio": "16:9",
    },
)
```

**実装時の確認事項:**
- `google-generativeai` SDK のバージョンを確認 (`pip show google-generativeai`)
- バージョンによって `aspectRatio` / `aspect_ratio` / `IMAGE_CONFIG` の命名が異なるため、実装時に公式ドキュメントで最新仕様を確認すること。
- API 側で指定不可なバージョンの場合は、生成後に Pillow で 1920×1080 にクロップする fallback を実装。

---

## 7. 失敗検知とフォールバック

### 7.1 抽象名詞ブラックリスト (強化版)

```python
ABSTRACT_NOUN_BLACKLIST = {
    # v1.0 からの引き継ぎ
    "growth", "risk", "trend", "market", "economy", "strategy",
    "future", "change", "impact",
    # v1.1 追加 (金融・ビジネスニュースで頻出)
    "innovation", "disruption", "transformation", "opportunity", "challenge",
    "landscape", "dynamics", "ecosystem", "momentum", "outlook",
    # 追加の抽象語
    "potential", "value", "performance", "competition", "advantage",
}
```

### 7.2 リトライ判定

以下のいずれかに該当したら **1 回だけ** 再試行:

1. `primary_subject_noun` に `ABSTRACT_NOUN_BLACKLIST` の語が含まれる (小文字比較)
2. `primary_subject_noun` が 2 語以下 (冠詞を除く)
3. JSON パース失敗

### 7.3 リトライ時の追加指示

```
Your previous output was too abstract. The primary_subject_noun must be
a physically drawable object that a child could recognize.
Examples of GOOD nouns: "a cyclist", "a skyscraper", "a golden coin",
"a chess piece", "a suitcase". Retry with a more concrete noun.
```

### 7.4 最終フォールバック (Anthropic 不使用なので関係なし → Gemini text 失敗時の挙動)

Gemini text (JSON抽出) が 2 回失敗した場合:

1. エラーログを記録
2. **現行ロジック (summary 直接 → Gemini image) にデグレード**
3. daily publish job は **失敗させない** (Hero image なしでも記事本文は配信する)

```python
def generate_hero_with_fallback(summary: str, media: str) -> Optional[bytes]:
    try:
        concept = extract_visual_concept(summary)  # Gemini text
        prompt = build_hero_prompt(**concept, **STYLE_DICTIONARY[media])
        return generate_image(prompt)  # Gemini image
    except GeminiTextExtractionError:
        log.warning("Gemini text failed, falling back to direct summary prompt")
        return generate_image_direct(summary, media)  # 現行ロジック
    except GeminiImageGenerationError:
        log.error("Gemini image generation failed")
        return None  # Hero image なしで記事は配信継続
```

---

## 8. ログ出力

### 8.1 出力先

`~/newsletter-dashboard/logs/hero_generation.log`

### 8.2 ログレベル分離

| レベル | 内容 |
|---|---|
| INFO | 成功/失敗、media、slug、所要時間、daily call count |
| DEBUG (opt-in) | 全プロンプト、JSON抽出結果、Gemini raw response |

### 8.3 INFO レベル出力例

```
[2026-04-22 10:30:15] INFO article_slug=wsj-2026-04-22 media=wsj
  core_theme=inflation
  subject_noun="a heavy weight"
  result=success duration=4.2s
  daily_calls=12/1500
```

### 8.4 PII / Key 漏洩防止

- `GEMINI_API_KEY` は絶対にログに出さない (マスク必須)
- ファイルパスはホームディレクトリを `~` に置換
- summary の本文は DEBUG レベルのみ、INFO には出さない

---

## 9. 受け入れ基準

### 9.1 ユニットテスト (test_hero_generation.py)

**合格条件 (決定論的で検証可能):**

| テストケース | 入力 | 合格条件 |
|---|---|---|
| TC-01 | summary = "日銀が利上げを示唆、円高が進行" (media=wsj) | `primary_subject_noun` が `ABSTRACT_NOUN_BLACKLIST` に含まれない |
| TC-02 | summary = "JAL City那覇、GW期間のADRが前年比+15%" (media=skift) | 同上 + 最終プロンプト中に `aspirational` が含まれる |
| TC-03 | summary = "Marubeniが仙台SS30の取得を検討" (media=buysiders) | 同上 + 最終プロンプトに `navy and gold` が含まれる |
| TC-04 | summary = "AI規制の必要性" (media=nyt-op) | 同上 + 最終プロンプトに `bold` と `high-contrast` が含まれる |
| TC-05 | Gemini text が `"primary_subject_noun": "growth"` を返す (mock) | 1 回リトライが実行される |
| TC-06 | Gemini text が 2 回失敗 (mock) | フォールバック (現行ロジック) が呼ばれる |

### 9.2 参考的な期待値 (LLM 非決定性のため必須合格条件ではない)

| 入力 | 期待される主役名詞 (参考) |
|---|---|
| "日銀が利上げを示唆..." | "a steep staircase" または "a rising arrow made of yen coins" |
| "JAL City那覇..." | "a luxury hotel lobby" または "a traveler with luggage" |
| "Marubeniが仙台SS30..." | "a chess piece being moved" または "two skyscrapers merging" |
| "AI規制..." | "a scale balancing a chip and a gavel" |

---

## 10. 実装順序

1. **依存確認** — `google-generativeai` SDK バージョン確認、`aspect_ratio` API の最新仕様確認
2. **Economist 配信実績確認** — `ls content/economist/` で日次配信の有無を確認、有無により `STYLE_DICTIONARY` 要素を調整
3. `STYLE_DICTIONARY` 定数を追加 (Section 4)
4. `extract_visual_concept(summary: str) -> dict` を実装 (Gemini 2.5 Flash text, JSON mode)
5. `ABSTRACT_NOUN_BLACKLIST` とリトライロジックを実装
6. `build_hero_prompt()` を実装 (Section 5)
7. `generate_hero_with_fallback()` を実装 (Section 7.4)
8. Aspect ratio 16:9 強制ロジックを実装 (Section 6、必要なら Pillow fallback)
9. ログ出力を追加 (Section 8)
10. `test_hero_generation.py` に TC-01 〜 TC-06 をユニットテスト化 (Section 9.1)
11. 手動で本日分 (4 media) を再生成し、視覚確認
12. git commit & push (commit message: `hero: 2-stage prompt with media-style dict (v1.1 SPEC)`)

---

## 11. コスト試算

| 項目 | 単価 | 日次 | 年次 |
|---|---|---|---|
| Gemini 2.5 Flash (text) | 無料枠 1,500 RPD | 7-14 calls | $0 |
| Gemini 2.5 Flash Image | 無料枠 | 7-14 calls | $0 |
| **合計** | — | **$0** | **$0** |

無料枠上限まで余裕: text/image とも 100 倍以上。

---

## 12. リスク & 未解決論点

| # | リスク | 緩和策 |
|---|---|---|
| R1 | Gemini 無料枠の将来的変更 (Google ポリシー変更) | 月次で pricing page を確認。有料化される場合は Haiku 4.5 ($1.80/年) への差し替えを即時検討 |
| R2 | Gemini text の JSON 抽出精度が Claude より低い可能性 | ユニットテスト (TC-01〜04) で合格率を測定、80% 以下なら Haiku 4.5 への切替を検討 |
| R3 | Aspect ratio 16:9 API 指定が SDK バージョンで動かない | Pillow fallback (Section 6.2) を必ず実装 |
| R4 | 日本語 summary を英語として Gemini が解釈する精度 | System prompt で "translate Japanese summary to English if needed" を明示検討 |

---

## 13. Open Questions (Claude Code 実装開始前に確認)

1. [ ] `scripts/generate_hero_image.py` の現行バージョンが v1.0 SPEC 前提で動作しているか?
2. [ ] `google-generativeai` SDK のバージョン (`pip show`)
3. [ ] `GEMINI_API_KEY` の無料枠 RPD 現在使用量
4. [ ] `logs/` ディレクトリが既存か否か (新規なら `.gitignore` 追記)
5. [ ] Economist セクションの日次配信実装予定

---

**END OF SPEC v1.1**
