# Bolgheri Daily Brief — Dashboard 仕様書

**最終更新**: 2026-04-21
**バージョン**: v1.1（長文チャンク分割＋429リトライ対応版）
**リポジトリ**: [`TH1214/newsletter-dashboard`](https://github.com/TH1214/newsletter-dashboard)
**公開サイト**: https://th1214.github.io/newsletter-dashboard/

---

## 1. システム概要

英語ニュースレターを毎朝自動取得・日本語翻訳し、Hugo 静的サイトとして GitHub Pages に公開するダッシュボード。コストは完全無料（GitHub Actions の public repo 無料枠 + GitHub Models Free Tier + Gmail API 無料枠）。

### 1.1 アーキテクチャ

```
┌───────────┐    ┌────────────────────────────────────┐    ┌──────────────┐
│   Gmail   │───►│  GitHub Actions (daily 21:00 UTC)   │───►│ GitHub Repo  │
│  (8ソース) │    │  ┌──────────────┐  ┌──────────────┐ │    │  main branch │
└───────────┘    │  │ fetch_gmail  │─►│translate_    │ │    └──────┬───────┘
                 │  │   .py        │  │gemini.py     │ │           │
                 │  │ (OAuth)      │  │(GitHub Models│ │           ▼
                 │  └──────────────┘  │ GPT-4.1)     │ │    ┌──────────────┐
                 │                    └──────────────┘ │    │  Deploy      │
                 │                                      │    │  Workflow    │
                 │  content/<source>/<date>.md commit  │    │  (Hugo)      │
                 └────────────────────────────────────┘    └──────┬───────┘
                                                                  │
                                                                  ▼
                                                          ┌──────────────┐
                                                          │GitHub Pages  │
                                                          │(公開サイト)   │
                                                          └──────────────┘
```

### 1.2 コスト構造（2026年4月時点）

| 項目 | 提供元 | 制限 | 現状消費 |
|---|---|---|---|
| GitHub Actions (public) | GitHub | 無制限 | ≒ 6分/日 |
| GitHub Pages | GitHub | 100GB/月 転送 | ≪1GB |
| GitHub Models API | GitHub | GPT-4.1 free: 10 RPM / 50 req/日 | 8ソース × 平均10チャンク ≒ 80 req（**要注意**） |
| Gmail API | Google | 1 billion quota units/日 | 無視できる量 |
| **月額合計** | | | **¥0** |

### 1.3 設計原則

1. **完全無料**: 外部有料APIに依存しない
2. **疎結合**: 翻訳エンジン（GitHub Models / Gemini / Groq 等）を差し替え可能
3. **冪等性**: 同日再実行しても上書きのみ、副作用なし
4. **観測可能**: 全てのステップが GitHub Actions ログに残る

---

## 2. ディレクトリ構成

```
newsletter-dashboard/
├── SPEC.md                          ← 本書
├── PUBLISH_GUIDE.md                 ← 手動Publish skill運用ガイド
├── config.yaml                      ← Hugo設定（theme / menu / taxonomies）
├── content/                         ← 翻訳済み記事（Hugoがビルド対象）
│   ├── wsj/<YYYY-MM-DD>.md
│   ├── nyt-bn/<YYYY-MM-DD>.md
│   ├── short-squeez/<YYYY-MM-DD>.md
│   ├── skift/<YYYY-MM-DD>.md
│   ├── buysiders/<YYYY-MM-DD>.md
│   ├── nyt-op/<YYYY-MM-DD>.md
│   ├── business-insider/<YYYY-MM-DD>.md
│   └── economist/<YYYY-MM-DD>.md    ← ※ 現在未実装
├── scripts/
│   ├── fetch_gmail.py               ← Gmail OAuth + メール取得
│   ├── translate_gemini.py          ← GitHub Models 翻訳エンジン（本番）
│   ├── translate_claude.py          ← Claude翻訳（レガシー、現在未使用）
│   ├── translate_prompt.md          ← 翻訳プロンプト本体
│   ├── get_gmail_token.py           ← refresh_token 取得用（1回きり）
│   ├── setup_secrets.py             ← GitHub Secrets設定ヘルパー
│   ├── README.md                    ← publish-skillセットアップ手順
│   └── publish-skill/SKILL.md       ← Cowork用publish skill定義
├── .github/workflows/
│   ├── daily-translate.yml          ← 翻訳ジョブ（cron + workflow_dispatch）
│   └── deploy.yml                   ← Hugo build + Pages deploy（push時）
└── themes/PaperMod/                 ← Hugoテーマ（submodule）
```

---

## 3. コンポーネント仕様

### 3.1 翻訳ジョブ (`.github/workflows/daily-translate.yml`)

| 項目 | 値 |
|---|---|
| トリガー | `cron: '0 21 * * *'` (毎日 21:00 UTC = 翌朝 6:00 JST) + `workflow_dispatch` |
| タイムゾーン | `TZ=Asia/Tokyo` |
| タイムアウト | 30分 |
| パーミッション | `contents: write`, `models: read` |
| 実行環境 | `ubuntu-latest`, Python 3.12 |
| 並列度 | 逐次（ソースごとに for ループ） |

**必要な GitHub Secrets**:

| Secret名 | 用途 |
|---|---|
| `GMAIL_CLIENT_ID` | Gmail OAuth クライアントID |
| `GMAIL_CLIENT_SECRET` | Gmail OAuth シークレット |
| `GMAIL_REFRESH_TOKEN` | 長期認証トークン |
| `GITHUB_TOKEN` | GitHub Models 認証（workflow が自動発行） |
| `GROQ_API_KEY` | （未使用、レガシー） |

**環境変数（workflow内設定）**:

| 変数 | 値 | 用途 |
|---|---|---|
| `TRANSLATION_MODEL` | `openai/gpt-4.1` | 翻訳モデル |
| `GITHUB_MODELS_ENDPOINT` | `https://models.github.ai/inference` | GitHub Models API |

**処理フロー**:

1. `ALL_SOURCES` = `wsj nyt-bn short-squeez skift buysiders nyt-op business-insider`（7ソース、economist未登録）
2. 各ソースについて:
   a. `fetch_gmail.py <source>` でメール取得
   b. `NO_EMAIL_FOUND` ならスキップ
   c. `translate_gemini.py <source> <date>` で翻訳
   d. 先頭行が `---`（front matter）であることを検証し `content/<source>/<date>.md` へ保存
3. 変更があれば `github-actions[bot]` が自動commit & push

**終了ステータスカウント**:
- `TRANSLATED` = 成功件数
- `SKIPPED` = メール未受信
- `FAILED` = 取得/翻訳失敗

### 3.2 デプロイジョブ (`.github/workflows/deploy.yml`)

| 項目 | 値 |
|---|---|
| トリガー | `push to main` + `workflow_dispatch` |
| Hugo バージョン | 0.160.1 (extended) |
| ビルドコマンド | `hugo --gc --minify --baseURL <pages_url>/` |
| デプロイ先 | `github-pages` environment |
| 平均実行時間 | 約30秒 |

### 3.3 翻訳エンジン (`scripts/translate_gemini.py`)

**現行バージョン**: v1.1（2026-04-21, merge commit `d5ad2ca`）

**主要定数**:

| 定数 | 既定値 | 目的 |
|---|---|---|
| `DEFAULT_MODEL` | `openai/gpt-4o-mini` | フォールバック用（workflow では gpt-4.1 を注入） |
| `DEFAULT_CHUNK_CHAR_LIMIT` | `6500` | 1チャンクの最大文字数 |
| `DEFAULT_CHUNK_SLEEP_SEC` | `7` | チャンク間スリープ（10 RPM 対応） |
| `DEFAULT_MAX_RETRIES` | `3` | HTTP 429 時のリトライ上限 |
| `BACKOFF_DELAYS` | `[15, 30, 60]` | 指数バックオフ秒数 |

**チャンク分割アルゴリズム**（長文対応）:

1. 段落境界（空行）で優先分割
2. 1段落が `CHUNK_CHAR_LIMIT` を超える場合は行単位で分割
3. 1行が超える場合は文字数で強制分割
4. 各チャンクを順次翻訳 → 結合
5. front matter は先頭チャンクから抽出し、全体で1回のみ出力（重複排除）

**レート制限対策**:
- 各チャンク呼び出し後に `CHUNK_SLEEP_SEC` 秒待機
- HTTP 429 受信時は `BACKOFF_DELAYS` の値だけ待機してリトライ
- `MAX_RETRIES` 超過で `sys.exit(1)`

**入出力**:

```bash
python scripts/translate_gemini.py <source> <date> < email.txt > translated.md
```

出力は Hugo front matter + 本文の Markdown。先頭は必ず `---`。

### 3.4 Gmail 取得エンジン (`scripts/fetch_gmail.py`)

**認証方式**: OAuth 2.0 refresh_token による自動再発行（unattended）

**検索ウィンドウ**: 過去36時間（`after:<epoch>` クエリで絞り込み、最大1件取得）

**本文デコード**: `text/plain` → `text/html` → ネスト multipart の順で再帰探索

**出力フォーマット**:

```
EMAIL_SUBJECT: <subject>
EMAIL_DATE: <RFC 2822 date>
EMAIL_SOURCE: <source label>
EMAIL_BODY_START
<body>
EMAIL_BODY_END
```

### 3.5 翻訳プロンプト (`scripts/translate_prompt.md`)

翻訳のスタイルガイド・出力フォーマット・front matter テンプレートを定義。翻訳エンジンはこれを読み込んで `{email_content}` にメール本文を差し込む。

---

## 4. ソース一覧

| # | Source slug | Label | Gmail 検索クエリ | サイトパス | 登録状態 |
|---|---|---|---|---|---|
| 1 | `wsj` | WSJ The 10-Point | `from:wsj.com subject:"The 10-Point"` | `/wsj/` | ✅ |
| 2 | `nyt-bn` | NYT Breaking News | `from:nytimes.com subject:"Breaking News"` | `/nyt-bn/` | ✅ |
| 3 | `short-squeez` | Short Squeez OWS | `from:shortsqueez.com "Overheard on Wall Street"` | `/short-squeez/` | ✅ |
| 4 | `skift` | Skift The Daily | `from:skift.com subject:"Skift Daily"` | `/skift/` | ✅ |
| 5 | `buysiders` | Buysiders Deal Report | `from:buysiders.com` | `/buysiders/` | ✅ |
| 6 | `nyt-op` | NYT Opinion Today | `from:nytimes.com subject:"Opinion Today"` | `/nyt-op/` | ✅ |
| 7 | `business-insider` | Business Insider | `from:businessinsider.com subject:"Today"` | `/business-insider/` | ✅ |
| 8 | `economist` | The Economist Espresso | — | `/economist/` | ⚠️ 未実装 (menu のみ) |

> **Economist の現状**: Hugo メニューには表示されているが、`fetch_gmail.py` の SOURCES dict および `daily-translate.yml` の ALL_SOURCES に登録されていないため、自動取得・翻訳は行われない。**Phase 2.5 で対応予定**。

---

## 5. 運用フロー

### 5.1 自動モード（本番）

| 時刻 (JST) | 処理 | 想定所要時間 |
|---|---|---|
| 06:00 | `daily-translate.yml` が cron 起動 | — |
| 06:00〜06:06 | 7ソース逐次処理（平均40秒/ソース） | 5〜7分 |
| 06:07 | bot が `content/` を commit & push | 数秒 |
| 06:07 | `deploy.yml` 自動起動 | — |
| 06:08 | Hugo build & Pages deploy 完了 | 30秒〜1分 |
| 06:08 | 読者がサイトで新記事を閲覧可能 | — |

### 5.2 手動モード（workflow_dispatch）

```bash
# 全ソース
gh workflow run daily-translate.yml

# 特定ソースのみ
gh workflow run daily-translate.yml -f sources="nyt-bn,nyt-op"

# 実行状況監視
gh run watch <run-id>
```

### 5.3 手動Publish モード（Cowork Publish skill）

翻訳スキル（WSJ/BN/OWS等）が Cowork チャットにレポートを出力した場合、ユーザーが `P` と入力すると `publish-to-bolgheri` スキルが起動し、該当 Markdown を `content/<source>/<date>.md` に手動保存＆commit する。詳細は `PUBLISH_GUIDE.md` を参照。

> この経路は**自動cronとは独立**。自動cronが成功していれば不要だが、特定日の補完や緊急追加に利用する。

---

## 6. 監視・トラブルシュート

### 6.1 ログの見方

```bash
# 最新の翻訳ジョブ一覧
gh run list --workflow=daily-translate.yml --limit 5

# 特定ランのサマリー
gh run view <run-id>

# サマリー＋詳細ログから主要イベントを抽出
gh run view <run-id> --log | grep -E "📊 Summary|chunk count|HTTP [0-9]|Translated|sleeping|Translation failed"
```

### 6.2 典型的失敗パターン

| 症状 | 原因 | 復旧手順 |
|---|---|---|
| `HTTP 413: Request body too large` | 入力がモデルの token 上限超過 | **既に対策済**（v1.1 チャンク分割） |
| `HTTP 429: Too many requests` | GitHub Models の RPM/日次制限超過 | **既に対策済**（v1.1 sleep+backoff）。日次制限に達した場合は翌日まで待機 |
| `NO_EMAIL_FOUND` | ニュースレター配信なし or Gmail 検索クエリ不一致 | Gmail側の受信確認／クエリ修正（`fetch_gmail.py` の SOURCES） |
| `Token refresh failed: 400` | `GMAIL_REFRESH_TOKEN` 失効 | `scripts/get_gmail_token.py` で再取得→GitHub Secrets 更新 |
| `Output missing front matter` | 翻訳結果の先頭が `---` でない | プロンプトを `translate_prompt.md` で調整 |
| Hugo build エラー | front matter YAML構文不正 | 該当 `content/<source>/<date>.md` の YAMLを検証・修正 |

### 6.3 ロールバック

```bash
# 直前の commit を取り消す（未push）
git reset --hard HEAD~1

# リモートの commit を取り消す（既push・非常時のみ）
git revert <bad-commit-sha>
git push
```

---

## 7. 既知の課題と今後のロードマップ

### 7.1 既知の課題

| 優先度 | 項目 | 影響 | 備考 |
|---|---|---|---|
| 🔴 HIGH | Economist 未実装 | メニュークリックで404 | `fetch_gmail.py` + `daily-translate.yml` に追加必要 |
| 🟡 MED | GPT-4.1 日次50req制限 | 長文日に後半ソースが429で失敗する可能性 | 合計チャンク数を監視、超過時は model をチャンクごとに分散検討 |
| 🟡 MED | Node.js 20 deprecation | 2026/09/16に runner から削除 | `actions/checkout@v4`, `actions/setup-python@v5` を Node 24対応版に更新 |
| 🟢 LOW | `translate_claude.py` 未使用 | ファイル残存 | 削除 or legacy ディレクトリへ移動 |
| 🟢 LOW | `GROQ_API_KEY` Secret 未使用 | リソース無駄 | Secret削除 |

### 7.2 ロードマップ

| Phase | 内容 | 状態 | 完了予定 |
|---|---|---|---|
| Phase 1 | GitHub Models 翻訳エンジン移行 | ✅ 完了 | 2026-04-15 |
| Phase 2 | 長文チャンク分割＋429リトライ対応 | ✅ 完了 | 2026-04-21 |
| Phase 2.5 | Economist ソース追加 | 🕒 未着手 | 2026-04-28予定 |
| Phase 3 | Nano Banana (Gemini 2.5 Flash Image) 記事イラスト自動生成 | 🕒 未着手 | 2026-05 |
| Phase 4 | ダッシュボードUI強化（サマリーカード、タグクラウド） | 🕒 構想中 | 2026-Q3 |
| Phase 5 | 多言語対応（英→日に加え日→英） | 🕒 構想中 | 未定 |

### 7.3 Phase 3 設計メモ（参考）

- **API**: Gemini 2.5 Flash Image (Google AI Studio 無料枠)
- **生成タイミング**: 翻訳完了直後に `translate_gemini.py` 内もしくは別ステップで1記事あたり1枚
- **プロンプト**: front matter の `summary` を元に 16:9 横長イラストを生成
- **保存先**: `static/images/<source>/<date>.webp`
- **front matter**: `cover: { image: "/images/<source>/<date>.webp" }` を追記
- **注意**: Gemini API は別途 `GEMINI_API_KEY` が必要、レート制限調査必須

---

## 付録A: 改訂履歴

| 日付 | バージョン | 変更内容 | 担当 |
|---|---|---|---|
| 2026-04-15 | v1.0 | 初期構築（Claude翻訳→GitHub Models 移行） | 初期構築 |
| 2026-04-21 | v1.1 | 長文チャンク分割、429 exponential backoff、SPEC.md 初版作成 | 現行 |

## 付録B: 関連ドキュメント

- [`PUBLISH_GUIDE.md`](./PUBLISH_GUIDE.md) — 手動Publish skillの運用手順
- [`scripts/README.md`](./scripts/README.md) — publish-skillセットアップ
- [`scripts/translate_prompt.md`](./scripts/translate_prompt.md) — 翻訳プロンプト本体
- [GitHub Models Docs](https://docs.github.com/en/github-models) — GitHub Models 公式
- [Hugo PaperMod Docs](https://github.com/adityatelange/hugo-PaperMod/wiki) — テーマ設定リファレンス
