# Axios 統合ニュースレター（3タイトル）Dashboard 追加 — 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Axios の定期編集ニュースレター12種を、Dashboard 上の3つの統合タイトル（Axios Daily / Axios AI+PE/MA/VC / Axios Def/CAR/2028）として、既存の翻訳・画像パイプラインに乗せて掲載する。

**Architecture:** 既存「1ソース＝1記事」パイプラインに3つの「複数メンバー集約ソース」を追加する。`fetch_gmail.py` を `members` 構造対応に拡張し、各メンバーの当日最新1通を取得→HTML除去＋ボイラープレート除去→メンバー境界マーカー付きで連結したテキストを出力。翻訳は既存 `translate_gemini.py`（CNBC同様のチャンク分割）、画像は既存 `generate_hero_image.py` を流用。集約単位は「その日届いた分だけ」。

**Tech Stack:** Python 3.12（標準ライブラリのみ）、GitHub Actions（YAML）、Next.js/TypeScript（v2-next）、Gmail API、GitHub Models（gpt-4o-mini）、Unsplash。

設計スペック: `docs/superpowers/specs/2026-06-27-axios-consolidated-newsletters-design.md`

## Global Constraints

以下はスペックのプロジェクト全体要件。全タスクに暗黙的に適用される。

- 翻訳モデル `openai/gpt-4o-mini`、`CHUNK_CHAR_LIMIT=24000`、レート 150 req/日（現状 ~25 → 目標 ~32）。
- 出力 Markdown に絵文字・emoji を一切使わない。見出しは `##` / `###` のみ。
- ソース追加は宣言的7点（SOURCES / daily-translate matrix / batch-backfill / sections.ts / SectionNav / translate_prompt.md / `_index.md`）。
- **Gmail クエリは set 前に必ず Gmail MCP で実検証**（2026-06-13 PERE 取りこぼし事故の教訓）。
- `fetch_gmail.py` / `translate_gemini.py` は write-only の GitHub Secret。ローカルにマスター無し。再構築基点 = git 履歴 `a44ced5~1:scripts/fetch_gmail.py`（後付け3ソースのクエリは daily run ログ `[fetch] Searching:` 行から採取）。
- gpt-4o-mini は「除外」指示を無視しがち → 除去対象は「絶対厳守」見出し＋具体マーカー文字列で明示。
- 翻訳出力に front matter を二重に出さない（チャンク継続は本文のみ）。CNBC 方式を踏襲。
- 集約単位は「その日届いた分だけ／1日1記事」。ローリング蓄積・事後再翻訳はしない。
- 3 slug 固定: `axios-daily`(Axios Daily) / `axios-ai`(Axios AI+PE/MA/VC) / `axios-frontier`(Axios Def/CAR/2028)。
- リポジトリ作業は clone 後。`docs/` のみの変更は deploy をトリガーしない（deploy 条件 = `content/**`・`v2-next/**`・`static/images/**`）。

## メンバー定義（全タスク共通参照）

```
axios-daily    : Axios AM / Axios PM / Axios Finish Line / Axios Closer / Axios Markets / Axios Macro
axios-ai       : Axios Pro Rata / Axios AI+ / Axios AI+ Government
axios-frontier : Axios Mobility / Axios Defense / Axios 2028
```

メンバー連結マーカー（不変条件）: 各メンバー本文の直前に1行
`=== MEMBER: <label> | <件名> ===` を置く。

## File Structure

| ファイル | 責務 | 種別 |
|---|---|---|
| `scripts/fetch_gmail.py`（secret 実体） | メンバー集約フェッチ＋HTML/ボイラープレート除去＋連結出力 | 拡張 |
| `scripts/test_fetch_axios.py` | 純関数（stripper / concatenator）の単体テスト | 新規 |
| `scripts/translate_prompt.md` | Axios 統合翻訳ルール | 拡張 |
| `.github/workflows/daily-translate.yml` | matrix に3slug / timeout60 / WEEKLY | 拡張 |
| `.github/workflows/batch-backfill.yml` | ALL_SOURCES に3slug | 拡張 |
| `v2-next/lib/sections.ts` | 3セクション定義 | 拡張 |
| `v2-next/components/SectionNav.tsx` | SHORT 短縮ラベル3件 | 拡張 |
| `content/axios-daily/_index.md` 他2 | セクション index | 新規 |

---

### Task 1: メンバークエリを Gmail MCP で実検証

**Files:**
- Create: `docs/superpowers/notes/2026-06-27-axios-verified-queries.md`（検証結果メモ）

**Interfaces:**
- Produces: 12メンバーの「検証済み Gmail クエリ文字列」テーブル。Task 4 がこれを SOURCES に転記する。

