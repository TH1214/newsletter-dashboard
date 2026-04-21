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
import urllib.request
import urllib.error


DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-image")
DEFAULT_ENDPOINT = os.environ.get(
    "GEMINI_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta"
)
DEFAULT_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "120"))
DEFAULT_RETRIES = int(os.environ.get("GEMINI_RETRIES", "3"))

# 429 (レート制限) 受信時の backoff (秒)
BACKOFF_DELAYS = [15, 30, 60]


# ---------- セクション別スタイル (Monocle / Kinfolk / Cereal 編集写真調) ----------
SECTION_STYLES = {
    "wsj": (
        "Wall Street financial district at pre-dawn, glass skyscrapers reflecting soft golden light, "
        "reflective surfaces, quiet power, understated editorial photography"
    ),
    "nyt-bn": (
        "urban photojournalism documentary, street level scene, overcast sky, candid newsroom energy, "
        "muted tones, grainy 35mm film aesthetic"
    ),
    "nyt-op": (
        "contemplative editorial still life, sunlit interior with soft natural window light, "
        "books and ceramic coffee cup on wooden desk, thoughtful literary mood"
    ),
    "buysiders": (
        "executive corner office boardroom, distant glass skyline, mahogany surfaces, "
        "M&A negotiation mood, low-key corporate editorial, dusk light"
    ),
    "short-squeez": (
        "trading floor late at night, glowing Bloomberg terminals, financial intensity, "
        "amber and cyan neon reflections, cinematic low angle"
    ),
    "skift": (
        "travel editorial photograph, empty luxury hotel lobby or international airport terminal "
        "in golden hour, architectural symmetry, destination wanderlust"
    ),
    "business-insider": (
        "modern business architecture, clean tech workspace, minimal lines, "
        "sharp directional daylight, contemporary editorial"
    ),
    "economist": (
        "abstract conceptual editorial photography, economic theme, geometric composition, "
        "thoughtful quiet tone, muted documentary palette"
    ),
}

DEFAULT_STYLE = "editorial magazine photography, cinematic lighting, documentary aesthetic"

# 全セクション共通のスタイル指示
COMMON_STYLE = (
    "Editorial magazine hero photograph, Monocle Kinfolk Cereal magazine aesthetic. "
    "Photorealistic, cinematic lighting, shallow depth of field, "
    "muted earthy color palette with terracotta cream walnut tones, "
    "composition leaves central negative space for text overlay, "
    "no text, no letters, no logos, no visible faces, no watermarks, no signage."
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


# ---------- Gemini API 呼出 ----------
def call_gemini_image(prompt: str, api_key: str,
                      model: str = DEFAULT_MODEL,
                      endpoint: str = DEFAULT_ENDPOINT,
                      timeout: int = DEFAULT_TIMEOUT,
                      retries: int = DEFAULT_RETRIES) -> bytes:
    """
    Gemini 2.5 Flash Image に POST し、PNG バイト列を返す。
    HTTP 429 は exponential backoff で最大 retries 回リトライ。
    その他のエラーは即 raise。
    """
    url = f"{endpoint.rstrip('/')}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}],
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
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
            raise RuntimeError(
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
            raise RuntimeError(last_error)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = f"network error: {e}"
            if attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"[gemini] {last_error}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(last_error)

    raise RuntimeError(f"all {retries + 1} attempts failed: {last_error}")


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

    prompt = build_prompt(source, fm)
    print(f"[hero] {source}/{date}: prompt={prompt[:160]}...", file=sys.stderr)

    try:
        png_bytes = call_gemini_image(prompt, api_key)
    except Exception as e:
        print(f"[hero] ❌ Gemini API failed for {source}/{date}: {e}", file=sys.stderr)
        return 2

    if not png_bytes or len(png_bytes) < 4096:
        print(f"[hero] ❌ suspiciously small image ({len(png_bytes)} bytes) for "
              f"{source}/{date}", file=sys.stderr)
        return 2

    out_path = f"static/images/{source}/{date}.png"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    print(f"[hero] saved {len(png_bytes):,} bytes → {out_path}", file=sys.stderr)

    image_url = f"/images/{source}/{date}.png"
    if not inject_hero_image(md_path, image_url):
        print(f"[hero] ❌ frontmatter injection failed for {source}/{date}",
              file=sys.stderr)
        return 2

    print(f"[hero] ✅ {source}/{date} → {out_path} (+ frontmatter updated)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
