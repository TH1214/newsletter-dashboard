#!/bin/bash
# Bolgheri Pipeline Workload Identity Federation Setup Script
#
# OIDC_MIGRATION_GUIDE.md の Step 2.1〜2.6 を自動化する。
# ユーザーは gcloud CLI 認証済みで実行する必要がある。
#
# Usage: ./scripts/setup_wif.sh <PROJECT_ID>
#   例:   ./scripts/setup_wif.sh bolgheri-pipeline

set -euo pipefail

PROJECT_ID="${1:?Usage: $0 PROJECT_ID}"
REPO="${REPO:-TH1214/newsletter-dashboard}"
SA_NAME="${SA_NAME:-bolgheri-pipeline-sa}"
POOL="${POOL:-github-actions-pool}"
PROVIDER="${PROVIDER:-github-actions-provider}"

echo "🔧 Configuring Workload Identity Federation"
echo "  Project: $PROJECT_ID"
echo "  Repo:    $REPO"
echo "  SA:      $SA_NAME"
echo ""

gcloud config set project "$PROJECT_ID"

echo "📦 Enabling required APIs..."
gcloud services enable \
  gmail.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com

echo "👤 Creating Service Account (idempotent)..."
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="Bolgheri Pipeline GitHub Actions" \
  --description="Used by GitHub Actions to access Gmail API via WIF" \
  || echo "  (already exists, skipping)"

echo "🏊 Creating Workload Identity Pool (idempotent)..."
gcloud iam workload-identity-pools create "$POOL" \
  --location=global \
  --display-name="GitHub Actions Pool" \
  || echo "  (already exists, skipping)"

echo "🔌 Creating OIDC Provider (idempotent)..."
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global \
  --workload-identity-pool="$POOL" \
  --display-name="GitHub Actions OIDC Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository == '$REPO'" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  || echo "  (already exists, skipping)"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"

echo "🔐 Binding IAM (workloadIdentityUser)..."
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$PRINCIPAL"

echo ""
echo "================================================"
echo "✅ Setup complete!"
echo "================================================"
echo ""
echo "Add the following to GitHub repository secrets"
echo "(Settings → Secrets and variables → Actions):"
echo ""
echo "  GCP_PROJECT_ID = $PROJECT_ID"
echo "  GCP_SERVICE_ACCOUNT = $SA_EMAIL"
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER = $WIF_PROVIDER"
echo ""
echo "Then update daily-translate.yml / batch-backfill.yml per OIDC_MIGRATION_GUIDE.md Section 4."