このタスクはコード変更前のゲート。AM/PM/Finish Line は同一 From (`mike@axios.com`) のため subject 分離が必須。

- [ ] **Step 1: 各メンバークエリを Gmail MCP で実行**

以下の候補クエリを `mcp__gmail__search_emails` で1つずつ実行し、`maxResults: 5`、想定どおり当該メンバーのみ・最新1通が取れることを確認する。

```
Axios AM          : from:mike@axios.com subject:"Axios AM"
Axios PM          : from:mike@axios.com subject:"Axios PM"
Axios Finish Line : from:mike@axios.com subject:"Finish Line"
Axios Closer      : from:closer@axios.com
Axios Markets     : from:markets@axios.com
Axios Macro       : from:macro@axios.com
Axios Pro Rata    : from:dan@axios.com
Axios AI+         : from:ai.plus@axios.com
Axios AI+ Gov     : from:ai.plus.gov@axios.com
Axios Mobility    : from:mobility@axios.com
Axios Defense     : from:defense@axios.com
Axios 2028        : from:2028@axios.com
```

- [ ] **Step 2: Pro Rata の送信者ゆれを確認**

Pro Rata は曜日で著者が変わる（dan@ / lucinda.shen@ / Kia Kokalitcheva 等）。`from:dan@axios.com` で平日の取りこぼしが出るなら、件名側に寄せる:
Run（MCP）: `from:axios.com subject:"Pro Rata"`
Expected: 平日・土曜の Pro Rata が全てヒット。ヒットすれば Pro Rata の確定クエリを `subject:"Pro Rata"` に変更する。

- [ ] **Step 3: AM/PM/Finish Line の相互排他を確認**

Run（MCP）: `from:mike@axios.com subject:"Axios AM"` と `subject:"Axios PM"` と `subject:"Finish Line"` の3つ。
Expected: それぞれが他2種を1通も含まない（subject 重複が無い）こと。混線したら subject 句を厳格化（例: `subject:"Axios AM:"` のようにコロン込み）し再検証。

- [ ] **Step 4: 確定クエリ表をメモに記録**

