# Bolgheri Daily Brief — Claude Working Memory

このファイルは Claude セッションが本リポジトリで作業する際に最初に読むべき記憶。
最終更新: 2026-05-06

---

## プロジェクト概要

- **本番URL**: https://th1214.github.io/newsletter-dashboard/
- **リポジトリ**: TH1214/newsletter-dashboard
- **オーナー**: hashiramoto@mellowps.com
- **構成**: Hugo (legacy) + Next.js 14 (v2-next/, 本番) のハイブリッド
- **コンテンツソース**: 9媒体 (nyt-bn / wsj / dealbook / economist / business-insider / skift / buysiders / short-squeez / nyt-op)
- **配信**: 毎朝06:00 JST に GitHub Actions が自動取得→編集→デプロイ
- **最新仕様書**: `Bolgheri_Daily_Brief_仕様書_v3.1_2026-05-06.docx` (巻頭にChange Log)

## Critical Terminology Rules (法的配慮)

著作権法27/28条リスクを意識し、本サイト全域で「翻訳」を想起させる用語は使用しない。

| 旧用語 (NG) | 新用語 (使用) | 適用範囲 |
|---|---|---|
| 全文翻訳 / 完全翻訳 | **詳細解説** | 記事内見出し全般 |
| 翻訳本文 | **詳細解説本文** | テンプレート / レンダリング呼称 |
| 日本語翻訳 (アーカイブ) | **日本語版** (アーカイブ) | meta description |
| 日本語翻訳ダッシュボード | **日本語版キュレーションダッシュボード** | meta description |
| Translate / Translated | **Curate / Curated** | 英語タグライン |
| 翻訳し (動詞) | **編集し** | UI 文言 |

**例外（保持してよい技術用語）**:
- `scripts/translate_*.py` のdocstring・関数名: 機能名として技術的に正確
- §16 法的リスク評価メモ内の「翻訳権」「翻訳行為」: 法律用語として必要
- 記事本文の引用文中の比喩用法（例「数字を行動に翻訳する」）: 一般用語

## 検証プロトコル (用語リネーム時の必須手順)

過去に「コミットメッセージで完了済み」と書かれていながら120ファイルが未修正だった事故が発生した。
リネーム作業では必ず以下を実行する:

1. **作業前**: `git grep -c "対象文字列"` でリポジトリ全体の出現数を取得・記録
2. **修正対象の特定**: `git grep -l "対象文字列"` で全ファイル列挙してから着手
3. **作業後ゲート**: `git grep -l "対象文字列"` が **0件** を返すまで完了とみなさない
4. **本番反映後**: GitHub Actions deploy 完了後、Chrome から本番URLを fetch して `body.includes("対象文字列") === false` を全主要ページで確認

**禁則**: 他コミットのメッセージ（例: "rename across 127 files"）を信じて検証を省略してはならない。コミットメッセージは目安、実ファイル grep が真実。

## 本リポジトリ特有の状況

- **ブランチ運用**: `main` 直接push (PR運用なし)。GitHub Actions auto-commits も同ブランチに混在
- **divergence 注意**: ローカルとリモートで並行作業が発生しがち。push前に必ず `git fetch origin` → `git log origin/main..HEAD` / `git log HEAD..origin/main` で双方向確認
- **divergence 解決方針 (確立済)**: リモートが細粒度で進んでいる場合は **A案: `git reset --hard origin/main` → 必要なローカル独自コミットだけ cherry-pick** が最も安全
- **サンドボックス制約**: Claude Cowork のサンドボックスは GitHub 認証情報を持たないため、push は user のローカルMacから手動実行が必要
- **Build output**: `v2-next/out/` と `v2-next/.next/` は gitignore済み (チェック対象外)
- **Hugo public/**: 同様に gitignore済み

## ディレクトリ構成 (要点)

```
newsletter-dashboard/
├── content/<source>/<YYYY-MM-DD>.md   ← 記事の真実の源 (9 sources)
├── layouts/                            ← Hugo legacy templates (一部本番使用)
├── v2-next/                            ← Next.js 14 本番フロントエンド
│   ├── app/                            (App Router)
│   ├── components/
│   └── out/                            (build output, gitignore)
├── scripts/
│   ├── fetch_gmail.py                  (Gmail OAuth + メール取得)
│   ├── translate_gemini.py             (Gemini 2.5-flash 編集エンジン)
│   ├── translate_prompt.md             (編集スタイル定義)
│   └── publish-skill/SKILL.md          (Cowork publish スキル)
├── .github/workflows/
│   ├── daily-translate.yml             (cron: 21:00 UTC = 06:00 JST)
│   └── deploy.yml                      (push to main → Pages deploy)
└── Bolgheri_Daily_Brief_仕様書_v*.docx  (バージョン別仕様書)
```

## ユーザーコミュニケーションの好み

- 言語: 日本語 (専門用語は英語可)
- 進め方: **Step by Step、勝手に進めない、確認を取りながら**
- 数値表示: 金額=百万円単位、面積=㎡、利回り=%
- 出力品質: McKinsey/BCG/Bain クラス、C-level プレゼン耐性
- 視覚化: グラフ・表を多用 (専門は不動産・不動産金融・投資ファンド組成)

## 過去の重大失敗 (再発防止のため記録)

**2026-05-06 の事案**: ユーザーから10回以上「全文翻訳が直っていない」と指摘されながら毎回部分修正で済ませてしまった。

**根本原因**:
1. 直前のコミット f4a2471 のメッセージ "rename across 127 files" を鵜呑みにし、`git grep` で再検証しなかった
2. ユーザー指摘箇所 (`layouts/wsj/single.html`) のみを直し、`content/` 配下の実コンテンツ120ファイルを網羅的に検証しなかった
3. 「ユーザーの目に何が映るか」を起点に検証していなかった

**最終的な解決**: `git grep -l "全文翻訳"` で120ファイル発見 → 一括置換788箇所 → 本番Chrome検証で194記事すべて0件確認。

**教訓**: 「ユーザーから繰り返し同じ指摘が来る」 = 「自分の検証範囲が狭い」のシグナル。指摘箇所のスコープを拡張すべし。

## 残課題 (v3.2 以降)

v3.1 公開時点の Pending Items:
- 内部スキル文書 10件 (`scripts/publish-skill/SKILL.md`, `scripts/README.md`)
- 内部実装 docstring 18件 (`scripts/translate_*.py`)
- §16法的リスク評価メモ 推奨対応 (a)(b)(c) → v4.0 検討課題
