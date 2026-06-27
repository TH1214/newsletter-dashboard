# Axios 統合ニュースレター（3タイトル）Dashboard 追加 — 設計

- 日付: 2026-06-27
- 対象リポジトリ: TH1214/newsletter-dashboard（本番 = v2-next / Next.js / GitHub Actions）
- ステータス: 設計承認済み → 実装プラン作成へ

## 1. 背景・目的

Axios のニュースレターを購読開始した結果、直近30日で約100通／17種類が届いている。
送信元（From）で種類が完全に分類でき、定期編集ニュースレターは全種が同一の
「Smart Brevity®」骨格（`1 big thing:` / 太字ラベル / 文字数表示 / スポンサー枠 /
シェア行）を共有している。

このうち**定期編集ニュースレター12種**を、Dashboard 上で **3つの統合タイトル**に
集約して掲載する。各統合記事は「メールの配信タイトル（件名）」をサブ見出しにして、
その中身を内側に入れる構造とする。翻訳・画像生成は既存ニュースと同一の仕組みに乗せる。

速報（Alerts / Scoop / Exclusive）とマーケ/運用（The Axios Show / Axios HQ / Feedback）
は中身が外部リンク誘導のみのため**対象外**。

## 2. スコープ

### 2.1 対象（IN）

| slug | Dashboard 表示名 | eyebrow | メンバー（=サブ見出し / From） |
|---|---|---|---|
| `axios-daily` | **Axios Daily** | NEWS · MARKETS · LIFE | AM(mike@) / PM(mike@) / Finish Line(mike@) / Closer(closer@) / Markets(markets@) / Macro(macro@) |
| `axios-ai` | **Axios AI+PE/MA/VC** | AI · DEALS · POLICY | Pro Rata(dan@) / AI+(ai.plus@) / AI+ Government(ai.plus.gov@) |
| `axios-frontier` | **Axios Def/CAR/2028** | DEFENSE · MOBILITY · POLITICS | Mobility(mobility@) / Defense(defense@) / 2028(2028@) |

### 2.2 対象外（OUT）

- Axios Alerts / Axios Scoop / Axios Exclusive（速報・1記事＋リンクのみ）
- The Axios Show（番組宣伝）/ Axios HQ（B2Bイベント）/ Feedback Survey（運用メール）
- 既存14ソースの挙動変更（回帰させない）

## 3. 集約の単位 — 「その日届いた分だけ」（確定）

- **1日1記事**。`content/<slug>/<date>.md` を1ファイル生成。
- その日（対象 JST 日付）に届いたメンバーだけをサブ見出しで並べる。未着メンバーは省略。
- 全メンバー未着の日は `SKIPPED`（既存の週次ソースと同じ無害扱い）。
  - `axios-frontier` は実質 水・日のみ稼働 → no-email 日を info 扱い（ログノイズ削減）。
  - `axios-daily` / `axios-ai` は日次稼働。
- ローリング蓄積・再翻訳は**行わない**（実装単純・冪等性維持）。
- Dashboard には**この3タイトルのみ**を表示する（12個の個別記事は出さない）。

## 4. 出力記事の構造

```
---
title: "Axios Daily｜2026年6月27日"
date: 2026-06-27
categories: ["Axios Daily"]
tags: ["タグ1", "タグ2", "タグ3"]
original_url: "https://www.axios.com/newsletters"
summary: "その日の届いたメンバー横断トップ3テーマを60字以内で要約"
---

## エグゼクティブサマリー
（その日届いたメンバーの一覧表：#, メンバー名, 配信タイトル, 一言要約）

## Axios AM：<件名の和訳>
（AM本文を翻訳。Smart Brevity ラベルを和訳：
 Why it matters→なぜ重要か / The big picture→全体像 / The bottom line→結論 等）

## Axios PM：<件名の和訳>
...

（届いたメンバーのみ。順序は AM→PM→Finish Line→Closer→Markets→Macro 等の固定順）
```

