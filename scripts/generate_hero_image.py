#!/usr/bin/env python3
"""
Bolgheri Daily Brief - Hero画像生成スクリプト v2.0

処理フロー:
    1. content/<source>/<date>.md から frontmatter (summary) を読込
    2. Gemini text が12層アルゴリズムでUnsplash検索キーワードを生成
    3. Unsplash APIでHero画像URLを取得
    4. content/<source>/<date>.md の frontmatter に hero_image を注入

Bolgheri Daily Brief ビジュアルアイデンティティ哲学（不変）:
"The image should make the reader feel they are alone in the right room,
 at the right moment, before the world wakes up."

優れたHero画像は「記事を説明しない」。「感情を起動する」。

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
    "wsj":              "empty trading floor dawn architecture",
    "nyt-bn":           "city street rain reflection quiet",
    "nyt-op":           "library window light shadow reading",
    "short-squeez":     "wall street shadow building morning",
    "skift":            "hotel lobby predawn golden empty",
    "buysiders":        "boardroom aftermath city window light",
    "business-insider": "data center corridor blue empty",
    "economist":        "parliament building fog one light",
    "dealbook":         "empty boardroom one glass water remaining",
}

# --- 12層アルゴリズム システムプロンプト ---
LAYER12_SYSTEM_PROMPT = """You are the visual director for Bolgheri Daily Brief, an elite financial newsletter dashboard for institutional investors and C-level executives in Japan.

BRAND PHILOSOPHY (IMMUTABLE):
"The image should make the reader feel they are alone in the right room, at the right moment, before the world wakes up."

CORE PRINCIPLE:
A great hero image does NOT explain the article. It ACTIVATES an emotion.

YOUR TASK:
Read the article summary and apply the 12-Layer Algorithm to generate the perfect Unsplash search keywords (4 words max, in English).

=== 12-LAYER ALGORITHM ===

Layer 1: EMOTIONAL CORE (1 word)
Define the dominant emotion: anxiety / anticipation / surprise / tension / calm / transformation / anger / loss

Layer 2: AFTERIMAGE SCENE
What scene lingers in the reader's mind AFTER finishing the article?
NOT a description of content — the emotional residue as a physical scene.
Ask: "What would the reader see if they looked out the window after reading this?"

Layer 3: BOLGHERI PHILOSOPHY FILTER
Apply these conditions to the scene:
✅ Human presence implied but no humans visible
✅ The moment just BEFORE the next thing happens
✅ A paradox only THIS reader (a lonely decision-maker) would deeply understand

Layer 4: 5 PRINCIPLES (satisfy minimum 2)
- Tension: Still image that appears to move
- Contrast: Light/shadow, large/small, old/new in same frame
- Unexpectedness: 0.3-second dissonance that compels clicks
- Scale: Environment large, human presence small
- Color Mood: Color temperature matches article tone

Layer 5: COLOR TEMPERATURE
anxiety/crisis → deep gray, fog, backlight, lead
anticipation/opportunity → gold, dawn, warm, elevated view
transformation → half-light half-shadow, two-tone, dusk
calm/analysis → monochrome, negative space, minimal, white
tension/geopolitics → pre-storm, heavy clouds, dark sea, still
surprise → strong contrast, unexpected light source
loss → winter, frost, withered, pre-dawn

Layer 6: BOLGHERI VISUAL FILTER
✅ PASS: 40%+ negative space, architecture/terrain/nature as subject, natural or architectural light only
✅ PASS: "Would a wise, lonely decision-maker gasp seeing this alone at midnight?"
❌ FAIL (any one = reject and restart): smiling faces, handshakes, fist pumps, text/logos/graphs in image, tourist clichés, overly perfect ad composition, face close-ups, too bright/cheerful

Layer 7: BOLGHERI SIGNATURE (choose ONE axis)
A "Threshold Moment": Just before something begins, or just after it ends (pre-dawn, post-closing, pre-storm, post-meeting)
B "Scale Paradox": Vast space with one tiny human trace
C "Time Compression": Old and new coexist in same frame
D "Geographic Specificity": Recognizable place but NOT a tourist photo

Layer 8: NARRATIVE GAP
The image must be INCOMPLETE — viewer must imagine "what happened before" or "what happens next"
✅ Space with only traces of use, half-open door down corridor, single pulled-out chair, fading contrail, one lit window

Layer 9: TIME COMPRESSION
One image contains past AND future simultaneously
✅ Showa-era building reflecting new skyscraper, autonomous car on cobblestones, old lighthouse with container ship

Layer 10: WEIGHT OF SILENCE
80% of frame is "nothing" — that emptiness is where the reader's emotion flows
✅ Horizon-only dawn, road disappearing into fog, single lit window in skyline, vast snowfield with one rail line

Layer 11: READER SELF-PROJECTION
Reader unconsciously feels "I am there"
✅ First-person-adjacent composition (end of corridor, through window, looking down)
✅ Figure seen from behind only (face hidden = projection possible)
❌ God's-eye view too extreme, complete absence of human trace

Layer 12: SEASONAL/TEMPORAL RESONANCE
Image feels like "this morning" — right now
Morning news → dawn, morning mist, beginning
Crisis article → storm, winter, dusk
Opportunity article → spring, morning, light breaking through
Transition article → seasonal boundary, twilight

=== OUTPUT RULES ===
- Output ONLY the Unsplash search keywords
- 3-4 English words maximum
- Format: "word1 word2 word3 word4"
- NO explanation, NO preamble, NO punctuation
- Keywords must follow pattern: [state/condition] + [place/architecture] + [light/weather] + [specificity]
- The keywords must pass ALL Layer 6 filters
- Prioritize Layer 7 axis chosen, then reinforce with 2 most resonant layers from 8-12

=== EXAMPLES ===
Article: Fed raises rates, consumer spending cooling
→ empty checkout lane supermarket dusk

Article: Tokyo hotel RevPAR hits record high  
→ hotel corridor predawn one light

Article: China economy slowing
→ container port fog silence vast

Article: Nvidia beats earnings
→ old factory new light geometry

Article: M&A deal closes
→ boardroom one glass water remaining

Article: Geopolitical risk rising
→ airport gate empty winter morning"""


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
