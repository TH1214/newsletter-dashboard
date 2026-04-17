#!/usr/bin/env python3
"""Groq API を使ってニュースレターを日本語翻訳するスクリプト。
GitHub Actions 上で実行される。GROQ_API_KEY 環境変数で認証。
Groq 無料枠: 14,400 req/day, 500K tokens/min (llama-3.3-70b-versatile)

Usage:
    python scripts/translate_gemini.py <source> <date> < email_content.txt > translated.md

Exit codes:
    0: 成功
    1: エラー
"""

import sys
import os
import json
import urllib.request
import urllib.error

TRANSLATE_PROMPT_PATH = "scripts/translate_prompt.md"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def call_groq(api_key: str, prompt: str) -> str:
    """Groq API (OpenAI互換) を呼び出して翻訳結果を返す"""
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GROQ_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        text = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        print(f"[groq] OK model={GROQ_MODEL} tokens=in:{usage.get('prompt_tokens','?')}/out:{usage.get('completion_tokens','?')}", file=sys.stderr)
        return text

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        print(f"[error] Groq API HTTP {e.code}: {msg}", file=sys.stderr)
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
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[error] GROQ_API_KEY is not set", file=sys.stderr)
        sys.exit(1)
    print(f"[groq] API key: {api_key[:8]}...{api_key[-4:]} (len={len(api_key)})", file=sys.stderr)

    # メール本文を stdin から読み込む
    email_content = sys.stdin.read()
    if not email_content.strip():
        print("[error] No email content provided via stdin", file=sys.stderr)
        sys.exit(1)
    print(f"[groq] Email content: {len(email_content)} bytes", file=sys.stderr)

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
    print(f"[groq] Full prompt: {len(full_prompt)} bytes", file=sys.stderr)
    print(f"[groq] Calling Groq API (model: {GROQ_MODEL})...", file=sys.stderr)

    result = call_groq(api_key, full_prompt)

    # コードフェンスが付いていたら除去
    lines = result.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    result = "\n".join(lines)

    print(f"[groq] Output: {len(result)} bytes", file=sys.stderr)
    print(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
