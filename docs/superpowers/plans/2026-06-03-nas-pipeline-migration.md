# NAS Pipeline Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub Actions の翻訳パイプラインを QNAP NAS 上の cron に移行し、コンテンツ（Markdown）のみを GitHub に push、画像は NAS ローカルに保存する。

**Architecture:** QNAP NAS が毎朝 JST 6:00 に Gmail から取得・OpenAI で翻訳・Unsplash 画像をローカル保存し、Markdown のみを GitHub に push する。GitHub Pages は変わらず静的サイトを配信し、画像は front matter の Unsplash URL 経由で表示する。

**Tech Stack:** Python 3.12, OpenAI API (gpt-4o-mini), Gmail OAuth2, Unsplash API, Git, QNAP Task Scheduler (cron)

---

## ファイルマップ

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `scripts/translate_openai.py` | **新規作成** | OpenAI gpt-4o-mini 翻訳スクリプト（NAS専用） |
| `scripts/run_pipeline.py` | **新規作成** | NAS オーケストレーター（全ソースを直列実行） |
| `scripts/generate_hero_image.py` | **修正** | PNG を `IMAGES_DIR` にダウンロード保存する機能追加 |
| `.env.example` | **新規作成** | QNAP 上の環境変数テンプレート |
| `.gitignore` | **修正** | `static/images/` `local_images/` `logs/` `*.env` を追加 |
| `.github/workflows/daily-translate.yml` | **修正** | cron トリガー削除、`workflow_dispatch` のみに変更（緊急用に温存） |

---

## Task 1: GitHub から画像を削除・.gitignore 更新

**Files:**
- Modify: `.gitignore`
- Action: `git rm -r --cached static/images/`

- [ ] **Step 1: .gitignore に追加**

```
# NAS migration: images stored locally, not in git
static/images/
local_images/
logs/
*.log
```

`.gitignore` の末尾に追記する。

- [ ] **Step 2: static/images/ を git 管理から外す（ファイルは残す）**

```bash
cd /tmp/newsletter-check
git rm -r --cached static/images/
```

Expected output: `rm 'static/images/nyt-bn/2026-04-01.png'` × 217件

- [ ] **Step 3: daily-translate.yml の cron トリガーを削除**

`.github/workflows/daily-translate.yml` の `on:` セクションを以下に変更する：

```yaml
on:
  # cron 廃止: NAS cron に移行 (2026-06-03)
  # 緊急時の手動実行のみ残す
  workflow_dispatch:
    inputs:
      sources:
        description: 'Sources to translate (comma-separated, or "all")'
        required: false
        default: 'all'
        type: string
      date_override:
        description: 'Date override (YYYY-MM-DD). Leave empty for today.'
        required: false
        default: ''
        type: string
      force_overwrite:
        description: 'Overwrite existing files (default: skip if exists)'
        required: false
        default: 'false'
        type: choice
        options:
          - 'false'
          - 'true'
```

- [ ] **Step 4: コミット＆プッシュ**

```bash
git add .gitignore .github/workflows/daily-translate.yml
git commit -m "chore: NAS移行 — static/images/ をgit管理から除外、daily-translate cron廃止"
git push
```

---

## Task 2: translate_openai.py 作成

**Files:**
- Create: `scripts/translate_openai.py`

- [ ] **Step 1: ファイル作成**

`scripts/translate_openai.py` を以下の内容で作成する：

