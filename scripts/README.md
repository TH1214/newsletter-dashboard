# scripts/

## apply-phase4-to-skills.sh

既存の翻訳スキル（WSJ・NYT BN・Short Squeez・Skift・Buysiders・NYT OP・BI）に、
本サイトへの自動保存・コミット処理を追加するセクションを一括で追記するスクリプト。

### 使い方（Macローカルターミナル）

```bash
cd ~/newsletter-dashboard
bash scripts/apply-phase4-to-skills.sh
```

### 挙動

- `~/.claude/skills/<skill>/SKILL.md` を各スキルについて上書き（追記）
- 同じセクションが既にある場合はスキップ（冪等）
- 変更前に `SKILL.md.bak.<タイムスタンプ>` としてバックアップ作成

### ロールバック

何か問題があれば各スキルフォルダの最新 `.bak.*` を `SKILL.md` にリネームで元に戻せる:

```bash
cd ~/.claude/skills/wsj-newsletter-report
ls -lt SKILL.md.bak.*  # 最新のを確認
mv SKILL.md.bak.20260415-223500 SKILL.md  # 最新バックアップに戻す
```
