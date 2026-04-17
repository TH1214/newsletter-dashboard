#!/usr/bin/env python3
"""Google Gemini API を使ってニュースレターを日本語翻訳するスクリプト。
GitHub Actions 上で実行される。GEMINI_API_KEY 環境変数で認証。
無料枠: 15 RPM / 1,500 requests/day / 1M tokens/day

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

# 試すモデルの優先順位（上から順に試す）
CANDIDATE_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-pro",
]

# v1 → v1beta の順で試す
API_VERSIONS = ["v1", "v1beta"]
GEMINI_API_HOST = "https://generativelanguage.googleapis.com"


def list_models(api_key: str) -> list:
    """利用可能なモデル一覧を取得"""
    url = f"{GEMINI_API_HOST}/v1/models?key={api_key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        models = [m["name"] for m in result.get("models", [])]
        return models
    except Exception as e:
        print(f"[gemini] ListModels failed: {e}", file=sys.stderr)
        return []


def call_gemini_once(api_key: str, model: str, version: str, prompt: str) -> str:
    """指定モデル・バージョンで Gemini API を呼び出す"""
    url = f"{GEMINI_API_HOST}/{version}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    candidates = result.get("candidates", [])
    if not candidates:
        raise ValueError(f"Empty candidates: {result}")
    text = candidates[0]["content"]["parts"][0]["text"]
    usage = result.get("usageMetadata", {})
    print(f"[gemini] OK model={model} api={version} tokens=in:{usage.get('promptTokenCount','?')}/out:{usage.get('candidatesTokenCount','?')}", file=sys.stderr)
    return text


def call_gemini(api_key: str, prompt: str) -> str:
    """利用可能なモデルを自動検出して呼び出す"""
    # まず利用可能なモデルをリスト
    available = list_models(api_key)
    if available:
        print(f"[gemini] Available models: {', '.join(m.split('/')[-1] for m in available[:5])}...", file=sys.stderr)

    # 候補モデルを順に試す
    last_err = None
    for model in CANDIDATE_MODELS:
        for version in API_VERSIONS:
            print(f"[gemini] Trying model={model} api={version}...", file=sys.stderr)
            try:
                return call_gemini_once(api_key, model, version, prompt)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                try:
                    msg = json.loads(body).get("error", {}).get("message", body)
                except Exception:
                    msg = body
                print(f"[gemini] HTTP {e.code}: {msg[:120]}", file=sys.stderr)
                last_err = f"HTTP {e.code}: {msg}"
            except Exception as e:
                print(f"[gemini] Error: {e}", file=sys.stderr)
                last_err = str(e)

    print(f"[error] All models failed. Last error: {last_err}", file=sys.stderr)
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