```python
#!/usr/bin/env python3
"""
OpenAI API を使った翻訳スクリプト（NAS版）
GitHub Actions 版 translate_gemini.py の代替。
制限なし・安定・gpt-4o-mini で高品質翻訳。

Usage:
    python scripts/translate_openai.py <source> <YYYY-MM-DD> < email_content.txt
"""
import sys
import os
import json
import urllib.request
import urllib.error
import time
import re

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
CHUNK_CHAR_LIMIT = 12000   # NASは並列なし → 大きめチャンクで少ない API 呼び出し
CHUNK_SLEEP_SEC = 3        # チャンク間スリープ（秒）
BACKOFF_DELAYS = [15, 30, 60]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATE_PROMPT_PATH = os.path.join(SCRIPT_DIR, "translate_prompt.md")


def call_openai(api_key: str, prompt: str, model: str, max_retries: int = 3) -> str:
    """OpenAI Chat Completions API を呼び出し、テキストを返す。429 は backoff リトライ。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
    }).encode("utf-8")

    for attempt in range(max_retries):
        req = urllib.request.Request(OPENAI_API_URL, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                print(
                    f"[openai] OK model={model} "
                    f"tokens=in:{usage.get('prompt_tokens','?')}/out:{usage.get('completion_tokens','?')}",
                    file=sys.stderr,
                )
                return text
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < max_retries - 1:
                delay = BACKOFF_DELAYS[min(attempt, len(BACKOFF_DELAYS) - 1)]
                print(f"[openai] 429 rate-limited; backing off {delay}s (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(delay)
                continue
            raise RuntimeError(f"[openai] HTTP {e.code}: {body[:300]}")
        except Exception as e:
            if attempt < max_retries - 1:
                delay = BACKOFF_DELAYS[min(attempt, len(BACKOFF_DELAYS) - 1)]
                print(f"[openai] Error: {e}; retry in {delay}s", file=sys.stderr)
                time.sleep(delay)
                continue
            raise


def split_into_chunks(text: str, limit: int) -> list:
    """テキストを段落単位で limit 文字以下のチャンクに分割する。"""
    if len(text) <= limit:
        return [text]
    chunks, current, current_len = [], [], 0
    for para in text.split("\n\n"):
        if current and current_len + len(para) + 2 > limit:
            chunks.append("\n\n".join(current))
            current, current_len = [para], len(para)
        else:
            current.append(para)
            current_len += len(para) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def strip_code_fences(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def extract_front_matter(markdown: str):
    """先頭 --- ブロックを (front_matter, body) に分離する。"""
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, markdown
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[:i + 1]), "\n".join(lines[i + 1:]).lstrip("\n")
    return None, markdown


def build_prompt(base_prompt: str, source: str, date: str, chunk: str, part: int = 1, total: int = 1) -> str:
    header = f"---\nSOURCE_SLUG: {source}\nDATE: {date}\n---\n\n"
    if total == 1:
        return f"{base_prompt}\n\n{header}{chunk}"
    if part == 1:
        directive = (
            f"【分割翻訳 PART {part}/{total}】\n"
            "- front matter を先頭に1回だけ出力すること\n"
            "- エグゼクティブサマリー表を出力すること\n"
            "- このチャンクの全記事を翻訳すること\n\n"
        )
    else:
        directive = (
            f"【分割翻訳 PART {part}/{total}】\n"
            "- front matter・タイトル・ESS表は出力しないこと\n"
            "- このチャンクの記事本文のみ続きから出力すること\n\n"
        )
    return f"{base_prompt}\n\n{directive}{header}{chunk}"


def main():
    if len(sys.argv) < 3:
        print("Usage: python translate_openai.py <source> <YYYY-MM-DD>", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1]
    date = sys.argv[2]
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[error] OPENAI_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("TRANSLATION_MODEL", DEFAULT_MODEL)

    try:
        with open(TRANSLATE_PROMPT_PATH, "r", encoding="utf-8") as f:
            base_prompt = f.read()
    except FileNotFoundError:
        print(f"[error] プロンプトファイルが見つかりません: {TRANSLATE_PROMPT_PATH}", file=sys.stderr)
        sys.exit(1)

    email_content = sys.stdin.read()
    if not email_content.strip():
        print("[error] 標準入力にコンテンツがありません", file=sys.stderr)
        sys.exit(1)

    print(f"[openai] model={model} input={len(email_content)} chars", file=sys.stderr)

    chunks = split_into_chunks(email_content, CHUNK_CHAR_LIMIT)
    total = len(chunks)
    print(f"[openai] chunks={total}", file=sys.stderr)

    if total == 1:
        prompt = build_prompt(base_prompt, source, date, chunks[0])
        result = strip_code_fences(call_openai(api_key, prompt, model))
        print(result)
        return

    # 複数チャンク: 分割翻訳 → 結合
    front_matter = None
    bodies = []
    for i, chunk in enumerate(chunks, 1):
        print(f"[openai] chunk {i}/{total} ({len(chunk)} chars)...", file=sys.stderr)
        prompt = build_prompt(base_prompt, source, date, chunk, i, total)
        result = strip_code_fences(call_openai(api_key, prompt, model))
        fm, body = extract_front_matter(result)
        if i == 1:
            front_matter = fm
        bodies.append(body if fm else result)
        if i < total:
            time.sleep(CHUNK_SLEEP_SEC)

    if front_matter is None:
        front_matter = (
            f"---\ntitle: \"{source}｜{date}\"\ndate: {date}\n"
            f"categories: [\"{source}\"]\n---"
        )

    combined = "\n\n".join(b.strip() for b in bodies if b.strip())
    print(f"{front_matter}\n\n{combined}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 構文チェック**

```bash
python3 -c "import ast; ast.parse(open('scripts/translate_openai.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: コミット**