12メンバーの最終確定クエリを `docs/superpowers/notes/2026-06-27-axios-verified-queries.md` に表で記録（Task 4 / 将来の secret 再構築の一次資料）。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/notes/2026-06-27-axios-verified-queries.md
git commit -m "docs(axios): Gmail MCPで検証済みのメンバークエリ12件を記録"
```

---

### Task 2: 現行 fetch_gmail.py（secret 実体）をローカルに再構築

**Files:**
- Create: `/tmp/fetch_gmail_real.py`（ローカル作業コピー。リポジトリにはコミットしない）

**Interfaces:**
- Consumes: なし
- Produces: 既存14ソースを現状どおり処理できる、編集可能な実 `fetch_gmail.py` 作業コピー。Task 3/4 がこれを編集する。

secret は write-only でマスターが無いため、git 履歴の既知良好版を基点に現行14ソース版を再構築する。

- [ ] **Step 1: 全履歴を取得**

```bash
git fetch --unshallow 2>/dev/null || git fetch --depth=200
git show a44ced5~1:scripts/fetch_gmail.py | head -5
```
Expected: 262行程度の本物のフェッチロジックが表示される（`SOURCES = {` を含む）。表示されなければ `git log --oneline --all -- scripts/fetch_gmail.py` で実体のある最新コミットを探す。

- [ ] **Step 2: 基点をローカルへ展開**

```bash
git show a44ced5~1:scripts/fetch_gmail.py > /tmp/fetch_gmail_real.py
grep -n '"query"' /tmp/fetch_gmail_real.py   # 11ソース分のクエリを確認
```
Expected: 11ソース（wsj, nyt-bn, dealbook, economist, business-insider, skift, buysiders, short-squeez, nyt-op, cnbc, cnbc-squawk）の SOURCES。

- [ ] **Step 3: 後付け3ソース（pere/maverick/hospitality-net）のクエリを run ログから採取**

```bash
gh run list -R TH1214/newsletter-dashboard --workflow daily-translate.yml -L 20
# 成功 run を1つ選び:
gh run view <RUN_ID> -R TH1214/newsletter-dashboard --log | grep -i "Searching" | grep -iE "pere|maverick|hospitality"
```
Expected: `[fetch] Searching: <query>` 行から3ソースのクエリ文字列を採取。`/tmp/fetch_gmail_real.py` の SOURCES に3エントリを追記（label/query、必要なら multi）。

- [ ] **Step 4: 既存ソースで出力一致を確認（回帰ガード）**

ローカル実行には Gmail OAuth env が要る。env が無い環境では本ステップを「smoke のみ」に縮退してよいが、可能なら:
```bash
GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... GMAIL_REFRESH_TOKEN=... \
  python /tmp/fetch_gmail_real.py wsj | head -20
```
Expected: WSJ の当日テキストが NO_EMAIL_FOUND ではなく本文として出る（基点の健全性確認）。env 不可なら Task 5 の workflow_dispatch smoke で代替する旨をメモ。

- [ ] **Step 5: Commit（作業ノートのみ）**

`/tmp` の作業コピーはコミットしない。再構築手順の確認結果を Task 1 のメモに追記してコミット。
```bash
git add docs/superpowers/notes/2026-06-27-axios-verified-queries.md
git commit -m "docs(axios): fetch_gmail.py再構築の基点(a44ced5~1)と後付け3ソース採取手順を記録"
```

---

### Task 3: ボイラープレート除去＋メンバー連結（純関数）を TDD で追加

**Files:**
- Modify: `/tmp/fetch_gmail_real.py`（関数を追記）
- Test: `scripts/test_fetch_axios.py`（リポジトリにコミットする）

**Interfaces:**
- Produces:
  - `strip_axios_boilerplate(text: str) -> str` — Axios 本文テキストからスポンサー枠・SB宣伝・フッター・マストヘッド定型を除去して返す。
  - `build_member_block(label: str, subject: str, body: str) -> str` — `=== MEMBER: <label> | <subject> ===\n<stripped body>\n` を返す。
  - `concat_members(blocks: list[str]) -> str` — メンバーブロックを `\n\n` 連結。空リストなら空文字。

これら純関数は実 Gmail 不要でテスト可能。`scripts/test_fetch_axios.py` は除去関数の本体を import するため、関数定義は実 `fetch_gmail.py` 側にも置きつつ、テストからは同名ロジックを検証する（テストはコピーロジックではなく実関数を参照する形にするため、テスト実行時に `/tmp/fetch_gmail_real.py` を `scripts/_axios_fetch_lib.py` としても保存し、そこから import する。secret 化の際はこの lib 内容を fetch_gmail.py 本体へ取り込む）。

- [ ] **Step 1: テストを書く（失敗する状態）**

`scripts/test_fetch_axios.py`:
```python
import importlib.util, pathlib, sys

# 純関数ライブラリを読み込む（fetch_gmail.py から切り出した Axios 補助関数）
_spec = importlib.util.spec_from_file_location(
    "axios_fetch_lib", pathlib.Path(__file__).with_name("_axios_fetch_lib.py")
)
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)


def test_strip_removes_sponsor_block():
    text = (
        "Why it matters: this stays.\n"
        "A MESSAGE FROM COMCAST\n"
        "Buy our stuff. Learn more.\n"
        "The bottom line: keep this."
    )
    out = lib.strip_axios_boilerplate(text)
    assert "this stays" in out
    assert "keep this" in out
    assert "COMCAST" not in out
    assert "Buy our stuff" not in out


def test_strip_removes_smart_brevity_promo_and_footer():
    text = (
        "Real content line.\n"
        "Like this comms style and format? It's called Smart Brevity.\n"
        "Was this email forwarded to you? Sign up now.\n"
        "Axios, PO Box 101060, Arlington VA 22201\n"
        "Unsubscribe | Manage preferences"
    )
    out = lib.strip_axios_boilerplate(text)
    assert "Real content line." in out
    assert "Smart Brevity" not in out
    assert "Arlington VA" not in out
    assert "Unsubscribe" not in out


def test_strip_keeps_smart_brevity_labels():
    # 本文中の Why it matters: / The bottom line: は残す
    text = "1 big thing: X\nWhy it matters: Y\nThe bottom line: Z"
    out = lib.strip_axios_boilerplate(text)
    assert "Why it matters: Y" in out
    assert "The bottom line: Z" in out


def test_build_member_block_has_marker():
    block = lib.build_member_block("Axios AM", "Blind loyalty", "body text")
    assert block.startswith("=== MEMBER: Axios AM | Blind loyalty ===")
    assert "body text" in block


def test_concat_members_empty_is_empty():
    assert lib.concat_members([]) == ""


def test_concat_members_joins_with_blank_line():
    out = lib.concat_members(["A", "B"])
    assert out == "A\n\nB"
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
cp /tmp/fetch_gmail_real.py scripts/_axios_fetch_lib.py
python -m pytest scripts/test_fetch_axios.py -v
```
Expected: FAIL（`strip_axios_boilerplate` / `build_member_block` / `concat_members` が未定義で AttributeError）。

- [ ] **Step 3: 純関数を実装**

`/tmp/fetch_gmail_real.py` の末尾（main の前）に追記し、`scripts/_axios_fetch_lib.py` にも反映:
```python
import re as _re

