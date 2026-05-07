# OIDC + Google Workload Identity Federation Migration Guide

P2 #9: 長期 OAuth refresh_token を **Workload Identity Federation (WIF)** に置換し、GitHub
Actions が短命 (1時間) のトークンで Google Cloud / Gmail にアクセスする構成への移行ガイド。

**現状リスク**: `GMAIL_REFRESH_TOKEN` が GitHub Secrets に長期保存されており、漏洩時の被害が大きい。
**移行後**: 短命 access_token を on-demand で取得、長期トークンは存在しなくなる。

---

## 1. 前提

- ユーザー側で **Google Cloud プロジェクト** が必要 (無料枠で OK)
- GitHub repo: `TH1214/newsletter-dashboard` (本リポジトリ)
- 設定後の GitHub Actions runner は OIDC token を提示して GCP IAM から短命 token を取得する

---

## 2. GCP 側設定 (ユーザー作業: 約 15 分)

### Step 2.1: GCP プロジェクトの確認

```bash
# gcloud CLI が必要 (https://cloud.google.com/sdk/docs/install)
gcloud auth login
gcloud config set project YOUR_PROJECT_ID  # 例: bolgheri-pipeline
```

### Step 2.2: 必要 API の有効化

```bash
gcloud services enable \
  gmail.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com
```

### Step 2.3: Service Account 作成

```bash
gcloud iam service-accounts create bolgheri-pipeline-sa \
  --display-name="Bolgheri Pipeline GitHub Actions" \
  --description="Used by GitHub Actions to access Gmail API"

# Gmail readonly scope を Service Account に付与する代わりに、
# Domain-wide delegation を設定する (ユーザーレベルアクセス用)
# OR
# Service Account 自身の Gmail に届くように設定する (推奨: 専用 Gmail アカウント)
```

### Step 2.4: Workload Identity Pool 作成

```bash
gcloud iam workload-identity-pools create github-actions-pool \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Pool 内に GitHub OIDC Provider を作成
gcloud iam workload-identity-pools providers create-oidc github-actions-provider \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository == 'TH1214/newsletter-dashboard'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

### Step 2.5: Service Account に WIF アクセス権を付与

```bash
PROJECT_ID="YOUR_PROJECT_ID"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
REPO="TH1214/newsletter-dashboard"

gcloud iam service-accounts add-iam-policy-binding \
  bolgheri-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/$REPO"
```

### Step 2.6: 設定値の取得 (GitHub Secrets に登録する値)

```bash
echo "GCP_PROJECT_ID=$PROJECT_ID"
echo "GCP_SERVICE_ACCOUNT=bolgheri-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider"
```

---

## 3. GitHub 側設定 (ユーザー作業: 約 5 分)

### Step 3.1: Repository Secrets の登録

GitHub repo Settings → Secrets and variables → Actions に追加:

| Secret 名 | 値 |
|---|---|
| `GCP_PROJECT_ID` | Step 2.6 で取得 |
| `GCP_SERVICE_ACCOUNT` | Step 2.6 で取得 |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Step 2.6 で取得 |

旧 secrets (`GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN`) は移行完了後に削除する。

---

## 4. Workflow 側変更 (本ガイドで完成形を提示)

### Step 4.1: `daily-translate.yml` の auth 部分を OIDC 化

```yaml
permissions:
  contents: write
  models: read
  issues: write
  id-token: write   # ← ★ OIDC token 取得のため必須

jobs:
  translate:
    # ... 既存設定 ...
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      # ─── 旧: secrets.GMAIL_REFRESH_TOKEN を渡す ───
      # ─── 新: WIF で短命 token を取得 ───
      - name: Authenticate to Google Cloud (Workload Identity)
        id: gcp-auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}
          create_credentials_file: true

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Fetch and translate
        env:
          # 既存の Groq / Gemini / GitHub Models は維持
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          # ★ 旧 GMAIL_* secrets 削除、代わりに ADC 使用
          GOOGLE_APPLICATION_CREDENTIALS: ${{ steps.gcp-auth.outputs.credentials_file_path }}
        run: |
          python scripts/fetch_gmail.py ...
```

### Step 4.2: `scripts/fetch_gmail.py` を ADC 対応化

旧 implementation (`get_access_token` 関数) は OAuth2 refresh_token フロー。
新 implementation は **Application Default Credentials (ADC)** + Service Account impersonation:

```python
# scripts/fetch_gmail.py の get_access_token を以下に置換:

import google.auth
from google.auth.transport.requests import Request