### 4.1 メンバー別の特例

- **Pro Rata**：ディール箇条書き構造（`企業名 — 金額 — 主導投資家「led, joined by…」`）を
  散文に展開せず、**箇条書きのまま**和訳する。VC/PE/IPO/M&A/人事のサブセクションを保持。
  投資家名・企業名・ティッカー・金額（$50m 等）は原文表記のまま転記。
- **Finish Line**：ライフ/自己啓発系。報道トーンに変換しない。
- **AI+ Government の "The Output"**：政策週間まとめの絵文字ミニ見出しは見出し和訳のみで簡潔に。

## 5. 翻訳・画像 = 既存と同一の仕組み

- **翻訳**：既存 `scripts/translate_gemini.py`（`openai/gpt-4o-mini` / `CHUNK_CHAR_LIMIT=24000`）。
  **CNBC と同じ「1ソース＝多コンテンツをチャンク分割翻訳」方式**を踏襲（実績あり）。
- **画像**：既存 `scripts/generate_hero_image.py`（front matter `summary` → Gemini/GitHub Models で
  Unsplash キーワード生成 → Unsplash 画像 → `hero_image` 注入）。
  **統合記事1本につき hero 画像1枚**（1日最大3枚）。
- 追加は宣言的。既存の選択的処理（HN/PERE/Maverick）と同じく translate_prompt.md に
  ルールブロックを足す方式。

## 6. トークン超過の事前対策（必須要件）

増える翻訳量で token / レート制限エラーを出さないため、
**「1回の LLM 呼び出しがメール1通分（≈1,500語）を超えない」**を担保する。

1. **取得時に HTML→テキスト＋定型ブロック除去**：Axios メールは ~90k 字の HTML だが実本文は
   ~1,500語。既存 fetch と同様にテキスト抽出し、さらに以下を除去してメンバー1通 ≈ 10k 字に圧縮：
   - スポンサー枠（`A MESSAGE FROM …` / `PRESENTED BY …`）
   - Smart Brevity® 宣伝枠（`Like this comms style and format?`）
   - フッター（住所 / unsubscribe / social / `Was this email forwarded to you?`）
   - マストヘッド定型・`View in browser`
2. **メンバー境界マーカーで連結**：`=== MEMBER: Axios AM | <件名> ===` を各メンバー本文の
   先頭に挿入 → 24k チャンク分割がほぼメンバー単位の境界で切れる。
3. **継続チャンクは本文のみ出力**（front matter・ESS表を重複させない）。CNBC で実証済みの
   処理を流用（translate_prompt.md に明記）。
4. **モデル・レート据え置き**：`gpt-4o-mini` 150 req/日。3グループ追加でも +約7 req/日
   （現状 ~25 → ~32）で上限内。
5. **matrix timeout 40分→60分**に引き上げ（ソース 14→17 本化の余裕確保）。
6. プロンプトで定型ブロック除去を指示し、出力トークンも削減。

### 6.1 設計上の不変条件

- 1つの統合ソースのフェッチ結果は「テキスト本文のみ・ボイラープレート除去済み・メンバー
  マーカー付き」であること。生 HTML を翻訳器に流さない。
- チャンク分割の継続出力で front matter を二重に出さないこと（壊れた md を防ぐ）。

## 7. 変更するファイル（宣言的7点 + α）