# Axios メールの非編集ブロック。行単位で前方一致/部分一致除去する。
_AXIOS_DROP_LINE_MARKERS = (
    "A MESSAGE FROM",
    "PRESENTED BY",
    "Presented By",
    "Like this comms style and format",
    "It's called Smart Brevity",
    "Was this email forwarded to you",
    "Sign up now",
    "Please invite your friends",
    "Advertise with us",
    "Sponsorship has no influence",
    "View in browser",
    "Unsubscribe",
    "Manage preferences",
    "Arlington VA",
    "PO Box 101060",
    "3100 Clarendon",
)


def strip_axios_boilerplate(text: str) -> str:
    """Axios 本文からスポンサー枠・SB宣伝・フッター等の非編集行を除去。
    本文中の Smart Brevity ラベル (Why it matters: 等) は残す。"""
    out_lines = []
    skip_block = False
    for raw in text.splitlines():
        line = raw.rstrip()
        # 'A MESSAGE FROM' / 'PRESENTED BY' は次の 'Learn more.' まで広告ブロックとして読み飛ばす
        if line.strip().startswith(("A MESSAGE FROM", "PRESENTED BY", "Presented By")):
            skip_block = True
            continue
        if skip_block:
            if "Learn more" in line or line.strip() == "":
                skip_block = False
            continue
        if any(m in line for m in _AXIOS_DROP_LINE_MARKERS):
            continue
        out_lines.append(line)
    # 連続空行を1つに畳む
    collapsed = _re.sub(r"\n{3,}", "\n\n", "\n".join(out_lines))
    return collapsed.strip()


def build_member_block(label: str, subject: str, body: str) -> str:
    clean = strip_axios_boilerplate(body)
    return f"=== MEMBER: {label} | {subject} ===\n{clean}\n"


def concat_members(blocks: list) -> str:
    return "\n\n".join(b.strip() for b in blocks if b and b.strip())
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
cp /tmp/fetch_gmail_real.py scripts/_axios_fetch_lib.py
python -m pytest scripts/test_fetch_axios.py -v
```
Expected: 6 passed。

- [ ] **Step 5: Commit**

```bash
git add scripts/test_fetch_axios.py scripts/_axios_fetch_lib.py
git commit -m "feat(axios): ボイラープレート除去＋メンバー連結の純関数とテストを追加"
```

---

### Task 4: 3つの集約ソース（members 構造）を fetch_gmail.py に追加

**Files:**
- Modify: `/tmp/fetch_gmail_real.py`（SOURCES に3エントリ＋集約フェッチ分岐）
- Modify: `scripts/_axios_fetch_lib.py`（同期）

**Interfaces:**
- Consumes: `strip_axios_boilerplate` / `build_member_block` / `concat_members`（Task 3）、Task 1 の確定クエリ。
- Produces: `python fetch_gmail.py axios-daily [YYYY-MM-DD]` が、当日届いたメンバーを連結したテキストを stdout に出力（全未着なら `NO_EMAIL_FOUND`）。`axios-ai` / `axios-frontier` も同様。

- [ ] **Step 1: SOURCES に3集約エントリを追加**

`/tmp/fetch_gmail_real.py` の `SOURCES` 辞書に追加（query は Task 1 の確定値で置換）:
```python
SOURCES["axios-daily"] = {"members": [
    {"label": "Axios AM",          "query": 'from:mike@axios.com subject:"Axios AM"'},
    {"label": "Axios PM",          "query": 'from:mike@axios.com subject:"Axios PM"'},
    {"label": "Axios Finish Line", "query": 'from:mike@axios.com subject:"Finish Line"'},
    {"label": "Axios Closer",      "query": "from:closer@axios.com"},
    {"label": "Axios Markets",     "query": "from:markets@axios.com"},
    {"label": "Axios Macro",       "query": "from:macro@axios.com"},
]}
SOURCES["axios-ai"] = {"members": [
    {"label": "Axios Pro Rata",      "query": 'from:axios.com subject:"Pro Rata"'},
    {"label": "Axios AI+",           "query": "from:ai.plus@axios.com"},
    {"label": "Axios AI+ Government", "query": "from:ai.plus.gov@axios.com"},
]}
SOURCES["axios-frontier"] = {"members": [
    {"label": "Axios Mobility", "query": "from:mobility@axios.com"},
    {"label": "Axios Defense",  "query": "from:defense@axios.com"},
    {"label": "Axios 2028",     "query": "from:2028@axios.com"},
]}
```

- [ ] **Step 2: 集約フェッチ分岐を main に追加**

`fetch_gmail.py` の main（SOURCE を引数で受けて SOURCES を引くロジック）に、`members` を持つソースの分岐を追加。既存の単一クエリ処理は温存する。挿入位置は「SOURCE の設定を引いた直後・単一クエリfetchの前」。
```python
cfg = SOURCES[source]
if "members" in cfg:
    blocks = []
    for m in cfg["members"]:
        # 既存の単一メール取得関数を再利用（当日最新1通の subject と本文テキストを返す）。
        # 関数名は実装に合わせる: ここでは fetch_latest_message(query, date) -> (subject, body) or None
        hit = fetch_latest_message(m["query"], target_date)
        if hit is None:
            sys.stderr.write(f"[fetch] member empty: {m['label']}\n")
            continue
        subject, body = hit
        blocks.append(build_member_block(m["label"], subject, body))
    if not blocks:
        print("NO_EMAIL_FOUND")
        return
    print(concat_members(blocks))
    return
