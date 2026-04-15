# Bolgheri Daily Brief — 翻訳スキル自動反映ガイド

各翻訳スキル（WSJ・NYT BN・Short Squeez・Skift・Buysiders・NYT OP・BI）が生成したMarkdownレポートを、本サイトへ自動反映するための共通パターン。

## 前提

- 保存先リポジトリ: `~/newsletter-dashboard/`（ユーザーのMacホーム直下）
- Cowork VM 上の対応パス: `/sessions/<session-id>/mnt/newsletter-dashboard/`
- サイトURL: https://th1214.github.io/newsletter-dashboard/
- push はユーザーが GitHub Desktop の「Push origin」をクリックして実行（sandboxから直接pushしない）

## ソース対応表

| スキル | SOURCE slug | categoryLabel | サイトパス |
|--------|-------------|---------------|-----------|
| WSJ The 10-Point | `wsj` | `WSJ` | /wsj/ |
| NYT Breaking News | `nyt-bn` | `NYT-BN` | /nyt-bn/ |
| Short Squeez OWS | `short-squeez` | `Short Squeez` | /short-squeez/ |
| Skift The Daily | `skift` | `Skift` | /skift/ |
| Buysiders Deal Report | `buysiders` | `Buysiders` | /buysiders/ |
| NYT Opinion Today | `nyt-op` | `NYT-Opinion` | /nyt-op/ |
| Business Insider | `business-insider` | `Business Insider` | /business-insider/ |

## 共通ワークフロー

翻訳スキルがチャットにレポートを出力した **後** に、以下を必ず追加実行する。

### ステップ0: フォルダのマウント確認

VMパス `/sessions/<session>/mnt/newsletter-dashboard/` にアクセスできない場合、`mcp__cowork__request_cowork_directory` で以下をマウントする:

```
/Users/hashiramototetsuya/newsletter-dashboard
```

### ステップ1: Markdownファイルとして保存

保存先:

```
<mount-path>/content/<SOURCE>/<YYYY-MM-DD>.md
```

ファイル内容（Hugo front matter + 本文）:

```markdown
---
title: "<スキル固有のタイトル>｜YYYY年MM月DD日"
date: YYYY-MM-DD
categories: ["<categoryLabel>"]
tags: [今日のレポートの主要トピックから3〜5個選定]
original_url: "<Gmailから取得した元URL or 代表URL>"
summary: "<トップ3テーマを1行で要約（60字以内）>"
---

## 出典
[<source名> 原文](<original_url>)

---

<チャット本文で出力したMarkdownレポート全文をそのまま貼り付け>
```

**front matter のルール:**
- `date` はISO 8601の `YYYY-MM-DD` 形式（配信日）
- `tags` は3〜5個。日本語で統一（例: `["米国経済", "金利動向", "FRB"]`）
- `summary` はTOPカードに表示されるので60字以内で魅力的に
- `original_url` はGmailに含まれるWebバージョンURL or ニュースレター配信URL

### ステップ2: git commit（sandboxで実行）

```bash
cd <mount-path>
git add content/<SOURCE>/<YYYY-MM-DD>.md
git commit -m "Add <SourceLabel> <YYYY-MM-DD>"
```

### ステップ3: ユーザーへの通知

チャット末尾に以下のブロックを追記する:

```markdown
---

💾 **Bolgheri Daily Brief サイトに保存済**: `content/<SOURCE>/<YYYY-MM-DD>.md`
🚀 **公開手順**: GitHub Desktop で **「Push origin」** をクリック → 1〜3分後に以下で公開
👉 https://th1214.github.io/newsletter-dashboard/<SOURCE>/
```

## 注意事項

- **同日に同スキルを複数回実行した場合**: 同名ファイルを上書き（最新版を採用）
- **push失敗時**: sandboxから`git push`は credentials がないため失敗する。必ずGitHub Desktop経由で行う
- **Hugo frontmatter構文エラー**: YAMLバリデートしてから保存（特殊文字のエスケープに注意）