1. **`SECRET_FETCH_GMAIL_PY`**（gh secret set）: 3グループの `SOURCES` エントリを追加。
   各グループは複数メンバーのクエリを持つため、`members` 配列構造へ拡張：
   ```
   "axios-daily": {
     "members": [
       {"label": "Axios AM",          "query": "from:mike@axios.com subject:\"Axios AM\""},
       {"label": "Axios PM",          "query": "from:mike@axios.com subject:\"Axios PM\""},
       {"label": "Axios Finish Line", "query": "from:mike@axios.com subject:\"Finish Line\""},
       {"label": "Axios Closer",      "query": "from:closer@axios.com"},
       {"label": "Axios Markets",     "query": "from:markets@axios.com"},
       {"label": "Axios Macro",       "query": "from:macro@axios.com"}
     ]
   }
   ```
   - fetch_gmail.py を `members` 対応に拡張：各メンバーの当日最新1通を取得 → HTML除去＋
     ボイラープレート除去 → マーカー付きで連結して1本のテキストとして出力。
   - 1通も無ければ `NO_EMAIL_FOUND`。1通以上あれば連結出力。
   - **クエリは Gmail MCP で実検証してから set**（PERE 2026-06-13 事故の教訓：
     アポストロフィ句や曖昧な subject は取りこぼす）。AM/PM/Finish Line は同一 From のため
     subject で分離が必要。
2. **`.github/workflows/daily-translate.yml`**: matrix に `axios-daily` / `axios-ai` /
   `axios-frontier` を追加。`timeout-minutes: 40→60`。`WEEKLY_SOURCES` に `axios-frontier`
   を追加（no-email 日の info 扱い）。
3. **`.github/workflows/batch-backfill.yml`**: `ALL_SOURCES` に3slug追加。
4. **`scripts/translate_prompt.md`**: Axios 統合ルールブロックを追加（§4・§4.1・§6の規則、
   ソース対応表に3slug、Smart Brevity ラベル和訳表、継続チャンク規則、Pro Rata 分岐）。
   - **重要**：gpt-4.1/4o-mini は「除外」指示を無視しがち。除去対象は「絶対厳守」見出し＋
     具体的なマーカー文字列（`A MESSAGE FROM` 等）で明示する。
5. **`v2-next/lib/sections.ts`**: 3エントリ追加（slug / label / eyebrow）。
6. **`v2-next/components/SectionNav.tsx`**: `SHORT` に短縮ラベル追加
   （例: `Axios Daily` / `Axios AI/Deals` / `Axios Def/CAR/2028`）。
7. **`content/axios-daily/_index.md` / `content/axios-ai/_index.md` /
   `content/axios-frontier/_index.md`**: セクション index を3つ作成。

## 8. 検証

- **クエリ検証**：追加前に Gmail MCP で各メンバークエリを実行し、当日の正しい1通が
  取れることを確認（特に AM/PM/Finish Line の subject 分離）。
- **batch-backfill 実メール検証**：追加後、`skip_existing=false` で過去数日を再生成し、
  - 3記事が生成される
  - サブ見出しが「メンバー名：配信タイトル和訳」になっている
  - 定型ブロック（スポンサー/フッター/SB宣伝）が消えている
  - front matter が二重化していない（チャンク分割の継続が正しい）
  - hero 画像が1記事1枚付く
  を確認。
- **回帰**：既存14ソースの当日翻訳が従来どおり成功すること（timeout 内、レート内）。

## 9. リスクと緩和

| リスク | 緩和 |
|---|---|
| AM/PM/Finish Line が同一 From で混線 | subject 句でクエリ分離 + Gmail MCP 実検証 |
| 統合により1ソースが大きくなりトークン/出力上限超過 | §6：HTML除去＋ボイラープレート除去＋メンバー境界チャンク＋継続本文のみ |
| ソース17本化で matrix が40分超過 | timeout 60分へ |
| gpt-4o-mini が除外指示を無視し定型文が残る | 「絶対厳守」＋具体マーカー明示、backfill 実検証 |
| `axios-frontier` が大半の日で空 | WEEKLY 扱いで info 化、全空日は SKIPPED |
| SECRET_FETCH_GMAIL_PY のマスター紛失 | git 履歴 `a44ced5~1:scripts/fetch_gmail.py` から復元して拡張・再 set |

## 10. 非目標（YAGNI）

- 速報・マーケ/運用メールの取り込み
- 個別12記事の Dashboard 表示／カテゴリ別ナビ UI 新設
- ローリング週次集約・記事の事後更新
- Axios 専用の新規翻訳器・新規画像生成器（既存を流用）
