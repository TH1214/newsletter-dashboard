# Bolgheri Daily Brief — Operations Runbook

このドキュメントは Pipeline 障害発生時の標準対応手順 (incident response) を定義する。
P3 #12 として 2026-05-07 incident の経験を踏まえて作成。

最終更新: 2026-05-07

---

## 1. 障害検知のシグナル

| シグナル | 重大度 | 検知経路 |
|---|---|---|
| 朝 7時 にサイトが昨日のまま | 🔴 Critical | サイト目視 / `/status/` ページ |
| GitHub Issue が `auto-generated` ラベル付きで作成 | 🔴 Critical | Email / GitHub 通知 |
| `Daily Newsletter Translation` workflow が **failure** | 🟡 Warning | GitHub Actions の通知 |
| `Daily Newsletter Translation` が **success** だが配信 0 件 | 🔴 Critical | `/status/` ページの "7-Day Delivery Rate" |
| 特定ソースの "Last Delivery" が 7日以上前 | 🟡 Warning | `/status/` ページ |

**重要**: workflow が success ステータス ≠ 業務的成功。サイレント失敗の検出には `/status/` ページが最も確実。

## 2. 初動対応 (5分以内)

### 2-1. 影響範囲の特定

```bash
# サイト最新コミットを確認
gh repo view TH1214/newsletter-dashboard --json defaultBranchRef
git log origin/main --oneline -10

# 当日の content/ 追加状況
git ls-tree -r origin/main --name-only | grep "$(date +%Y-%m-%d)"

# Workflow 状況
gh run list --workflow=daily-translate.yml --limit 5
gh run list --workflow=batch-backfill.yml --limit 5
```

### 2-2. ログ確認

```bash
# 最新 daily-translate run のログを取得
gh run view --log $(gh run list --workflow=daily-translate.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

エラーパターン早見表:

| ログ文字列 | 原因 | 対処 → §3 |
|---|---|---|
| `Gemini API HTTP 503` | Gemini 一時障害 | 3-A |
| `Gemini API HTTP 429` | Rate limit (1500 RPD超過) | 3-B |
| `NO_EMAIL_FOUND` 全件 | Gmail 認証/検索クエリ問題 | 3-C |
| `Token refresh failed` | OAuth refresh_token 失効 | 3-D |
| `KeyError: 'parts'` | Gemini レスポンス異常 | 3-E |

## 3. 障害類型別の対処

### 3-A. Gemini API 一時障害 (HTTP 503)

**症状**: 1〜複数ソースが `[gemini] HTTP 503 high demand` で失敗

**対処**:
1. **フォールバック確認**: 2026-05-07 fix で Gemini → Groq → GitHub Models 自動フォールバック有効
   ログに `[fallback] gemini 失敗; 次の優先度 groq へフォールバック` があれば自動復旧済
2. **全バックエンド失敗時** (GROQ_API_KEY 未設定など):
   - 1〜2 時間待機して Gemini 復旧を待つ
   - GitHub Actions UI から **Daily Newsletter Translation** を手動 `Run workflow`
3. **検証**: https://status.cloud.google.com/ で Vertex AI ステータス確認

### 3-B. Rate Limit (HTTP 429)

**症状**: `[gemini] HTTP 429 rate-limited; backing off`

**対処**:
- 既存の exponential backoff で自動回復することが多い
- 連発する場合: chunk_sleep_sec を増やす (現行 7s → 15s) を `daily-translate.yml` で再設定
- 月内 1500 RPD 制限超過の可能性: Gemini Cloud Console でクォータ確認

### 3-C. NO_EMAIL_FOUND が全件で発生

**症状**: 9ソース中 9件すべてが `no email for X on YYYY-MM-DD`

**対処**:
1. **Gmail 認証確認**:
   ```bash
   # ローカルで手動 fetch を試す (Mac で開発環境がある場合)
   python scripts/fetch_gmail.py wsj
   ```
2. **検索クエリ確認**: `scripts/fetch_gmail.py` の SOURCES dict
3. **Gmail 受信箱を直接確認**: アーカイブ含む (`in:anywhere "from:wsj.com"`)

### 3-D. OAuth refresh_token 失効

**症状**: `[auth] Token refresh failed: 400 invalid_grant`

**対処**:
1. ローカルで `python scripts/get_gmail_token.py` を実行 (新 refresh_token 取得)
2. GitHub repo Settings → Secrets → `GMAIL_REFRESH_TOKEN` を更新

### 3-E. Gemini レスポンス異常 (KeyError 等)

**症状**: 翻訳途中で例外。v2.1 で safe `.get()` チェーン化済だが、新たな構造変化の可能性

**対処**:
1. `scripts/translate_gemini.py` の Gemini レスポンスパース部分を最新ドキュメントと比較
2. 問題ソースを `Daily Newsletter Translation` の `sources` 入力で個別実行して切り分け

## 4. 復旧手順

### 4-A. 当日分の手動再実行

GitHub Actions UI:
1. **Daily Newsletter Translation** → `Run workflow`
2. デフォルト (sources=all, date_override=空) のまま実行
3. デフォルトの 36 時間ウィンドウが前日 UTC 着メールも捕捉する

### 4-B. 過去日のバックフィル

GitHub Actions UI:
1. **Batch Backfill Translations** → `Run workflow`
2. Start date: 取り逃がし開始日 (YYYY-MM-DD)
3. End date: 取り逃がし終了日 (空欄なら昨日)
4. Sources: `all` または特定ソースのカンマ区切り
5. Skip existing: `true` (推奨、重複処理防止)

**注意**: 2026-05-07 fix 後、`fetch_gmail.py` の date_override モードは `[target -12h, target +27h]` ウィンドウ。前日 UTC 朝着の米国系ニュースレターも確実に捕捉。

### 4-C. Deploy が起動しないケース

**症状**: content commit はあるが本番サイトが古いまま

**対処**:
1. 通常は `workflow_run` trigger (2026-05-07 fix) で自動 deploy
2. 失敗時は **Deploy Bolgheri v2 (Next.js) to GitHub Pages** → `Run workflow` を手動実行

## 5. ポストモーテム必須事項

障害後は以下を CLAUDE.md の `## 過去の重大失敗` に追記:

1. **発生日時 + 影響範囲** (例: 9ソース中 8件失敗)
2. **検知方法** (ユーザー目視 / 自動 issue / status page)
3. **根本原因** (引数を伴う具体的な仕組み)
4. **対処と所要時間**
5. **再発防止策** (コード修正 / 監視追加 / runbook 改訂)

## 6. 連絡先・参考

- リポジトリ: https://github.com/TH1214/newsletter-dashboard
- 本番URL: https://th1214.github.io/newsletter-dashboard/
- ステータスページ: https://th1214.github.io/newsletter-dashboard/status/
- Gemini Status: https://status.cloud.google.com/
- 仕様書: `Bolgheri_Daily_Brief_仕様書_v3.2_*.docx` (最新)
