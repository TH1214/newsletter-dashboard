# 設計: Claude翻訳メールをDashboardに転載する（Email-Relay）

> **⚠️ このv1(Email-Relay)は [2026-07-22-git-relay-to-dashboard-v2.md](./2026-07-22-git-relay-to-dashboard-v2.md) に置換されました。**
> ChatGPTレビューを受け、「メールHTMLを再パース」する方式を廃し、Mac側で生成済みの
> 正規MarkdownをGit経由で受け渡す方式(v2)に格上げ。以下v1は経緯記録として残置。

- 作成: 2026-07-22
- ステータス: **SUPERSEDED by v2 / 実装は未実施**
- 対象: メール配信されている8ソースの、Dashboard掲載を「gpt-4o-mini再翻訳」から「Claude日本語版メールの転載」に切り替える設計

---

## 1. 背景・目的

同じ記事について、翻訳エンジンが2系統ある:

| 系統 | 実体 | モデル | 品質 |
|---|---|---|---|
| **メール** | `newsletter-automation`（Mac launchd → `claude` CLI → send_email） | **Claude** | 高 |
| **Dashboard** | GitHub Actions `daily-translate.yml` | **gpt-4o-mini**（`GEMINI_API_KEY`未登録のため） | 低（DealBook骨格重複・捏造リスク） |

→ **メール側は既にClaude品質の日本語版を作っている**。8ソースに限り、Dashboardで再翻訳せず**メール内容をそのまま転載**すれば、無料のままDashboard品質をClaude級に引き上げられる。

### 対象8ソース（＝メール配信あり）

| Dashboard slug | メールTASK | 件名ラベル | 配信cadence | 配信時刻(JST) |
|---|---|---|---|---|
| nyt-bn | BN | 【NYT Breaking News】 | 毎日・**複数版** | 07/10/13/16/19/22 |
| nyt-op | OP | 【NYT Opinion Today】 | 毎日・**複数版** | 07/12/18 |
| wsj | WSJ | 【WSJ The 10-Point】 | 毎日 | 17:30 |
| economist | EC | 【The Economist】 | 毎日 | 19:00 |
| business-insider | BI | 【BI Today】 | 毎日 | 22:00 |
| skift | SK | 【Skift Daily】 | 毎日 | 09:00 |
| short-squeez | SS | 【Short Squeez】 | 毎日 | 08:00 |
| buysiders | SIDE | 【Buysiders】 | 週次/月次（到着時のみ） | 08:30 |

※ Dashboard専用（メール無し・**本設計の対象外**）: DealBook / Hospitality Net / HI / CNBC(停止済) / PERE / Maverick / 武者 / Axios×3 / My CLIP。これらは現行のまま。

---

## 2. 現行フロー（差し替えポイント）

`daily-translate.yml` の matrix ジョブ「Fetch and translate (single source)」:

```
1. 冪等チェック  content/<src>/<date>.md が有れば skip
2. fetch_gmail.py <src>        → /tmp/email_<src>.txt   (原文ニュースレターを取得)
3. NO_EMAIL_FOUND → skip
4. translate_gemini.py <src> <date> < email → md         (gpt-4o-mini 翻訳)   ← ここを差し替える
5. 完全性検証 → content/<src>/<date>.md へ書き出し
6. generate_hero_image.py                                 (hero画像・non-blocking)
```

**Email-Relayでは 2〜4 を「Claude日本語版メールを取得して整形」に置換**。5・6（書き出し・hero・冪等・完全性検証）はそのまま再利用する。

---

## 3. 提案アーキテクチャ

### 3.1 新規コンポーネント（2つ）

1. **`scripts/fetch_relay.py <src> [<date>]`**
   - Gmail検索: `from:hashiramoto@mellowps.com subject:(件名ラベル) 日本語版`（＋日付/lookback条件）
   - 該当メールのHTML本文を取り出して stdout。無ければ `NO_RELAY_FOUND`。
   - 複数版があるソース（BN/OP）は**最新版を1通選ぶ**（→ §4.2）。
2. **`scripts/email_to_markdown.py <src> <date>`**（stdin=HTML本文）
   - メールchrome除去（署名・フッター・"Thanks for reading"・unsubscribe・トラッキング）
   - HTML→Markdown変換（html2text 等）
   - front matter生成（→ §4.3）
   - stdout = Dashboard用 `.md`（front matter＋本文）

### 3.2 ジョブ分岐（daily-translate.yml）

```
RELAY_SOURCES = "nyt-bn nyt-op wsj economist business-insider skift short-squeez buysiders"

if SOURCE in RELAY_SOURCES:
    fetch_relay.py SOURCE > /tmp/relay.html
    if NO_RELAY_FOUND:
        → フォールバック（§4.4）: 従来の fetch_gmail + translate_gemini (gpt-4o-mini)
    else:
        email_to_markdown.py SOURCE TODAY < /tmp/relay.html > /tmp/translated.md
else:
    （従来どおり fetch_gmail + translate_gemini）
# 以降 5.完全性検証→書き出し / 6.hero は共通
```

- `RELAY_SOURCES` は**環境変数/ワークフロー変数**にして、ソース単位でON/OFFできるようにする（カナリア展開・即ロールバック用）。

---

## 4. 論点と決定事項（★ユーザー判断が要る箇所）

### 4.1 ★タイミング結合（最重要）

Dashboardは **06:00 JST** 実行。だが当日分のClaudeメール生成は:

