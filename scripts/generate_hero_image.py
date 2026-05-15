#!/usr/bin/env python3
"""
Bolgheri Daily Brief - Hero画像生成スクリプト v2.0

処理フロー:
    1. content/<source>/<date>.md から frontmatter (summary) を読込
    2. Gemini text が12層アルゴリズムでUnsplash検索キーワードを生成
    3. Unsplash APIでHero画像URLを取得
    4. content/<source>/<date>.md の frontmatter に hero_image を注入

Bolgheri Daily Brief ビジュアルアイデンティティ哲学（不変）:
"Bolgheri is a sun-drenched Tuscan village. The image should carry warmth,
 clarity, and the feeling of standing at the edge of something significant
 — bright enough to inspire action, precise enough to convey intelligence."

優れたHero画像は「記事を説明しない」。「知性と温かみで感情を起動する」。

Usage:
    python scripts/generate_hero_image.py <source> <date>

Env:
    GEMINI_API_KEY        Google AI Studio API Key（既存のまま流用）
    UNSPLASH_ACCESS_KEY   Unsplash Developer Access Key

コスト: Gemini text（無料枠）+ Unsplash（無料）= ¥0/月
"""

import sys
import os
import re
import json
import time
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# --- API設定 ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = os.environ.get("GEMINI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "h2nrT6P2-7X1uFTM0ThFCWqub6B8Cc0M-ItRpoTV1aA")
UNSPLASH_ENDPOINT = "https://api.unsplash.com/photos/random"

# --- ソース別フォールバックキーワード（Gemini失敗時） ---
FALLBACK_KEYWORDS = {
    "wsj":              "sunlit financial district morning",
    "nyt-bn":           "bright city skyline daylight",
    "nyt-op":           "warm library window sunlight",
    "short-squeez":     "glass tower golden light",
    "skift":            "warm hotel terrace sun",
    "buysiders":        "grand marble hall daylight",
    "business-insider": "bright modern office light",
    "economist":        "open city panorama blue sky",
    "dealbook":         "sunlit boardroom architecture",
    "cnbc":             "financial district morning sun",
    "cnbc-squawk":      "bright trading floor morning light",
}