# ↓ ここから下は既存の単一クエリ処理（変更しない）
```
注: `fetch_latest_message` / `target_date` の実名は基点スクリプトの既存実装に合わせて結線する（既存ソースが当日1通を取得している関数をそのまま流用）。本文は既存の HTML→テキスト抽出を通った文字列を渡すこと（生 HTML を渡さない）。

- [ ] **Step 3: ライブ Gmail で3ソースを実行確認**

```bash
GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... GMAIL_REFRESH_TOKEN=... \
  python /tmp/fetch_gmail_real.py axios-daily | head -40
```
Expected:
- 先頭に `=== MEMBER: Axios AM | ... ===` 等のマーカーが、当日届いたメンバー分だけ並ぶ。
- スポンサー（`A MESSAGE FROM`）・フッター（`Arlington VA`）・SB宣伝が出力に含まれない。
- 全未着の日は `NO_EMAIL_FOUND`。
`axios-ai` / `axios-frontier` も同様に確認（frontier は水/日以外は NO_EMAIL_FOUND が正常）。

- [ ] **Step 4: lib を同期してコミット**

```bash
cp /tmp/fetch_gmail_real.py scripts/_axios_fetch_lib.py
python -m pytest scripts/test_fetch_axios.py -v   # 既存テストが緑のまま
git add scripts/_axios_fetch_lib.py
git commit -m "feat(axios): 3集約ソース(members構造)をfetch_gmailに追加"
```
Expected: テスト 6 passed。

---

### Task 5: SECRET_FETCH_GMAIL_PY を更新し、ソース単体で smoke

**Files:**
- なし（GitHub Secret 更新 + workflow_dispatch）

**Interfaces:**
- Consumes: Task 4 の `/tmp/fetch_gmail_real.py`
- Produces: 本番 secret に Axios 集約フェッチが入った状態。

- [ ] **Step 1: secret を更新**

```bash
gh secret set SECRET_FETCH_GMAIL_PY -R TH1214/newsletter-dashboard < /tmp/fetch_gmail_real.py
```
Expected: `✓ Set secret SECRET_FETCH_GMAIL_PY`。

- [ ] **Step 2: 既存ソース1本で回帰 smoke**

```bash
gh workflow run daily-translate.yml -R TH1214/newsletter-dashboard -f sources=wsj -f force_overwrite=true
gh run watch -R TH1214/newsletter-dashboard $(gh run list -R TH1214/newsletter-dashboard -L1 --json databaseId -q '.[0].databaseId')
```
Expected: wsj が従来どおり TRANSLATED（再構築した secret が既存を壊していない）。FAILED_FETCH なら再構築漏れ → Task 2 に戻る。

- [ ] **Step 3: Commit なし（secret はリポジトリ外）**

このタスクはコミット対象なし。次タスクへ。

---

### Task 6: translate_prompt.md に Axios 統合ルールを追加

**Files:**
- Modify: `scripts/translate_prompt.md`

**Interfaces:**
- Consumes: フェッチ出力のメンバーマーカー形式（Task 3）。
- Produces: 翻訳器が3slugを「1記事・メンバー件名サブ見出し・継続チャンク本文のみ」で出力するルール。

- [ ] **Step 1: ソース対応表に3行追記**

`【ソース対応表】` ブロック（musha 行の後）に追加:
```
axios-daily → ソース名: Axios Daily, カテゴリ: Axios Daily
axios-ai → ソース名: Axios AI+PE/MA/VC, カテゴリ: Axios AI+PE/MA/VC
axios-frontier → ソース名: Axios Def/CAR/2028, カテゴリ: Axios Def/CAR/2028
```

- [ ] **Step 2: Axios 統合ルールブロックを追記**

`【武者リサーチ 固有ルール】` の後、`【翻訳スタイル】` の前に挿入:
```
【Axios 統合ルール (SOURCE_SLUG: axios-daily / axios-ai / axios-frontier)】
入力は複数の Axios ニュースレターを「=== MEMBER: <メンバー名> | <件名> ===」マーカーで
連結したテキスト。これを1本の統合記事として出力する。

