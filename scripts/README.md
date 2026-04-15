# scripts/

## publish-skill/SKILL.md

Bolgheri Daily Brief サイトに翻訳レポートを自動反映するための**新スキル**の定義ファイル。

### セットアップ手順

Cowork アプリで新しいスキルを作成し、以下の内容を登録：

1. Cowork アプリ → 設定 → スキル → **新規スキル作成**
2. スキル名: `publish-to-bolgheri`
3. SKILL.md の内容: `publish-skill/SKILL.md` を全文コピペ
4. 保存

### 使用方法

```
1. "W" や "BN" や "OWS" 等を入力 → 翻訳レポートがチャットに表示
2. "P" と入力 → publish-to-bolgheri スキルが起動 → 直前レポートを保存＆commit
3. GitHub Desktop で「Push origin」をクリック → 数分後にサイト公開
```

### トリガーキーワード

- `P` （1文字）
- `pub`, `publish`, `Publish`
- `サイトに公開`, `サイト反映`, `反映`, `保存して`
