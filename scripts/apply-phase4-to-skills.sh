#!/bin/bash
# Bolgheri Daily Brief - Phase 4 セクションを各翻訳スキルに追加するスクリプト
# 使用方法: bash scripts/apply-phase4-to-skills.sh
# 実行環境: ユーザーのMacローカル（~/.claude/skills/ に書き込み権限がある場所）

set -e

SKILLS_DIR="$HOME/.claude/skills"
MARKER="# 🌐 Bolgheri Daily Brief サイトへの自動反映"

if [ ! -d "$SKILLS_DIR" ]; then
  echo "❌ エラー: $SKILLS_DIR が見つかりません"
  exit 1
fi

echo "=== Bolgheri Daily Brief Phase 4 適用開始 ==="
echo "対象ディレクトリ: $SKILLS_DIR"
echo ""

# 各スキルの設定: "skill-folder|SLUG|categoryLabel|SourceLabel|titleFormat|sampleTags"
SKILLS=(
  "wsj-newsletter-report|wsj|WSJ|WSJ The 10-Point|WSJ The 10-Point｜YYYY年MM月DD日|米国経済, 金利動向, 地政学"
  "daily-nyt-braking-news-report|nyt-bn|NYT-BN|NYT Breaking News|NYT Breaking News｜YYYY年MM月DD日|速報, 国際, 米国政治"
  "short-squeez-ows-report|short-squeez|Short Squeez|Short Squeez OWS|Short Squeez OWS｜YYYY年MM月DD日|ウォールストリート, M&A, 市場動向"
  "skift-daily-report|skift|Skift|Skift The Daily|Skift The Daily｜YYYY年MM月DD日|ホスピタリティ, 航空, 旅行業界"
  "buysiders-monthly-deal-report|buysiders|Buysiders|Buysiders Deal Report|Buysiders Deal Report｜YYYY年MM月DD日|M&A, LBO, PE"
  "nyt-opinion-today-report|nyt-op|NYT-Opinion|NYT Opinion Today|NYT Opinion Today｜YYYY年MM月DD日|論説, 政治, 社会"
  "business-insider-report|business-insider|Business Insider|Business Insider|Business Insider｜YYYY年MM月DD日|テック, ビジネス, 市場"
)

applied=0
skipped=0

for entry in "${SKILLS[@]}"; do
  IFS='|' read -r folder slug catLabel srcLabel titleFmt sampleTags <<< "$entry"
  skill_file="$SKILLS_DIR/$folder/SKILL.md"

  if [ ! -f "$skill_file" ]; then
    echo "⏭  スキップ: $folder (SKILL.md なし)"
    continue
  fi

  if grep -q "$MARKER" "$skill_file"; then
    echo "✓ 既適用: $folder"
    skipped=$((skipped + 1))
    continue
  fi

  # バックアップ作成
  cp "$skill_file" "$skill_file.bak.$(date +%Y%m%d-%H%M%S)"

  # Phase 4 セクションを追記
  cat >> "$skill_file" <<EOF


---

## 🌐 Bolgheri Daily Brief サイトへの自動反映

チャット本文にレポートを出力した**後**、必ず以下を追加実行する。
完全仕様は \`~/newsletter-dashboard/PUBLISH_GUIDE.md\` を参照。

### このスキル固有の設定

| 項目 | 値 |
|------|-----|
| SOURCE slug | \`$slug\` |
| categoryLabel | \`$catLabel\` |
| SourceLabel | \`$srcLabel\` |
| サイトパス | \`/$slug/\` |
| タイトル形式 | \`$titleFmt\` |

### ワークフロー

1. **マウント確認**: Cowork VMから \`~/newsletter-dashboard/\`（VMパス: \`/sessions/<session>/mnt/newsletter-dashboard/\`）にアクセスできない場合、\`mcp__cowork__request_cowork_directory\` で \`/Users/hashiramototetsuya/newsletter-dashboard\` をマウントする
2. **ファイル保存**: \`<mount-path>/content/$slug/<YYYY-MM-DD>.md\` に下記テンプレートで保存
3. **git commit**: sandboxで \`cd <mount-path> && git add content/$slug/<YYYY-MM-DD>.md && git commit -m "Add $srcLabel <YYYY-MM-DD>"\`
4. **ユーザー通知**: チャット末尾に下記の通知ブロックを追記

### 保存ファイルのテンプレート

\`\`\`markdown
---
title: "$titleFmt"
date: YYYY-MM-DD
categories: ["$catLabel"]
tags: [主要テーマから3〜5個抽出: 例 $sampleTags]
original_url: "<Gmailから取得した元URL or 代表URL>"
summary: "<TOPテーマを1行で要約（60字以内）>"
---

## 出典
[$srcLabel 原文](<original_url>)

---

<チャット本文で出力したMarkdownレポート全文をそのまま貼り付け>
\`\`\`

### チャット末尾に追記する通知ブロック

\`\`\`markdown
---

💾 **Bolgheri Daily Brief に保存済**: \`content/$slug/YYYY-MM-DD.md\`
🚀 **公開手順**: GitHub Desktop で **「Push origin」** をクリック → 1〜3分後に公開
👉 https://th1214.github.io/newsletter-dashboard/$slug/
\`\`\`
EOF

  echo "✅ 適用完了: $folder"
  applied=$((applied + 1))
done

echo ""
echo "=== 完了 ==="
echo "適用: $applied スキル"
echo "既適用スキップ: $skipped スキル"
echo ""
echo "バックアップは各 SKILL.md.bak.<timestamp> として保存されています。"
echo "問題があれば該当スキルの .bak ファイルをSKILL.mdにリネームすれば元に戻せます。"