```bash
git add scripts/translate_openai.py
git commit -m "feat: translate_openai.py — NAS用 OpenAI gpt-4o-mini 翻訳スクリプト"
```

---

## Task 3: generate_hero_image.py に PNG ダウンロード機能追加

**Files:**
- Modify: `scripts/generate_hero_image.py`

現在の `generate_hero_image.py` は Unsplash URL を front matter に注入するだけで PNG をダウンロードしない。`IMAGES_DIR` 環境変数が設定されている場合に PNG をダウンロード保存する機能を追加する。

- [ ] **Step 1: main() の inject_hero_image 呼び出し後に PNG ダウンロード処理を追加**

`scripts/generate_hero_image.py` の `main()` 関数内、`inject_hero_image(md_path, image_url)` の直後（約375行目付近）に以下を追加する：

```python
    # NAS用: IMAGES_DIR が設定されていれば PNG をローカルに保存
    images_dir = os.environ.get("IMAGES_DIR", "")
    if images_dir and image_url:
        try:
            import urllib.request as _req
            dest_dir = os.path.join(images_dir, source)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, f"{date}.jpg")
            _req.urlretrieve(image_url.split("?")[0], dest_path)
            log.info(f"PNG saved to {dest_path}")
        except Exception as e:
            log.warning(f"PNG download failed (non-blocking): {e}")
```

- [ ] **Step 2: 構文チェック**

```bash
python3 -m py_compile scripts/generate_hero_image.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: コミット**

```bash
git add scripts/generate_hero_image.py
git commit -m "feat: generate_hero_image — IMAGES_DIR 設定時に PNG をローカル保存"
```

---

## Task 4: run_pipeline.py 作成（NAS オーケストレーター）

**Files:**
- Create: `scripts/run_pipeline.py`

- [ ] **Step 1: ファイル作成**

`scripts/run_pipeline.py` を以下の内容で作成する：

```python
#!/usr/bin/env python3
"""
NAS Pipeline Orchestrator — Bolgheri Daily Brief
毎日 JST 6:00 に QNAP Task Scheduler から実行する。

実行前に .env を読み込む（setup_qnap.sh 参照）:
    source /path/to/.env && python3 scripts/run_pipeline.py

または crontab で:
    0 6 * * * cd /share/newsletter && source .env && python3 scripts/run_pipeline.py
"""
import os
import sys
import subprocess
import datetime
import pathlib
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            pathlib.Path(__file__).parent.parent / "logs" / f"pipeline_{datetime.date.today()}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger(__name__)

SCRIPT_DIR = pathlib.Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
CONTENT_DIR = REPO_DIR / "content"
IMAGES_DIR = pathlib.Path(os.environ.get("IMAGES_DIR", str(REPO_DIR / "local_images")))

SOURCES = [
    "nyt-bn", "wsj", "dealbook", "economist", "business-insider",
    "skift", "buysiders", "short-squeez", "nyt-op", "cnbc", "cnbc-squawk",
]

# 週次配信ソース（月曜のみ）
WEEKLY_SOURCES = {"buysiders"}


