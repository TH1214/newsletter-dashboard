#!/usr/bin/env python3
"""GitHub Models を使ってニュースレターを日本語翻訳するスクリプト。

GitHub Actions 上で実行される。GITHUB_TOKEN で認証。
長文メール (8000 token の入力上限超過) は段落単位でチャンクに分割し、
順次翻訳してから 1 本の Markdown に結合する。本文を短縮・要約して
捨てることは禁止。front matter は先頭 1 回のみ。

レート制限 (HTTP 429) 対策:
  - チャンク間に CHUNK_SLEEP_SEC 秒スリープ (既定 7s = 10 RPM)
  - 429 受信時は exponential backoff で最大 MAX_RETRIES 回リトライ

Usage:
    python scripts/translate_gemini.py <source> <date> < email_content.txt > translated.md

Env:
    GITHUB_TOKEN             必須。workflow が渡す GITHUB_TOKEN
    TRANSLATION_MODEL        既定: openai/gpt-4o-mini  (本番推奨: openai/gpt-4.1)
    GITHUB_MODELS_ENDPOINT   既定: https://models.github.ai/inference
    CHUNK_CHAR_LIMIT         既定: 6500  (1 チャンクに含める最大文字数)
    CHUNK_SLEEP_SEC          既定: 7     (チャンク間スリープ秒数、rate limit 対策)
    MAX_RETRIES              既定: 3     (HTTP 429 時の最大リトライ回数)

Exit codes:
    0: 成功
    1: エラー
"""

import sys
import os
import re
import json
import time
import urllib.request
import urllib.error

TRANSLATE_PROMPT_PATH = "scripts/translate_prompt.md"
DEFAULT_ENDPOINT = "https://models.github.ai/inference"
DEFAULT_MODEL = "openai/gpt-4o-mini"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Groq API (OpenAI 互換) — 無料枠で 14,400 req/day, 30 RPM
GROQ_API_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# GPT-4.1 の入力上限は 8000 tokens。translate_prompt.md (~600 tok) と
# チャンク指示 (~200 tok) を除いた安全域として本文 6500 文字を既定とする。
# 日本語/英語混在で 1 tok ≈ 3 chars 想定 → 6500 chars ≈ 2200 tok。
# チャンク数削減により 429 rate limit (GPT-4.1 free tier: 10 RPM / 50 req/day) の
# 露出を下げる。さらに各チャンク呼び出し間に CHUNK_SLEEP_SEC 秒スリープし、
# 429 を受けたら exponential backoff でリトライする。
DEFAULT_CHUNK_CHAR_LIMIT = 6500
DEFAULT_CHUNK_SLEEP_SEC = 7
DEFAULT_MAX_RETRIES = 3

# 429 受信時のバックオフ遅延 (秒)。長さが MAX_RETRIES を下回る場合は末尾値を使い回す。
BACKOFF_DELAYS = [15, 30, 60]