■ 出力構成:
  1. front matter（title は "Axios Daily｜YYYY年M月D日" 等、対応表のソース名を使用）
  2. 「## エグゼクティブサマリー」: そのチャンクに含まれるメンバーの一覧表（#, メンバー名, 一言要約）
  3. 各メンバーを「## <メンバー名>：<件名の日本語訳>」見出し＋本文翻訳
     （マーカー行 "=== MEMBER ... ===" 自体は出力しない。件名を和訳して見出しに使う）

■ Smart Brevity ラベルの和訳（本文中のラベルは訳して残す）:
  Why it matters→なぜ重要か / The big picture→全体像 / Driving the news→ニュースの要点 /
  Between the lines→行間を読む / By the numbers→数字で見る / The bottom line→結論 /
  What they're saying→関係者の声 / Zoom in→詳細 / State of play→現状

■ Pro Rata（axios-ai 内）特例:
  「The BFD」「Venture Capital Deals」「Private Equity Deals」「Public Offerings」
  「Liquidity Events」「It's Personnel」等のディールリストは散文化せず箇条書きのまま和訳。
  企業名・投資家名・ティッカー・金額（$50m 等）・axios.link URL は原文表記のまま転記。

■ ★絶対厳守（gpt-4o-mini が無視しがちなため明示）:
  - 入力に含まれる全 "=== MEMBER ... ===" を1件も省略しない。
  - 万一フェッチ漏れで残った定型文（"A MESSAGE FROM"/"PRESENTED BY"/"Like this comms style"/
    "Was this email forwarded"/"Unsubscribe"/"Arlington VA" を含む行）は出力に1文字も含めない。
  - 分割翻訳の続編チャンクは front matter・タイトル・ESS表を出力せず、メンバー本文のみ出力する
    （CNBC と同一の継続ルール）。
```

- [ ] **Step 3: 構文確認**

```bash
grep -n "axios-daily" scripts/translate_prompt.md
grep -n "絶対厳守" scripts/translate_prompt.md
```
Expected: 対応表とルールブロックの両方にヒット。

- [ ] **Step 4: Commit**

```bash
git add scripts/translate_prompt.md
git commit -m "feat(axios): translate_promptにAxios統合3ソースのルールを追加"
```

---

### Task 7: daily-translate.yml に matrix・timeout・WEEKLY を反映

**Files:**
- Modify: `.github/workflows/daily-translate.yml`

**Interfaces:**
- Consumes: 3 slug、secret 更新（Task 5）。
- Produces: 日次 run が3 Axios ソースを処理する。

- [ ] **Step 1: matrix に3slugを追加**

`matrix.source` リスト末尾（`- maverick` の後）に追加:
```yaml
          - axios-daily
          - axios-ai
          - axios-frontier
```

- [ ] **Step 2: timeout を 60 分へ**

`jobs.translate.timeout-minutes: 40` を `60` に変更。

- [ ] **Step 3: WEEKLY_SOURCES に axios-frontier を追加**

`WEEKLY_SOURCES="buysiders maverick musha"` を
`WEEKLY_SOURCES="buysiders maverick musha axios-frontier"` に変更（frontier の no-email 日を info 扱い）。

- [ ] **Step 4: 構文確認**

```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/daily-translate.yml')); print('YAML OK')"
grep -n "axios-" .github/workflows/daily-translate.yml
grep -n "timeout-minutes: 60" .github/workflows/daily-translate.yml
```
Expected: YAML OK、3slug 表示、timeout 60。

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/daily-translate.yml
git commit -m "feat(axios): daily-translate matrixに3ソース追加・timeout60・frontierをWEEKLY化"
```

---

### Task 8: batch-backfill.yml の ALL_SOURCES に3slug追加

**Files:**
- Modify: `.github/workflows/batch-backfill.yml`

**Interfaces:**
- Produces: backfill で Axios 3ソースを日付指定再生成可能。

- [ ] **Step 1: ALL_SOURCES を特定**