# --- 12層アルゴリズム システムプロンプト ---
LAYER12_SYSTEM_PROMPT = """You are the visual director for Bolgheri Daily Brief, an elite financial newsletter dashboard for institutional investors and C-level executives in Japan.

BRAND IDENTITY (IMMUTABLE):
Bolgheri is named after a sun-drenched Tuscan wine village — warm, golden, Mediterranean. The brand color is a vivid warm orange-red (#FF3B00) against cream-white paper. Hero images must carry the same warmth, clarity, and luminosity as the brand itself.

BRAND PHILOSOPHY:
"The image should carry the warmth and precision of a Tuscan morning — bright enough to inspire action, clear enough to convey intelligence, beautiful enough to make the reader pause."

CORE PRINCIPLE:
A great hero image does NOT explain the article. It ACTIVATES an emotion — and for Bolgheri, that emotion is intelligence-meets-warmth, never gloom.

YOUR TASK:
Read the article summary and apply the 12-Layer Algorithm to generate the perfect Unsplash search keywords (4 words max, in English).

=== 12-LAYER ALGORITHM ===

Layer 1: EMOTIONAL CORE (1 word)
Define the dominant emotion: clarity / anticipation / momentum / tension / insight / transformation / precision / discovery

Layer 2: AFTERIMAGE SCENE
What scene lingers in the reader's mind AFTER finishing the article?
NOT a description of content — the emotional residue as a physical scene.
Ask: "What would the reader see if they looked out the window after reading this, in the warm morning light?"

Layer 3: BOLGHERI PHILOSOPHY FILTER
Apply these conditions to the scene:
✅ Human presence implied but no humans visible
✅ The moment just AS something begins — threshold of action, not aftermath of darkness
✅ A scene a decisive, globally-minded executive would find beautiful and energizing

Layer 4: 5 PRINCIPLES (satisfy minimum 2)
- Luminosity: Image has a dominant warm or bright light source
- Contrast: Light/shadow with warm highlights, not cold grey uniformity
- Unexpectedness: 0.3-second visual surprise that compels clicks
- Scale: Expansive environment with human-scale precision element
- Color Warmth: Warm tones (gold, amber, terracotta, cream, bright white) predominate

Layer 5: COLOR TEMPERATURE — DEFAULT IS WARM
DEFAULT (all articles) → golden hour, warm light, bright interior, sunlit architecture, Mediterranean
anticipation/opportunity → golden dawn, warm sunlight, open horizon, bright sky
analysis/insight → clean bright architecture, white marble, sharp geometry, daylight
transformation → warm dusk with bright horizon, autumn gold, turning point light
tension/geopolitics → dramatic bright contrast, storm with golden break, strong sidelight
crisis/loss → cool but luminous, silver light, overcast but bright (NOT dark, NOT gloomy)
M&A/deals → grand architecture, warm boardroom light, polished surfaces
travel/hospitality → warm lobby light, sun-drenched terrace, golden hour destination

Layer 6: BOLGHERI VISUAL FILTER
✅ PASS: Warm or bright natural light, golden hour, sunlit interiors, Mediterranean warmth
✅ PASS: Clean architecture in bright daylight, expansive luminous landscapes
✅ PASS: "Would a sophisticated, globally-minded executive feel energized seeing this?"
✅ PASS: 40%+ negative space filled with warm light or bright sky
❌ FAIL (any one = reject and restart): smiling faces, handshakes, fist pumps, text/logos/graphs in image
❌ FAIL: face close-ups, stock photo clichés, tourist trap clichés
❌ FAIL: predominantly dark, gloomy, foggy, overcast, or cold grey imagery
❌ FAIL: images where the dominant mood is sadness, heaviness, or bleakness

Layer 7: BOLGHERI SIGNATURE (choose ONE axis)
A "Golden Threshold": The moment light breaks through — dawn cresting a skyline, sun entering a room, light at the end of a corridor
B "Luminous Scale": Vast bright space (open sea at noon, sunlit plain, bright city) with one precise human element
C "Warm Precision": Architectural geometry in warm direct light — sharp shadows, golden surfaces
D "Mediterranean Clarity": Stone, terrace, coast, vineyard, or courtyard in clear warm light

Layer 8: NARRATIVE OPENNESS
The image suggests possibility, not conclusion.
✅ Open door onto a sunlit courtyard, window with bright view, road toward bright horizon
✅ Empty seat at a sunlit table, morning light on a clean workspace, bright sky over a city

Layer 9: MATERIAL WARMTH
The image has tactile warmth — materials that absorb and reflect warm light
✅ Warm stone, polished wood, terracotta, glass catching sunlight, marble in daylight
✅ Contrast of bright architectural material against blue sky

Layer 10: BREATHING ROOM
60–80% of frame is open, luminous space — sky, bright wall, sunlit floor, open water in daylight
✅ Bright horizon, sunlit plaza, wide window with sky, open staircase in warm light

Layer 11: READER ASPIRATION
Reader unconsciously feels "I want to be there / I can achieve this"
✅ Elevated viewpoint with bright cityscape, open terrace over sunlit landscape
✅ Wide, bright interior suggesting clarity and decisive space
❌ Cramped, dark, or claustrophobic frames

Layer 12: SEASONAL/TEMPORAL RESONANCE
Default: Morning or midday brightness. Only use evening/dusk when the article strongly suggests transition.
Growth/markets/opportunity → morning sunlight, bright open sky, golden dawn
Finance/analysis → bright clear architecture, sharp daylight geometry
Travel/hospitality → warm midday destination, golden hour terrace
Crisis/tension → bright silver overcast (light present but dramatic), NOT dark
M&A/deals → grand sunlit institution, marble in daylight, city panorama bright sky

=== OUTPUT RULES ===
- Output ONLY the Unsplash search keywords
- 3-4 English words maximum
- Format: "word1 word2 word3 word4"
- NO explanation, NO preamble, NO punctuation
- Keywords must bias toward: warm, golden, bright, sunlit, daylight, morning, Mediterranean
- The keywords must pass ALL Layer 6 filters — especially the NO DARK/GLOOMY rule

=== EXAMPLES ===
Article: Fed raises rates, consumer spending cooling
→ sunlit empty store morning

Article: Tokyo hotel RevPAR hits record high
→ warm hotel lobby golden light

Article: China economy slowing
→ bright port cranes blue sky

Article: Nvidia beats earnings
→ glass building sunlight geometry

Article: M&A deal closes
→ grand marble hall daylight

Article: Geopolitical risk rising
→ bright city panorama dramatic sky

Article: Startup IPO pricing above range
→ glass tower morning light

Article: Travel industry recovery
→ sun terrace mediterranean warm"""


def read_frontmatter(md_path: str) -> dict:
    """MDファイルからfrontmatterを読み込む"""
    if not os.path.exists(md_path):
        return {}
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm


def inject_hero_image(md_path: str, image_url: str) -> None:
    """frontmatterにhero_imageを注入または上書き"""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    if re.search(r"^hero_image:", content, re.MULTILINE):
        content = re.sub(
            r"^hero_image:.*$",
            f'hero_image: "{image_url}"',
            content,
            flags=re.MULTILINE,
        )
    else:
        content = re.sub(r"^(---\n)", r"\1" + f'hero_image: "{image_url}"\n', content)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    log.info(f"hero_image injected: {image_url[:80]}...")


def generate_keywords_with_gemini(source: str, summary: str) -> Optional[str]:
    """Gemini textが12層アルゴリズムでキーワードを生成"""
    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set, using fallback keywords")
        return None

    url = f"{GEMINI_ENDPOINT}/models/{GEMINI_TEXT_MODEL}:generateContent?key={GEMINI_API_KEY}"

    user_message = f"""Source: {source}

Article summary:
\"\"\"
{summary}
\"\"\"

Apply the 12-Layer Algorithm and output ONLY the Unsplash search keywords (3-4 words, English only)."""

    payload = json.dumps({
        "system_instruction": {
            "parts": [{"text": LAYER12_SYSTEM_PROMPT}]
        },
        "contents": [{
            "parts": [{"text": user_message}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 30,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }).encode("utf-8")

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{"text": ""}])[0]
                    .get("text", "")
                    .strip()
                    .strip('"')
                    .lower()
                )
                # 不要な文字を除去
                text = re.sub(r"[^\w\s]", "", text).strip()
                # 4語以内に制限
                words = text.split()[:4]
                keywords = " ".join(words)
                if keywords:
                    log.info(f"Gemini 12-Layer keywords: {keywords!r}")
                    return keywords
        except urllib.error.HTTPError as e:
            log.warning(f"Gemini HTTP {e.code} (attempt {attempt+1}/3)")
            if e.code == 429:
                time.sleep(15 * (attempt + 1))
            else:
                break
        except Exception as e:
            log.warning(f"Gemini error: {e} (attempt {attempt+1}/3)")
            time.sleep(5)

    return None


def get_unsplash_image(keywords: str, retries: int = 3) -> Optional[str]:
    """Unsplash APIから画像URLを取得"""
    query = urllib.parse.quote(keywords, safe="")
    url = (
        f"{UNSPLASH_ENDPOINT}"
        f"?query={query}"
        f"&orientation=landscape"
        f"&client_id={UNSPLASH_ACCESS_KEY}"
    )
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                image_url = data["urls"]["regular"]
                log.info(f"Unsplash OK: {keywords!r} → {image_url[:60]}...")
                return image_url
        except urllib.error.HTTPError as e:
            log.warning(f"Unsplash HTTP {e.code} (attempt {attempt+1}/{retries})")
            if e.code == 403:
                log.error("Unsplash API key invalid or rate limit exceeded")
                return None
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            log.warning(f"Unsplash error: {e} (attempt {attempt+1}/{retries})")
            time.sleep(5 * (attempt + 1))
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: generate_hero_image.py <source> <date>", file=sys.stderr)
        return 1

    source = sys.argv[1].lower()
    date = sys.argv[2]

    # MDファイルパス
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    md_path = os.path.join(repo_root, "content", source, f"{date}.md")

    if not os.path.exists(md_path):
        log.error(f"MD not found: {md_path}")
        return 2

    # frontmatter読み込み
    fm = read_frontmatter(md_path)
    summary = fm.get("summary", fm.get("title", ""))
    log.info(f"Processing: source={source} date={date}")
    log.info(f"Summary: {summary[:80]}...")

    # Step 1: Gemini 12層アルゴリズムでキーワード生成
    keywords = None
    if summary:
        keywords = generate_keywords_with_gemini(source, summary)

    # Step 2: フォールバック（Gemini失敗時）
    if not keywords:
        keywords = FALLBACK_KEYWORDS.get(source, "empty room morning light architecture")
        log.info(f"Using fallback keywords: {keywords!r}")

    # Step 3: Unsplash画像取得
    image_url = get_unsplash_image(keywords)

    # Step 4: Unsplashも失敗した場合、別キーワードで再試行
    if not image_url:
        fallback = FALLBACK_KEYWORDS.get(source, "architecture morning light empty")
        log.warning(f"Retrying with fallback: {fallback!r}")
        image_url = get_unsplash_image(fallback)

    if not image_url:
        log.error("Failed to get any image from Unsplash")
        return 2

    # Step 5: frontmatterに注入
    inject_hero_image(md_path, image_url)
    log.info(f"Done: {source}/{date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