def call_github_models(base_url: str, token: str, model: str, prompt: str,
                       max_retries: int = DEFAULT_MAX_RETRIES) -> str:
    """GitHub Models (OpenAI 互換) を呼び出して翻訳結果を返す。

    HTTP 429 (rate limit) の場合は exponential backoff で最大 max_retries 回リトライ。
    その他のエラーは即座に sys.exit(1)。
    """
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
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    last_error_msg = ""
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            text = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            print(
                f"[github-models] OK model={model} "
                f"tokens=in:{usage.get('prompt_tokens','?')}/out:{usage.get('completion_tokens','?')}"
                + (f" (retry {attempt})" if attempt > 0 else ""),
                file=sys.stderr,
            )
            return text

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(body).get("error", {}).get("message", body)
            except Exception:
                msg = body
            last_error_msg = f"HTTP {e.code}: {msg}"

            # 429 (rate limit) はリトライ対象
            if e.code == 429 and attempt < max_retries:
                delay = BACKOFF_DELAYS[attempt] if attempt < len(BACKOFF_DELAYS) else BACKOFF_DELAYS[-1]
                print(
                    f"[github-models] HTTP 429 rate-limited; backing off {delay}s "
                    f"(attempt {attempt + 1}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue

            print(f"[error] GitHub Models {last_error_msg}", file=sys.stderr)
            sys.exit(1)

        except Exception as e:
            print(f"[error] Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
            sys.exit(1)

    # ここに来ることは通常無い (ループ内で return か sys.exit) が念のため
    print(f"[error] GitHub Models exhausted retries: {last_error_msg}", file=sys.stderr)
    sys.exit(1)


def call_groq_api(api_key: str, prompt: str,
                  model: str = GROQ_DEFAULT_MODEL,
                  max_retries: int = DEFAULT_MAX_RETRIES) -> str:
    """Groq API (OpenAI 互換) を呼び出して翻訳結果を返す。

    GROQ_API_KEY が設定されている場合に優先使用。
    無料枠: 30 RPM / 14,400 RPD — バッチ処理に最適。
    HTTP 429 時は exponential backoff でリトライ。
    """
    url = f"{GROQ_API_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 8192,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error_msg = ""
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            print(
                f"[groq] OK model={model} "
                f"tokens=in:{usage.get('prompt_tokens','?')}/out:{usage.get('completion_tokens','?')}"
                + (f" (retry {attempt})" if attempt > 0 else ""),
                file=sys.stderr,
            )
            return text

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(body).get("error", {}).get("message", body)
            except Exception:
                msg = body
            last_error_msg = f"HTTP {e.code}: {msg}"

            if e.code == 429 and attempt < max_retries:
                delay = BACKOFF_DELAYS[attempt] if attempt < len(BACKOFF_DELAYS) else BACKOFF_DELAYS[-1]
                print(
                    f"[groq] HTTP 429 rate-limited; backing off {delay}s "
                    f"(attempt {attempt + 1}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue

            print(f"[error] Groq API {last_error_msg}", file=sys.stderr)
            sys.exit(1)

        except Exception as e:
            print(f"[error] Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[error] Groq API exhausted retries: {last_error_msg}", file=sys.stderr)
    sys.exit(1)


def call_gemini_api(api_key: str, prompt: str,
                    max_retries: int = DEFAULT_MAX_RETRIES) -> str:
    """Google Gemini API を直接呼び出して翻訳結果を返す (GEMINI_API_KEY 利用)。

    GitHub Models の代替バックエンド。GEMINI_API_KEY が設定されている場合に使用。
    HTTP 429 時は exponential backoff でリトライ。
    """
    url = f"{GEMINI_API_URL}?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    last_error_msg = ""
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            print(
                f"[gemini] OK" + (f" (retry {attempt})" if attempt > 0 else ""),
                file=sys.stderr,
            )
            return text

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                msg = json.loads(body).get("error", {}).get("message", body)
            except Exception:
                msg = body
            last_error_msg = f"HTTP {e.code}: {msg}"

            if e.code == 429 and attempt < max_retries:
                delay = BACKOFF_DELAYS[attempt] if attempt < len(BACKOFF_DELAYS) else BACKOFF_DELAYS[-1]
                print(
                    f"[gemini] HTTP 429 rate-limited; backing off {delay}s "
                    f"(attempt {attempt + 1}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue

            print(f"[error] Gemini API {last_error_msg}", file=sys.stderr)
            sys.exit(1)

        except Exception as e:
            print(f"[error] Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[error] Gemini API exhausted retries: {last_error_msg}", file=sys.stderr)
    sys.exit(1)


def split_into_chunks(text: str, limit: int) -> list:
    """段落単位で本文をチャンクに分割する。

    優先順位:
      1. 段落 (空行区切り) で分割し、可能な限り詰め込む
      2. 1 段落だけで limit を超える場合は行単位で分割
      3. 1 行だけで limit を超える場合は文字数で強制分割
    """
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        if not para.strip():
            continue

        # 1 段落で上限超え → 行単位で刻む
        if len(para) > limit:
            flush()
            lines = para.split("\n")
            buf = ""
            for line in lines:
                # 1 行で上限超え → 強制分割
                if len(line) > limit:
                    if buf:
                        chunks.append(buf.strip())
                        buf = ""
                    for i in range(0, len(line), limit):
                        chunks.append(line[i:i + limit])
                    continue
                if len(buf) + len(line) + 1 > limit:
                    if buf:
                        chunks.append(buf.strip())
                    buf = line
                else:
                    buf = (buf + "\n" + line) if buf else line
            if buf:
                current = buf
            continue

        # 通常ケース: 現在のチャンクに詰め込めるか判定
        if len(current) + len(para) + 2 > limit:
            flush()
            current = para
        else:
            current = (current + "\n\n" + para) if current else para

    flush()
    return [c for c in chunks if c.strip()]


def strip_code_fences(text: str) -> str:
    """モデル出力に付いた ``` フェンスを除去する。"""
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def extract_front_matter(markdown: str):
    """先頭 --- で囲まれた front matter を抽出する。

    戻り値: (front_matter_block or None, body_without_front_matter)
    """
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, markdown
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            front = "\n".join(lines[:i + 1])
            body = "\n".join(lines[i + 1:]).lstrip("\n")
            return front, body
    return None, markdown


def build_single_chunk_prompt(base_prompt: str, source: str, date: str, chunk: str) -> str:
    """短文用: 従来どおり 1 回で全文を翻訳する。"""
    return (
        f"{base_prompt}\n\n"
        f"---\n"
        f"SOURCE_SLUG: {source}\n"
        f"DATE: {date}\n"
        f"---\n\n"
        f"{chunk}"
    )


def build_chunk_prompt(base_prompt: str, source: str, date: str,
                       chunk: str, part: int, total: int) -> str:
    """長文用: PART i/N を指定したチャンク翻訳プロンプトを構築する。"""
    is_first = (part == 1)
    if is_first:
        directive = (
            "【分割翻訳の指示】\n"
            f"この本文は長いため {total} チャンクに分割されています。\n"
            f"あなたが今翻訳しているのは PART {part}/{total} (先頭) です。\n"
            "- 出力の先頭に front matter を 1 回だけ付けてください。\n"
            "- エグゼクティブサマリー表は本文全体を踏まえた内容で作成してください。\n"
            "- 本文は続編 (後続チャンク) があるため、最後は区切りのよい位置で止めて構いません。\n"
            "- 後続チャンクで重複して出ないよう、見出しや表は PART 1 で一度だけ出すこと。\n"
        )
    else:
        directive = (
            "【分割翻訳の指示】\n"
            f"この本文は長いため {total} チャンクに分割されています。\n"
            f"あなたが今翻訳しているのは PART {part}/{total} (続編) です。\n"
            "- front matter は絶対に出力しないでください (PART 1 で既に出力済み)。\n"
            "- タイトル行・配信元引用行・エグゼクティブサマリー表も重複させないでください。\n"
            "- このチャンクに含まれる記事・段落を、スタイルルールに従って本文のみ全訳してください。\n"
            "- 先頭に `---` や `# タイトル` を付けず、本文の続きから書き始めてください。\n"
        )
    return (
        f"{base_prompt}\n\n"
        f"{directive}\n"
        f"---\n"
        f"SOURCE_SLUG: {source}\n"
        f"DATE: {date}\n"
        f"---\n\n"
        f"{chunk}"
    )


def fallback_front_matter(source: str, date: str) -> str:
    """PART 1 が front matter を返さなかった場合の最低限のフォールバック。"""
    return (
        "---\n"
        f"title: \"{source}｜{date}\"\n"
        f"date: {date}\n"
        f"categories: [\"{source}\"]\n"
        f"tags: [\"{source}\"]\n"
        "summary: \"\"\n"
        "---"
    )


def main():
    if len(sys.argv) < 3:
        print("Usage: python translate_gemini.py <source> <date>", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1]
    date = sys.argv[2]

    token = os.environ.get("GITHUB_TOKEN")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    groq_api_key = os.environ.get("GROQ_API_KEY")

    # バックエンド優先順位: Groq (高レート制限) > Gemini > GitHub Models
    if groq_api_key:
        backend = "groq"
    elif gemini_api_key:
        backend = "gemini"
    elif token:
        backend = "github_models"
    else:
        print("[error] No API key found: set GROQ_API_KEY, GEMINI_API_KEY, or GITHUB_TOKEN",
              file=sys.stderr)
        sys.exit(1)

    # 後方互換のため use_gemini を維持
    use_gemini = (backend == "gemini")

    model = os.environ.get("TRANSLATION_MODEL", DEFAULT_MODEL)
    base_url = os.environ.get("GITHUB_MODELS_ENDPOINT", DEFAULT_ENDPOINT)
    groq_model = os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)

    try:
        chunk_limit = int(os.environ.get("CHUNK_CHAR_LIMIT", DEFAULT_CHUNK_CHAR_LIMIT))
    except ValueError:
        chunk_limit = DEFAULT_CHUNK_CHAR_LIMIT

    try:
        chunk_sleep_sec = float(os.environ.get("CHUNK_SLEEP_SEC", DEFAULT_CHUNK_SLEEP_SEC))
    except ValueError:
        chunk_sleep_sec = DEFAULT_CHUNK_SLEEP_SEC

    try:
        max_retries = int(os.environ.get("MAX_RETRIES", DEFAULT_MAX_RETRIES))
    except ValueError:
        max_retries = DEFAULT_MAX_RETRIES

    if backend == "groq":
        print(
            f"[groq] backend=Groq API model={groq_model} "
            f"chunk_limit={chunk_limit} chunk_sleep={chunk_sleep_sec}s "
            f"max_retries={max_retries}",
            file=sys.stderr,
        )
    elif backend == "gemini":
        print(
            f"[gemini] backend=Google Gemini API (gemini-2.5-flash) "
            f"chunk_limit={chunk_limit} chunk_sleep={chunk_sleep_sec}s "
            f"max_retries={max_retries}",
            file=sys.stderr,
        )
    else:
        print(
            f"[github-models] endpoint={base_url} model={model} "
            f"token={token[:4]}...{token[-4:]} (len={len(token)}) "
            f"chunk_limit={chunk_limit} chunk_sleep={chunk_sleep_sec}s "
            f"max_retries={max_retries}",
            file=sys.stderr,
        )

    email_content = sys.stdin.read()
    if not email_content.strip():
        print("[error] No email content provided via stdin", file=sys.stderr)
        sys.exit(1)
    print(f"[{backend}] Email content: {len(email_content)} bytes", file=sys.stderr)

    try:
        with open(TRANSLATE_PROMPT_PATH, "r", encoding="utf-8") as f:
            translate_prompt = f.read()
    except FileNotFoundError:
        print(f"[error] Prompt file not found: {TRANSLATE_PROMPT_PATH}", file=sys.stderr)
        sys.exit(1)

    # ── チャンク分割判定 ──
    if len(email_content) <= chunk_limit:
        chunks = [email_content]
    else:
        chunks = split_into_chunks(email_content, chunk_limit)

    total = len(chunks)
    backend_tag = f"[{backend}]"
    print(f"{backend_tag} chunk count: {total}", file=sys.stderr)
    for i, c in enumerate(chunks, 1):
        print(f"{backend_tag}   chunk {i}/{total}: {len(c)} chars", file=sys.stderr)

    def call_api(prompt: str) -> str:
        """バックエンドに応じて Groq / Gemini / GitHub Models を呼び出す。"""
        if backend == "groq":
            return call_groq_api(groq_api_key, prompt, model=groq_model, max_retries=max_retries)
        elif backend == "gemini":
            return call_gemini_api(gemini_api_key, prompt, max_retries=max_retries)
        else:
            return call_github_models(base_url, token, model, prompt, max_retries=max_retries)

    # ── 単一チャンク: 従来どおりの I/O 挙動を完全維持 ──
    if total == 1:
        full_prompt = build_single_chunk_prompt(translate_prompt, source, date, chunks[0])
        print(f"{backend_tag} Full prompt: {len(full_prompt)} bytes", file=sys.stderr)
        print(f"{backend_tag} Calling translation API (single chunk)...", file=sys.stderr)
        result = call_api(full_prompt)
        result = strip_code_fences(result)
        print(f"{backend_tag} Output: {len(result)} bytes", file=sys.stderr)
        print(result)
        sys.exit(0)

    # ── 複数チャンク: 分割翻訳 → 結合 ──
    front_matter = None
    bodies = []

    for i, chunk in enumerate(chunks, 1):
        prompt = build_chunk_prompt(translate_prompt, source, date, chunk, i, total)
        print(
            f"{backend_tag} Translating chunk {i}/{total} "
            f"(prompt={len(prompt)} bytes, chunk={len(chunk)} chars)...",
            file=sys.stderr,
        )
        result = call_api(prompt)
        result = strip_code_fences(result)

        fm, body = extract_front_matter(result)
        if i == 1:
            front_matter = fm
            bodies.append(body)
        else:
            if fm is not None:
                print(
                    f"{backend_tag} [warn] chunk {i} returned an extra front matter; discarding",
                    file=sys.stderr,
                )
            bodies.append(body)

        # チャンク間スリープ (最終チャンクの後は不要)
        if i < total and chunk_sleep_sec > 0:
            print(
                f"{backend_tag} sleeping {chunk_sleep_sec}s before next chunk...",
                file=sys.stderr,
            )
            time.sleep(chunk_sleep_sec)

    if front_matter is None:
        print(f"{backend_tag} [warn] PART 1 did not produce front matter; using fallback",
              file=sys.stderr)
        front_matter = fallback_front_matter(source, date)

    combined_body = "\n\n".join(b.strip() for b in bodies if b.strip())
    final = f"{front_matter}\n\n{combined_body}\n"

    print(
        f"{backend_tag} Final output: {len(final)} bytes "
        f"(combined from {total} chunks)",
        file=sys.stderr,
    )
    print(final)
    sys.exit(0)


if __name__ == "__main__":
    main()
