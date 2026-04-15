---
name: publish-to-bolgheri
description: 直前のチャットに出力された翻訳レポート（WSJ / NYT BN / Short Squeez / Skift / Buysiders / NYT OP / BI のいずれか）を Bolgheri Daily Brief サイト（~/newsletter-dashboard/）にMarkdownファイルとして保存＆git commitする。「P」「pub」「publish」「Publish」「サイトに公開」「サイト反映」「反映」「保存して」などの入力で必ずトリガーする。「P」という1文字の入力のみでも必ずトリガーする。
---

# Bolgheri Daily Brief — 自動反映スキル

直前のチャットに出力された翻訳レポートを、Bolgheri Daily Brief サイトに自動保存＆コミットする専用スキル。

公開サイト: https://th1214.github.io/newsletter-dashboard/
リポジトリパス: `~/newsletter-dashboard/`

## 前提

- ユーザーは直前に何らかの翻訳スキル（`W` / `BN` / `OWS` / `SK` / `buy` / `OP` / `BI` 等）を実行し、チャットにMarkdownレポートが表示されている状態
- そのレポート全文を流用して、サイトの `content/` 配下に保存する

## ワークフロー

### ステップ1: 直前の翻訳レポートを特定

直前のアシスタント出力（現在の会話履歴の直近）から、以下のいずれに該当するかを判定する：

| 判定キーワード | SOURCE slug | categoryLabel | SourceLabel | titleFormat |
|--------------|-------------|---------------|-------------|-------------|
| WSJ The 10-Point, 10-Point, The 10-Point | `wsj` | `WSJ` | `WSJ The 10-Point` | `WSJ The 10-Point｜YYYY年MM月DD日` |
| NYT Breaking News, Breaking News, BN | `nyt-bn` | `NYT-BN` | `NYT Breaking News` | `NYT Breaking News｜YYYY年MM月DD日` |
| Short Squeez, Overheard on Wall Street, OWS | `short-squeez` | `Short Squeez` | `Short Squeez OWS` | `Short Squeez OWS｜YYYY年MM月DD日` |
| Skift The Daily, Skift | `skift` | `Skift` | `Skift The Daily` | `Skift The Daily｜YYYY年MM月DD日` |
| Buysiders, M&A Deal Report | `buysiders` | `Buysiders` | `Buysiders Deal Report` | `Buysiders Deal Report｜YYYY年MM月DD日` |
| NYT Opinion Today, Opinion Today | `nyt-op` | `NYT-Opinion` | `NYT Opinion Today` | `NYT Opinion Today｜YYYY年MM月DD日` |
| Business Insider, BI | `business-insider` | `Business Insider` | `Business Insider` | `Business Insider｜YYYY年MM月DD日` |

判定が曖昧な場合はユーザーに確認する。

### ステップ2: フォルダのマウント確認

Cowork VMから `~/newsletter-dashboard/`（VMパス: `/sessions/<session>/mnt/newsletter-dashboard/`）にアクセスできない場合、以下のMCPツールでマウントする:

- `mcp__cowork__request_cowork_directory` with path: `/Users/hashiramototetsuya/newsletter-dashboard`

### ステップ3: Markdownファイルとして保存

保存先: `<mount-path>/content/<SOURCE>/<YYYY-MM-DD>.md`

- `<YYYY-MM-DD>` は翻訳レポートの配信日（レポート冒頭やサブタイトルから抽出）
- 同日・同スキルの既存ファイルがあれば上書き

ファイル内容（Hugo front matter + 本文）:

```markdown
---
title: "<titleFormat を実際の日付で展開>"
date: YYYY-MM-DD
categories: ["<categoryLabel>"]
tags: [レポート本文から主要トピックを3〜5個抽出、日本語で統一]
original_url: "<レポート本文に含まれる元URL or 該当ニュースレターの公式URL>"
summary: "<TOPテーマを1行で要約（60字以内、TOPカードに表示される）>"
---

## 出典
[<SourceLabel> 原文](<original_url>)

---

<直前のチャットに出力された翻訳レポート全文をそのまま貼り付け。見出し・表・引用・絵文字なども保持>
```

**front matter のルール:**
- `date` は ISO 8601 の `YYYY-MM-DD` 形式
- `tags` は3〜5個。日本語で統一（例: `["米国経済", "金利動向", "FRB"]`）
- `summary` は60字以内、機関投資家が興味を持つフック
- `original_url` はレポート中に明示されていればそれを、なければ空文字 `""`
- 文字列内のダブルクォートは `\"` でエスケープ

### ステップ4: git commit（sandboxで実行）

```bash
cd <mount-path>
git add content/<SOURCE>/<YYYY-MM-DD>.md
git commit -m "Add <SourceLabel> <YYYY-MM-DD>"
```

### ステップ5: ユーザーへの通知

チャットに以下のブロックを表示:

```markdown
## 💾 Bolgheri Daily Brief に保存完了

**保存ファイル**: `content/<SOURCE>/<YYYY-MM-DD>.md`
**コミット**: `Add <SourceLabel> <YYYY-MM-DD>`

### 🚀 公開手順

1. **GitHub Desktop** を開く
2. 画面上部の **「Push origin」** をクリック
3. 1〜3分後、以下のURLで公開されます:

👉 https://th1214.github.io/newsletter-dashboard/<SOURCE>/
👉 https://th1214.github.io/newsletter-dashboard/<SOURCE>/<YYYY-MM-DD>/ （個別記事）
```

## エラーハンドリング

- **直前にレポートが見当たらない場合**: 「直前のチャットに翻訳レポートが見当たりません。先に翻訳スキル（`W`、`BN`、`OWS`等）を実行してください。」と返答して終了
- **マウント失敗**: ユーザーに `~/newsletter-dashboard` フォルダが存在するか確認を促す
- **git commit 失敗（変更なし）**: 既に同日同スキルで保存済みの可能性。ファイル内容の diff を表示して上書き確認

## 注意事項

- **絶対にpushしない**: sandboxから `git push` は credentials 不足で失敗するので実行しない。必ず GitHub Desktop 経由
- **既存ファイルの上書き**: 同日・同スキルで再実行した場合は最新版に置き換える（diff表示なしでOK）
- **複数ソース混在**: 直前のチャットに複数の翻訳レポートが混ざっている場合は、最も新しい（下にある）ものを採用