```bash
grep -n "ALL_SOURCES" .github/workflows/batch-backfill.yml
```

- [ ] **Step 2: 3slugを ALL_SOURCES 文字列末尾に追加**

該当行の既存リスト末尾に ` axios-daily axios-ai axios-frontier` を追記（区切りは既存に合わせる。スペース区切りなら半角スペース、カンマなら `,`）。

- [ ] **Step 3: 構文確認**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/batch-backfill.yml')); print('YAML OK')"
grep -n "axios-frontier" .github/workflows/batch-backfill.yml
```
Expected: YAML OK、3slug 表示。

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/batch-backfill.yml
git commit -m "feat(axios): batch-backfill ALL_SOURCESに3ソース追加"
```

---

### Task 9: sections.ts と SectionNav.tsx に3セクション追加

**Files:**
- Modify: `v2-next/lib/sections.ts`
- Modify: `v2-next/components/SectionNav.tsx`

**Interfaces:**
- Produces: Dashboard ナビ/TOP に3タイトルが出る。

- [ ] **Step 1: sections.ts に3エントリ追加**

`SECTIONS` 配列の `nikkei-hack` 行の前（または末尾の適切な位置）に追加:
```typescript
  { slug: 'axios-daily',    label: 'Axios Daily',           eyebrow: 'NEWS · MARKETS · LIFE' },
  { slug: 'axios-ai',       label: 'Axios AI+PE/MA/VC',     eyebrow: 'AI · DEALS · POLICY' },
  { slug: 'axios-frontier', label: 'Axios Def/CAR/2028',    eyebrow: 'DEFENSE · MOBILITY · POLITICS' },
```

- [ ] **Step 2: SectionNav.tsx の SHORT を確認して3件追加**

```bash
grep -n "SHORT" v2-next/components/SectionNav.tsx
```
`SHORT` マップ（slug→短縮ラベル）に追加:
```typescript
  'axios-daily': 'Axios Daily',
  'axios-ai': 'Axios AI/Deals',
  'axios-frontier': 'Axios Def/CAR/2028',
```
注: SHORT が `Record<string,string>` でない実装（配列等）なら既存要素の書式に合わせる。

- [ ] **Step 3: 型チェック / ビルド**

```bash
cd v2-next && npm run lint && npx tsc --noEmit && cd ..
```
Expected: 型エラー無し（`SectionSlug` に3slugが追加され、SHORT の参照と整合）。lint/tsc が無い場合は `npm run build` で代替。

- [ ] **Step 4: Commit**

```bash
git add v2-next/lib/sections.ts v2-next/components/SectionNav.tsx
git commit -m "feat(axios): sections/SectionNavにAxios統合3セクションを追加"
```

---

### Task 10: 3つの content/_index.md を作成

**Files:**
- Create: `content/axios-daily/_index.md`
- Create: `content/axios-ai/_index.md`
- Create: `content/axios-frontier/_index.md`

**Interfaces:**
- Consumes: 既存 `_index.md` の書式（他ソースの content/<slug>/_index.md に倣う）。

- [ ] **Step 1: 既存 _index.md の書式を確認**

```bash
cat content/wsj/_index.md
```
Expected: front matter（title / 説明等）の最小書式を把握。

- [ ] **Step 2: 3ファイルを既存書式で作成**

`content/axios-daily/_index.md`（他2つも同形式で title/説明を差し替え）:
```markdown
---
title: "Axios Daily"
---

Axios の朝刊・夕刊・市場・マクロ・ライフを束ねた日次ダイジェスト（その日届いた分）。
```
- `content/axios-ai/_index.md` → title "Axios AI+PE/MA/VC"、説明「Pro Rata / AI+ / AI+ Government を束ねたAI・ディール・政策ダイジェスト」。
- `content/axios-frontier/_index.md` → title "Axios Def/CAR/2028"、説明「防衛・モビリティ・2028大統領選を束ねた週次ダイジェスト」。
（既存 _index.md に title 以外の必須フィールドがあればそれに合わせる。）

- [ ] **Step 3: Commit**

```bash
git add content/axios-daily/_index.md content/axios-ai/_index.md content/axios-frontier/_index.md
git commit -m "feat(axios): 3統合セクションの_index.mdを作成"
```

---

### Task 11: batch-backfill で実メール E2E 検証＋回帰確認

**Files:**
- なし（workflow 実行と目視検証）

**Interfaces:**
- Consumes: Task 5–10 の全変更。

- [ ] **Step 1: リポジトリ変更を push**

```bash
git push origin HEAD:main
```
注: `content/**`・`v2-next/**` 変更を含むため deploy がトリガーされる。E2E 検証の生成物もこの後 backfill で main に入る。

