#!/usr/bin/env python3
"""Anthropic SDK を使ってニュースレターを日本語翻訳するスクリプト。
GitHub Actions 上で実行される。ANTHROPIC_API_KEY 環境変数で認証。

Usage:
    python scripts/translate_claude.py <source> <date> < email_content.txt > translated.md

Exit codes:
    0: 成功
    1: エラー（認証失敗、API エラー等）
"""

import sys
import os
import anthropic

TRANSLATE_PROMPT_PATH = "scripts/translate_prompt.md"


def main():
    if len(sys.argv) < 3:
        print("Usage: python translate_claude.py <source> <date>", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1]
    date = sys.argv[2]

    # API キー確認
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[error] ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(1)
    print(f"[claude] API key: {api_key[:8]}...{api_key[-4:]} (len={len(api_key)})", file=sys.stderr)

    # メール本文を stdin から読み込む
    email_content = sys.stdin.read()
    if not email_content.strip():
        print("[error] No email content provided via stdin", file=sys.stderr)
        sys.exit(1)
    print(f"[claude] Email content size: {len(email_content)} bytes", file=sys.stderr)

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
    print(f"[claude] Full prompt size: {len(full_prompt)} bytes", file=sys.stderr)

    # Anthropic API を呼び出す
    print(f"[claude] Calling Anthropic API (model: claude-sonnet-4-6)...", file=sys.stderr)
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[
                {"role": "user", "content": full_prompt}
            ]
        )
        result = message.content[0].text
        print(f"[claude] Response received: {len(result)} bytes, stop_reason={message.stop_reason}", file=sys.stderr)
        print(f"[claude] Usage: input={message.usage.input_tokens} output={message.usage.output_tokens} tokens", file=sys.stderr)

        # コードフェンスが付いていたら除去
        lines = result.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        result = "\n".join(lines)

        # stdout に出力
        print(result)
        sys.exit(0)

    except anthropic.AuthenticationError as e:
        print(f"[error] Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)
    except anthropic.RateLimitError as e:
        print(f"[error] Rate limit exceeded: {e}", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIConnectionError as e:
        print(f"[error] API connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"[error] API status error {e.status_code}: {e.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[error] Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