| 06:00に**間に合う**（前日夜に生成済） | 06:00に**間に合わない**（当日朝以降に生成） |
|---|---|
| WSJ 17:30 / EC 19:00 / BI 22:00 / BN・OPの前夜版 | SS 08:00 / SIDE 08:30 / SK 09:00 / BN 07:00 / OP 07:00（当日版） |

→ **06:00のままだと SK/SS/SIDE と BN/OPの当日版は転載できず**フォールバック(gpt-4o-mini)に落ちる。対策3案:

- **案A（推奨）: イベント駆動**。メール送信直後に `newsletter-automation` が該当ソースの relay を GitHub `workflow_dispatch` で叩く（`gh workflow run daily-translate.yml -f sources=<src>`）。→ 各Claudeメールが「送られた瞬間に自分をDashboardへ転載」。タイミング問題が原理的に消える。Mac→GitHub の1コール追加のみ。
- **案B: latest駆動＋実行時刻後ろ倒し/2回目追加**。relayは「そのソースの最新日本語版」を件名日付で拾う。Dashboardのcronを **10:00 JST 付近**へ移す or 06:00に加えて relay専用の2回目(例:10:00, 23:00)を追加。BN/OPは実行時点の最新版を採用。実装は小さいが「最新の1版」に固定される。
- **案C: 現状06:00維持＋間に合わない分はフォールバック**。SK/SS/SIDE/BN/OPは当面gpt-4o-mgまま、WSJ/EC/BIのみClaude化。段階導入としては安全だが効果限定。

> 推奨: **案A（イベント駆動）**。次点は案B。案Cはカナリア初期のみ。

### 4.2 ★複数版ソース（BN/OP）の版選択

Dashboardは「1ソース＝1日1ファイル」。BN(6版/日)・OP(3版/日)をどう1本にするか:

- **B-1（推奨）: その日の最新版を1本**（例: BNなら22:00版、OPなら18:00版）。1日の総まとめに近い。
- B-2: 07:00版（朝の初版）に固定。
- B-3: 版ごとに別記事化（`nikkei-hack`のように1日複数md）。情報量最大だが、Dashboard/検索/Interestの粒度が変わる中規模改修。

> 推奨: **B-1（最新版1本）**。将来B-3に拡張余地あり。

### 4.3 front matter マッピング

Dashboard mdに必要な項目の埋め方:

| 項目 | 埋め方 |
|---|---|
| `title` | `"{ソース表示名}｜{YYYY年MM月DD日}"`（現行規約どおり・slug+dateから決定的生成） |
| `date` | TODAY（イベント駆動なら件名日付） |
| `summary` | メール本文の先頭リード文/見出しを抽出（無ければ空）。**創作しない** |
| `tags` | 当面空でも可（将来: 本文から抽出）。既存記事と揃える |
| `hero_image` | **現行の `generate_hero_image.py` を継続**（mdから生成）。メール由来の画像は使わない |
| `original_url` | メールに原文URLがあれば転記、無ければ空（**捏造しない**） |

### 4.4 ★フォールバック方針

relayメールが見つからない時（メール未送/失敗/件名変更）:

- **推奨: 従来の gpt-4o-mini 翻訳にフォールバック**（＝Dashboardが今より悪化しない・回帰なし）。
- 代替: スキップ（その日その源の記事なし）。

### 4.5 その他エッジ

- **Buysiders**: 週次/月次。到着日のみメールあり → 既存の "weekly cadence" skip 分岐を relay 側にも適用。
- **件名ラベルのドリフト**: メール側でラベルが変わると relay が拾えない → マッピング表を単一定義（`RELAY_MAP`）にして両系統で共有 or ドキュメント固定。ミスマッチ時はフォールバックで安全側。
- **HTML整形の残骸**: 変換ノイズは変換ルール＋既存の完全性検証（front matter有り＋500字以上）で弾く。
- **重複/二重翻訳の停止**: relay採用ソースは translate_gemini を**呼ばない**（無料枠req節約にも寄与）。

---

## 5. 段階導入（**入れ替えは各段階で承認制・即ロールバック可**）

- **Phase 0（本書）**: 設計のみ。パイプライン不変。
- **Phase 1**: `fetch_relay.py` + `email_to_markdown.py` を新規作成し、**オフラインでshadow**（過去メールで変換→現行md品質と目視比較）。パイプライン未接続。
- **Phase 2**: `RELAY_SOURCES` 分岐を daily-translate に追加。**canary 1ソース**（例: economist）だけON。数日観測。
- **Phase 3**: タイミング方式（§4.1）を実装（推奨=案A イベント駆動）。
- **Phase 4**: 残りソースへ拡大。BN/OPの版選択（§4.2）を確定。
- **ロールバック**: `RELAY_SOURCES` から外す → 即 gpt-4o-mini に戻る。

各Phaseは独立PRで、[[feedback-pr-granularity-phase]] に従い範囲を1画面で提案してから着手。

---

## 6. 効果・リスクまとめ

**効果**: 8ソースのDashboard翻訳がClaude級に（DealBook/BI等の捏造・骨格重複が解消）。gpt-4o-miniのreq削減。無料維持。
**主リスク**: ①06:00タイミング（§4.1で解消）②複数版の粒度（§4.2）③HTML→md変換品質（Phase1 shadowで検証）。いずれもフォールバックで回帰ゼロ。

## 7. 未決事項（次アクションで確認したい）
1. タイミング方式（§4.1）: 案A/B/C どれで進めるか
2. BN/OP版選択（§4.2）: 最新1本 / 初版 / 複数記事化
3. フォールバック（§4.4）: gpt-4o-mini継続 / スキップ
4. 対象順（canary）: 最初にClaude化する1ソース