- [ ] **Step 2: 直近の届いた日付で backfill（skip_existing=false）**

Axios メンバーが揃いやすい日付を選ぶ（frontier は水曜推奨）。
```bash
gh workflow run batch-backfill.yml -R TH1214/newsletter-dashboard \
  -f date_from=2026-06-24 -f date_to=2026-06-24 \
  -f sources=axios-daily,axios-ai,axios-frontier -f skip_existing=false
gh run watch -R TH1214/newsletter-dashboard $(gh run list -R TH1214/newsletter-dashboard -L1 --json databaseId -q '.[0].databaseId')
```
Expected: 3ソースが TRANSLATED（frontier は水曜なら Mobility+Defense を含む）。

- [ ] **Step 3: 生成記事を検証**

```bash
git pull --rebase
for s in axios-daily axios-ai axios-frontier; do
  echo "===== $s ====="; sed -n '1,40p' content/$s/2026-06-24.md
done
```
Expected（チェックリスト）:
- front matter が1つだけ（title が対応表どおり、二重化なし）。
- `## <メンバー名>：<件名和訳>` のサブ見出しが、その日届いたメンバー分だけ並ぶ。
- 本文に `A MESSAGE FROM` / `PRESENTED BY` / `Smart Brevity` / `Arlington VA` / `Unsubscribe` が無い。
- Smart Brevity ラベルが和訳（「なぜ重要か」等）で残っている。
- Pro Rata（axios-ai）はディール箇条書きが保持され、金額・投資家が原文表記。
- 絵文字が無い。

- [ ] **Step 4: hero 画像を確認**

```bash
ls -la static/images/axios-daily/2026-06-24.png static/images/axios-ai/2026-06-24.png static/images/axios-frontier/2026-06-24.png 2>/dev/null
grep -l "hero_image" content/axios-*/2026-06-24.md
```
Expected: 各統合記事に hero 画像1枚＋ front matter に `hero_image`。

- [ ] **Step 5: 既存ソース回帰確認**

```bash
gh run list -R TH1214/newsletter-dashboard --workflow daily-translate.yml -L 3
```
Expected: 直近の日次 run で既存14ソースが従来どおり（FAILED が増えていない）。timeout 60分内に完了。

- [ ] **Step 6: deploy 反映確認**

```bash
gh run list -R TH1214/newsletter-dashboard --workflow deploy.yml -L 2
```
Expected: deploy 成功。`https://th1214.github.io/newsletter-dashboard/` に3タイトルが表示される。

- [ ] **Step 7: 検証結果をメモに記録してコミット**

```bash
# docs/superpowers/notes/2026-06-27-axios-verified-queries.md に E2E 結果を追記
git add docs/superpowers/notes/2026-06-27-axios-verified-queries.md
git commit -m "docs(axios): E2E backfill検証結果を記録" && git push origin HEAD:main
```

---

## Self-Review

**Spec coverage（スペック→タスク対応）:**
- §2.1 対象3slug → Task 4/6/7/8/9/10 全体。
- §3 その日届いた分だけ → Task 4 Step2（全未着で NO_EMAIL_FOUND）/ Task 7 Step3（WEEKLY）。
- §4 記事構造（サブ見出し=件名） → Task 6 Step2。
- §4.1 Pro Rata 特例 → Task 6 Step2 Pro Rata ブロック。
- §5 翻訳・画像 既存流用 → Task 7（既存 translate/hero ステップ温存）/ Task 11 Step4。
- §6 トークン対策（HTML除去/ボイラープレート除去/メンバー境界/継続本文のみ/timeout/レート） → Task 3（除去純関数）/ Task 4（連結）/ Task 6（継続ルール）/ Task 7（timeout60）。
- §7 変更7ファイル → Task 4(SOURCES)/6/7/8/9/10。
- §8 検証（クエリ/backfill/回帰） → Task 1 / Task 11。
- §9 リスク（混線/再構築） → Task 1 Step3 / Task 2。

**Placeholder scan:** 残課題は「実 fetch_gmail.py の関数名（fetch_latest_message / target_date）に結線」のみ。これは secret 実体を見られない制約による明示的な結線指示であり、Task 4 Step2 に注記済み（プレースホルダではなく既存実装名への適合指示）。

**Type consistency:** 純関数名 `strip_axios_boilerplate` / `build_member_block` / `concat_members` は Task 3 定義、Task 4 で使用、一致。slug `axios-daily`/`axios-ai`/`axios-frontier` は全タスクで一貫。カテゴリ名は translate_prompt 対応表（Task 6）と front matter（Task 11 検証）で一致。