def get_access_token():
    """ADC + Workload Identity 経由で短命 access_token を取得。

    GOOGLE_APPLICATION_CREDENTIALS env が google-github-actions/auth@v2 で
    自動設定されているため、google.auth.default() で透過的に取得可能。
    """
    credentials, project = google.auth.default(
        scopes=['https://www.googleapis.com/auth/gmail.readonly']
    )
    if not credentials.valid:
        credentials.refresh(Request())
    return credentials.token
```

### Step 4.3: 依存ライブラリ追加

`requirements.txt` (新規作成 or 更新):

```
google-auth>=2.30.0
google-auth-oauthlib>=1.2.0  # 既存維持
```

`daily-translate.yml` / `batch-backfill.yml` のセットアップステップに追加:

```yaml
- name: Install Python dependencies
  run: pip install -r requirements.txt
```

---

## 5. 移行手順 (本番移行: 段階的、ロールバック可能)

### Phase A: 並行運用検証 (1 週間)

1. GCP 設定 (Step 2) 完了
2. GitHub Secrets 追加 (Step 3) 完了
3. **新 workflow を別ファイル** として作成: `.github/workflows/daily-translate-oidc.yml`
4. 1 週間、2 つの workflow を並列実行 (時間ずらして cron 設定)
5. 出力比較: 同じ記事内容が生成されるか確認

### Phase B: 本番切替 (5 分)

1. `daily-translate.yml` を新実装で上書き (PR + merge)
2. 旧 secrets (GMAIL_*) を repository から削除
3. 旧 OAuth credentials を Google Cloud Console で revoke

### Phase C: クリーンアップ (1 日後)

1. `daily-translate-oidc.yml` 削除 (本流に統合)
2. 設定変更を CLAUDE.md / ARCHITECTURE.md に反映
3. RUNBOOK.md の "OAuth refresh_token 失効" 項を WIF 対応版に更新

---

## 6. ロールバック手順

問題発生時は以下で即座に旧実装に戻せる:

1. GitHub Secrets で旧 `GMAIL_*` を再登録 (削除前の値を保管しておく)
2. `daily-translate.yml` を 1 つ前の commit に revert
3. 5 分以内に旧構成で運用再開

---

## 7. メリット / デメリット

| 観点 | 旧 (refresh_token) | 新 (WIF) |
|---|---|---|
| Token 寿命 | 半年〜永久 (revoke まで) | **1 時間** |
| 漏洩時被害 | 全期間 Gmail 読取可能 | 1時間以内のみ |
| ローテーション | 手動 (年 1 回必須) | **自動** (毎回新規) |
| 設定工数 | 簡単 (15分) | やや複雑 (45分初期設定) |
| 監査ログ | 限定的 | **GCP Audit Logs に全記録** |
| GCP プロジェクト必要 | 不要 | **必要** (無料枠で OK) |

---

## 8. 実施判断

**実施推奨タイミング**:
- セキュリティ監査が必要になった (B2B 配信前など)
- refresh_token を疑わしい状況で扱った場合 (流出懸念)
- GCP プロジェクトを既に運用している場合 (移行コスト低)

**現時点での推奨**: **個人運用継続中ならオプション**。
v4.0 (B2B 検討) と同タイミングで実施するのが効率的。

---

## 9. 補助スクリプト (移行作業の自動化)

`scripts/setup_wif.sh` (新規作成、ユーザーが gcloud CLI で実行):

```bash
#!/bin/bash
# Bolgheri Pipeline WIF Setup Script
set -euo pipefail

PROJECT_ID="${1:?Usage: $0 PROJECT_ID}"
REPO="TH1214/newsletter-dashboard"
SA_NAME="bolgheri-pipeline-sa"
POOL="github-actions-pool"
PROVIDER="github-actions-provider"

gcloud config set project "$PROJECT_ID"

# 全ステップ自動実行
gcloud services enable gmail.googleapis.com iamcredentials.googleapis.com sts.googleapis.com
gcloud iam service-accounts create "$SA_NAME" --display-name="Bolgheri Pipeline GitHub Actions" || true
gcloud iam workload-identity-pools create "$POOL" --location=global --display-name="GitHub Actions Pool" || true
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global --workload-identity-pool="$POOL" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == '$REPO'" \
  --issuer-uri="https://token.actions.githubusercontent.com" || true

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
gcloud iam service-accounts add-iam-policy-binding \
  "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"

echo ""
echo "=========================================="
echo "✅ Setup complete. Add these to GitHub Secrets:"
echo "=========================================="
echo "GCP_PROJECT_ID=$PROJECT_ID"
echo "GCP_SERVICE_ACCOUNT=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
```

使い方:
```bash
chmod +x scripts/setup_wif.sh
./scripts/setup_wif.sh bolgheri-pipeline
```

---

**結論**: 本ガイドに沿えば、ユーザー作業 ~30分 で長期 token を完全排除できる。
v4.0 移行と同時並行で実施するのが最も効率的。