def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def get_today_jst() -> str:
    try:
        from zoneinfo import ZoneInfo
        jst = ZoneInfo("Asia/Tokyo")
    except ImportError:
        import datetime as _dt
        return (_dt.datetime.utcnow() + _dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    return datetime.datetime.now(jst).strftime("%Y-%m-%d")


def is_weekday(date_str: str) -> bool:
    d = datetime.date.fromisoformat(date_str)
    return d.weekday() < 5  # 0=Mon, 4=Fri


def is_monday(date_str: str) -> bool:
    return datetime.date.fromisoformat(date_str).weekday() == 0


def main():
    (REPO_DIR / "logs").mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    date = os.environ.get("DATE_OVERRIDE") or get_today_jst()
    log.info(f"=== NAS Pipeline start: {date} ===")

    if not is_weekday(date):
        log.info("週末のためスキップ")
        return

    ok = skip = fail = 0

    for source in SOURCES:
        content_file = CONTENT_DIR / source / f"{date}.md"

        # 週次ソースの曜日チェック
        if source in WEEKLY_SOURCES and not is_monday(date):
            log.info(f"  [{source}] 週次ソースのため月曜以外はスキップ")
            skip += 1
            continue

        # 冪等性チェック
        if content_file.exists() and content_file.stat().st_size > 500:
            log.info(f"  [{source}] 既存ファイルあり、スキップ")
            skip += 1
            continue

        log.info(f"  [{source}] fetch 開始...")

        # ── Step 1: Gmail fetch ──
        fetch = run(
            ["python3", str(SCRIPT_DIR / "fetch_gmail.py"), source, date],
            env={**os.environ},
        )
        if fetch.returncode != 0:
            log.error(f"  [{source}] fetch 失敗: {fetch.stderr[-200:]}")
            fail += 1
            continue
        if "NO_EMAIL_FOUND" in fetch.stdout:
            log.info(f"  [{source}] メールなし")
            skip += 1
            continue

        # ── Step 2: 翻訳 ──
        (CONTENT_DIR / source).mkdir(parents=True, exist_ok=True)
        translate = run(
            ["python3", str(SCRIPT_DIR / "translate_openai.py"), source, date],
            input=fetch.stdout,
            env={**os.environ},
        )
        translated = translate.stdout.strip()

        # 完全性チェック: front matter あり + 500字以上
        if (translate.returncode != 0
                or not translated.startswith("---")
                or len(translated) < 500):
            log.error(f"  [{source}] 翻訳失敗 (exit={translate.returncode})")
            log.error(translate.stderr[-300:])
            fail += 1
            continue

        content_file.write_text(translated + "\n", encoding="utf-8")
        log.info(f"  [{source}] ✅ → {content_file}")
        ok += 1

        # ── Step 3: ヒーロー画像（non-blocking）──
        hero = run(
            ["python3", str(SCRIPT_DIR / "generate_hero_image.py"), source, date],
            env={**os.environ, "IMAGES_DIR": str(IMAGES_DIR)},
        )
        if hero.returncode == 0:
            log.info(f"  [{source}] 🎨 hero image OK")
        else:
            log.warning(f"  [{source}] 🎨 hero image skip (non-blocking)")

    log.info(f"翻訳完了: OK={ok} SKIP={skip} FAIL={fail}")

    # ── Step 4: git push（新規ファイルがある場合のみ）──
    if ok > 0:
        log.info("GitHub へ push 中...")
        run(["git", "-C", str(REPO_DIR), "add", "content/"])
        run(["git", "-C", str(REPO_DIR), "pull", "--rebase", "--autostash", "origin", "main"])
        commit = run([
            "git", "-C", str(REPO_DIR), "commit",
            "-m", f"Daily newsletter {date} [{ok} file(s)]",
            "--author", "NAS-Pipeline <nas@bolgheri.local>",
        ])
        if commit.returncode == 0:
            push = run(["git", "-C", str(REPO_DIR), "push"])
            if push.returncode == 0:
                log.info(f"✅ GitHub に {ok}件 push 完了")
            else:
                log.error(f"push 失敗: {push.stderr}")
        else:
            log.info("コミットなし（変更なし）")
    else:
        log.info("新規ファイルなし、push スキップ")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 構文チェック**

```bash
python3 -m py_compile scripts/run_pipeline.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: コミット**

```bash
git add scripts/run_pipeline.py
git commit -m "feat: run_pipeline.py — NAS cron 用オーケストレーター"
```

---

## Task 5: .env.example 作成

**Files:**
- Create: `.env.example`

- [ ] **Step 1: ファイル作成**

`.env.example` を以下の内容で作成する：

```bash
# Bolgheri Daily Brief — NAS Pipeline 環境変数
# このファイルを .env にコピーして各値を設定する
# cp .env.example .env

# Gmail OAuth2（既存の値をそのまま使う）
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=

# OpenAI API（翻訳）
OPENAI_API_KEY=sk-...
TRANSLATION_MODEL=gpt-4o-mini

# Unsplash（ヒーロー画像）
UNSPLASH_ACCESS_KEY=

# NAS 画像保存先（絶対パス）
# QNAP 例: /share/homes/admin/newsletter-images
IMAGES_DIR=/share/homes/admin/newsletter-images

# GitHub（git push 用）
# Personal Access Token (repo スコープ) を使う
# git remote set-url origin https://<TOKEN>@github.com/TH1214/newsletter-dashboard.git
# で設定するので .env には不要（参考のみ）

# 日付オーバーライド（通常は不要、デバッグ用）
# DATE_OVERRIDE=2026-06-03
```

- [ ] **Step 2: コミット**

```bash
git add .env.example
git commit -m "docs: .env.example — QNAP NAS pipeline 環境変数テンプレート"
```

---

## Task 6: GitHub への一括 push

- [ ] **Step 1: 最終確認**

```bash
cd /tmp/newsletter-check
git log --oneline -8
git status
```

Expected: 変更なし、以下のようなコミット履歴：
```
feat: run_pipeline.py — NAS cron 用オーケストレーター
feat: translate_openai.py — NAS用 OpenAI gpt-4o-mini 翻訳スクリプト
feat: generate_hero_image — IMAGES_DIR 設定時に PNG をローカル保存
docs: .env.example — QNAP NAS pipeline 環境変数テンプレート
chore: NAS移行 — static/images/ をgit管理から除外、daily-translate cron廃止
```

- [ ] **Step 2: push**

```bash
git push
```

---

## Task 7: QNAP セットアップ手順（作業者向けガイド）

以下の手順を QNAP で実行する（SSH 接続）：

### 7-1. リポジトリのクローン

```bash
ssh admin@<QNAP-IP>
cd /share/homes/admin
git clone https://<GITHUB_PAT>@github.com/TH1214/newsletter-dashboard.git
cd newsletter-dashboard
```

### 7-2. Python 確認（QNAP App Center で Python 3 インストール済み前提）

```bash
python3 --version
# Python 3.x.x が表示されること
```

※ Python が入っていない場合: QNAP App Center → Python 3 をインストール

### 7-3. .env 設定

```bash
cp .env.example .env
vi .env
# 各値を設定:
# GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN → 既存の値
# OPENAI_API_KEY → OpenAI Dashboard から取得
# UNSPLASH_ACCESS_KEY → Unsplash Developer から取得
# IMAGES_DIR=/share/homes/admin/newsletter-images
```

### 7-4. GitHub push 設定（PAT を使う）

```bash
git remote set-url origin https://<GITHUB_PAT>@github.com/TH1214/newsletter-dashboard.git
git config user.name "NAS-Pipeline"
git config user.email "nas@bolgheri.local"
```

### 7-5. 動作確認（手動実行）

```bash
cd /share/homes/admin/newsletter-dashboard
source .env
python3 scripts/run_pipeline.py
# OK=X SKIP=Y FAIL=0 が出れば成功
# GitHub に push されたか確認
```

### 7-6. QNAP Task Scheduler 設定（GUI）

Control Panel → Task Scheduler → Create → Scheduled Task:
- Task name: `Bolgheri Daily Newsletter`
- Schedule: Daily, 06:00 JST
- Command:
```bash
cd /share/homes/admin/newsletter-dashboard && source .env && python3 scripts/run_pipeline.py
```

---

## 完了後チェックリスト

- [ ] `static/images/` が git から外れている（`git ls-files static/images/ | wc -l` → 0）
- [ ] `daily-translate.yml` に cron がない
- [ ] QNAP で `run_pipeline.py` が手動実行で成功する
- [ ] GitHub に content/*.md が push される
- [ ] GitHub Pages でサイトが更新される
- [ ] 画像が `$IMAGES_DIR/{source}/{date}.jpg` に保存される
- [ ] 翌朝 6:00 JST に自動実行される
