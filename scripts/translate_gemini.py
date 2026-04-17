#!/usr/bin/env python3
"""Google Gemini API を使ってニュースレターを日本語翻訳するスクリプト。
GitHub Actions 上で実行される。GEMINI_API_KEY 環境変数で認証。
Gemini 2.0 Flash は無料枠: 15 RPM / 1,500 requests/day / 1M tokens/day

Usage:
    python scripts/translate_gemini.py <source> <date> < email_content.txt > translated.md

Exit codes:
    0: 成功
    1: エラー（認証失敗、API エラー等）
"""

import sys
import os
import json
import urllib.request
import urllib.error

TRANSLATE_PROMPT_PATH = "scripts/translate_prompt.md"
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1/models"


def call_gemini(api_key: str, prompt: str) -> str:
    """Gemini API を呼び出して翻訳結果を返す"""
    url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # レスポンスからテキストを抽出
        candidates = result.get("candidates", [])
        if not candidates:
            print(f"[error] Empty candidates in response: {result}", file=sys.stderr)
            sys.exit(1)

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            print(f"[error] Empty parts in response", file=sys.stderr)
            sys.exit(1)

        text = parts[0].get("text", "")

        # usage ログ
        usage = result.get("usageMetadata", {})
        print(f"[gemini] Tokens: input={usage.get('promptTokenCount', '?')} output={usage.get('candidatesTokenCount', '?')}", file=sys.stderr)

        return text

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(error_body)
            err_msg = err_json.get("error", {}).get("message", error_body)
        except Exception:
            err_msg = error_body
        print(f"[error] Gemini API HTTP {e.code}: {err_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[error] Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print("Usage: python translate_gemini.py <source> <date>", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1]
    date = sys.argv[2]

    # API キー確認
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[error] GEMINI_API_KEY is not set", file=sys.stderr)
        sys.exit(1)
    print(f"[gemini] API key: {api_key[:8]}...{api_key[-4:]} (len={len(api_key)})", file=sys.stderr)

    # メール本文を stdin から読み込む
    email_content = sys.stdin.read()
    if not email_content.strip():
        print("[error] No email content provided via stdin", file=sys.stderr)
        sys.exit(1)
    print(f"[gemini] Email content: {len(email_content)} bytes", file=sys.stderr)

    # 翻訳プロンプトを読み込む
    try:
        with open(TRANSLATE_PROMPT_PATH, "r", encoding="utf-8") as f:
            translate_prompt = f.read()
    except FileNotFoundError:
        print(f"[error] Prompt file not found: {TRANSLATE_PROMPT_PATH}", file=sys.stderr)
        sys.exit(1)

    # フルプロンプトを構築
    full_prompt = (
        f"{translate_prompt}\n\n"
        f"---\n"
        f"SOURCE_SLUG: {source}\n"
        f"DATE: {date}\n"
        f"---\n\n"
        f"{email_content}"
    )
    print(f"[gemini] Full prompt: {len(full_prompt)} bytes", file=sys.stderr)
    print(f"[gemini] Calling Gemini API (model: {GEMINI_MODEL})...", file=sys.stderr)

    result = call_gemini(api_key, full_prompt)

    # コードフェンスが付いていたら除去
    lines = result.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    result = "\n".join(lines)

    print(f"[gemini] Output: {len(result)} bytes", file=sys.stderr)
    print(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
