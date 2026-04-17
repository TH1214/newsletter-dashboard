#!/usr/bin/env python3
"""GitHub Models を使ってニュースレターを日本語翻訳するスクリプト。
GitHub Actions 上で実行される。GITHUB_TOKEN で認証。

Usage:
    python scripts/translate_gemini.py <source> <date> < email_content.txt > translated.md

Env:
    GITHUB_TOKEN             必須。workflow が渡す GITHUB_TOKEN
    TRANSLATION_MODEL        既定: openai/gpt-4o-mini  (本番推奨: openai/gpt-4.1)
    GITHUB_MODELS_ENDPOINT   既定: https://models.github.ai/inference  (ベース URL)

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
DEFAULT_ENDPOINT = "https://models.github.ai/inference"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def call_github_models(base_url: str, token: str, model: str, prompt: str) -> str:
    """GitHub Models (OpenAI 互換) を呼び出して翻訳結果を返す"""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        text = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        print(
            f"[github-models] OK model={model} "
            f"tokens=in:{usage.get('prompt_tokens','?')}/out:{usage.get('completion_tokens','?')}",
            file=sys.stderr,
        )
        return text

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        print(f"[error] GitHub Models HTTP {e.code}: {msg}", file=sys.stderr)
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

    # 認証・設定
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[error] GITHUB_TOKEN is not set", file=sys.stderr)
        sys.exit(1)
    model = os.environ.get("TRANSLATION_MODEL", DEFAULT_MODEL)
    base_url = os.environ.get("GITHUB_MODELS_ENDPOINT", DEFAULT_ENDPOINT)
    print(
        f"[github-models] endpoint={base_url} model={model} "
        f"token={token[:4]}...{token[-4:]} (len={len(token)})",
        file=sys.stderr,
    )

    # メール本文を stdin から読み込む
    email_content = sys.stdin.read()
    if not email_content.strip():
        print("[error] No email content provided via stdin", file=sys.stderr)
        sys.exit(1)
    print(f"[github-models] Email content: {len(email_content)} bytes", file=sys.stderr)

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
    print(f"[github-models] Full prompt: {len(full_prompt)} bytes", file=sys.stderr)
    print("[github-models] Calling GitHub Models...", file=sys.stderr)

    result = call_github_models(base_url, token, model, full_prompt)

    # コードフェンスが付いていたら除去
    lines = result.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    result = "\n".join(lines)

    print(f"[github-models] Output: {len(result)} bytes", file=sys.stderr)
    print(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
