# 設計 v2: Mac生成済みClaude Markdown の Git-Relay

- 作成: 2026-07-22
- ステータス: **設計のみ / 実装未実施**（v1 Email-Relay を置換）
- 前提レビュー: ChatGPT講評（②フォールバックの永久ブロック・④HTML逆変換の脆さ が主要指摘）を反映
- 対象: メール配信のある8ソースの Dashboard 掲載を、**gpt-4o-mini再翻訳 → Macで生成済みのClaude正規MarkdownをGit経由で受け渡し** に切り替える

---

## 1. 設計転換（v1 → v2）

v1は「Claude日本語版**メールのHTML本文**をGitHub Actionsで取得しMarkdownへ逆変換」だった。これは
**完成品(Claudeの整形済み日本語)を一度HTMLに落として再度復元する**構造で、Gmail検索・件名照合・
HTML除去・受信時刻との結合・Gmail認証依存という脆さを抱える。

**v2はこれらを全廃**する。Macは既にClaude本文を持っているのだから、**Mac側で正規Markdownを1回だけ
生成し、それをGit経由でそのまま渡す**。→ Gmail取得もHTMLパースもタイミング当て推量も不要になる。

> 本設計の目的は「メールを転載すること」ではなく **「Mac生成済みのClaude出力をサイトへ安全に渡すこと」**。

### 対象8ソース（変更なし）
nyt-bn / nyt-op / wsj / economist / business-insider / skift / short-squeez / buysiders
（非対象12ソース= DealBook/Hospitality Net/HI/CNBC(停止)/PERE/Maverick/武者/Axios×3/My CLIP は現行のまま）

---

## 2. アーキテクチャ（全体像）

```
[Mac newsletter-automation]
  ├─ (既存) Claude翻訳 → メール送信                 … 人間向け・従来どおり（独立ステップ）
  └─ (新規) Claude本文 → content/<src>/<date>.md 生成
                         → 専用ブランチ relay-incoming へ push   … 機械向け・独立ステップ

                    │ push (relay-incoming)
                    ▼
[GitHub Actions: relay-integrate.yml]   ← 専用ブランチへのpushがトリガー
  1. 変更された content/<src>/*.md を tmp で検証（§5）
  2. main上の同ファイルの generator と突合し、上書き優先度（§4）で採否
  3. 採用分のみ main へ「単一commit」で統合 → deploy 起動
                    │
                    ▼
[GitHub Actions: daily-translate.yml（既存・改修）]
  ├─ 06:00 JST: 非relay 12ソースを従来どおり
  └─ relay 8ソース: 「締切までに main に有効な claude-relay が無い」場合のみ gpt-fallback（§6）
```

**要点**
- **mainへの直接pushはしない**。Macは検証前ブランチ `relay-incoming` に置くだけ。**mainへの唯一の書き手はGitHub Actions**（検証ゲートを必ず通す）。
- **email送信 と git push は別ステップ**に分離。push失敗はpushだけ再実行でき、**GitHub障害でメールを再送しない**。
- relay採否の判定基準は**メールの有無ではなく「main上の generator」**（一貫性のため）。

---

## 3. front matter 仕様

既存項目に **3項目を追加**（それ以外の既存レンダリング/検索/Interestは不変）。

```yaml
---
# --- 既存（Dashboardが使う）---
title: "WSJ The 10-Point｜2026年07月22日"   # メールに明確な見出しがあればそれを優先、無ければ「ソース名｜日付」
date: 2026-07-22                            # dashboard_date（サイト上でどの日の記事か）
categories: ["WSJ"]
tags: []                                     # 無い場合はフィールド自体を省略してもよい
summary: "..."                               # 最初の有効本文段落から。挨拶/日付/署名/免責はsummaryにしない・創作しない
hero_image: "/images/wsj/_default.png"       # relayソースは §7 のソース別固定画像
original_url: ""                             # 単一の原文URLが明確な時のみ。まとめニュースレターでは省略（捏造しない）
# --- v2 追加（provenance）---
generator: claude-relay                      # manual | claude-relay | gpt-fallback
body_hash: "sha256:…"                        # 正規化した本文のハッシュ（変更検知・重複検知・検証用）
source_date: 2026-07-22                      # ニュースレター自身が示す発行日（received日とは別概念）
---
```

**日付は3概念を分離**（v1の混同を是正）:
- `source_date` … ニュースレターの発行日（件名/本文由来。Mac側で機械可読に確定）
- `date`（=dashboard_date）… サイト上の扱い日
- （参考）`received_at` … 実受信日時。必要なら front matter か run ログに ISO8601(JST) で保持

`generator` は**必須**。これが上書き優先度（§4）と締切フォールバック（§6）の判定キー。

---

## 4. 上書き優先度（provenance priority）

**優先度: `manual` > `claude-relay` > `gpt-fallback`**（単調）。統合時に「新規」と「main既存」の generator を比較して採否を決める。

| main既存 \ 新規 | claude-relay | gpt-fallback | manual |
|---|---|---|---|
| （無し） | ✅ 採用 | ✅ 採用 | ✅ 採用 |
| gpt-fallback | ✅ **上書き（昇格）** | ⏭️ 同格更新（§注1） | ✅ 上書き |
| claude-relay | 🔁 §注2 | ❌ **却下** | ✅ 上書き |
| manual | ❌ 却下 | ❌ 却下 | 🔁 §注2 |

- **注1**: 既存gpt-fallback を 別のgpt-fallback で更新するのは、`body_hash` が異なる時のみ許可（無駄コミット防止）。
- **注2**: 同格(claude→claude / manual→manual)は `body_hash` が異なる時のみ上書き（＝内容が変わった時だけ）。BN/OPの版差し替え（朝版→最新版）はここで表現。
- `manual`（人間が直接置いた確定版）は**自動系では絶対に上書きしない**。

> これにより ChatGPT指摘②「一時的な未着 → gpt版が永久に残る」を**構造的に排除**（後からclaude-relayが来れば必ず昇格）。

---

## 5. 検証条件（tmp → 合格時のみ main へ反映）

統合ワークフローは **一時領域で検証し、合格したファイルだけ**を main のパスへ置く。**失敗しても既存の正常ファイルは消さない/触らない**。

必須チェック（最小・実用十分）:
1. **front matter が妥当な YAML**（YAMLライブラリでparse。文字列連結生成は禁止）
2. **`date`(dashboard_date) が対象日と一致**
3. **本文の最小長**（日本語として意味を持つ最低字数。フッターだけの合格を排除）
4. **`generator` が既定値のいずれか**（manual|claude-relay|gpt-fallback）
5. **`body_hash` が存在し、本文から再計算した値と一致**（改竄/破損検知）
6. Markdown内に生HTMLを許すテンプレなら **script/iframe/form/on\*/style/トラッキング画像を除去**（v2はMac生成Markdownなので通常混入しないが安全弁）
7. **URLは http/https のみ許可**（javascript: 等を拒否）

やり過ぎない方針（ChatGPT過剰指摘は不採用）: リンク密度・全ソース横断のhash一意性・段落数の厳密下限などは**入れない**（個人・低リスク運用）。

ログには**本文全体を出さない**（message要旨・字数・hash・エラー分類のみ）。

---

## 6. 締切後フォールバック（判定はリポジトリの generator）

relay 8ソースについて、**「当日の締切時刻までに main に有効な `claude-relay` の `content/<src>/<date>.md` が無い」場合のみ** gpt-fallback を許可する。**メールの有無では判定しない。**

- **締切前**: `not_due`。フォールバックしない（＝当日のgpt版を作らない）。
- **締切後・claude-relay 未反映**: gpt-fallback を生成（従来 daily-translate 経路）。generator=`gpt-fallback` で保存。
- **その後 claude-relay が到着**: §4 の昇格で **gpt-fallback を上書き**。
- **Buysiders（不定期）**: 未着は障害ではなく正常。締切/フォールバックの対象外（到着時のみ掲載）。

締切はソース別に設定（§8 の設定ファイル）。実配信時刻は**実測して決める**（v1の「10:00で出揃う」等の当て推量はしない）。

失敗状態は**4分類に圧縮**（ChatGPTの10状態は過剰）: `not_due` / `imported`（claude-relay反映） / `fallback`（gpt生成） / `error`（auth/parse/validation）。`error` のみ通知対象。

---

## 7. hero 画像

relay対象は **ソース別の固定 hero 画像**（例 `/images/<src>/_default.png`）。
- 理由: Unsplash等の外部依存を切り、**「本文がgpt→claudeへ差し替わった後に旧heroが残る」不整合も回避**。
- 生成器(`generate_hero_image.py`)への依存を relayソースでは外す。hero失敗で記事掲載を止めない（現行も non-blocking）。

---

## 8. ソース設定（1ファイルに集約）

`config/relay_sources.json`（案）に8ソース分を集約。コード各所に散らさない。GitHub変数は**緊急kill switch**用途に限定。

```jsonc
{
  "wsj":            { "relay": true, "subject_label": "WSJ The 10-Point", "deadline_jst": "TBD(実測)", "edition": "single",  "hero": "/images/wsj/_default.png" },
  "nyt-bn":         { "relay": true, "subject_label": "NYT Breaking News", "deadline_jst": "10:30(要実測)", "edition": "morning_latest_by_deadline", "hero": "..." },  // 朝版確定
  "nyt-op":         { "relay": true, "subject_label": "NYT Opinion Today", "deadline_jst": "10:30(要実測)", "edition": "morning_latest_by_deadline", "hero": "..." },  // 朝版確定
  "economist":      { "relay": true, "subject_label": "The Economist",     "deadline_jst": "TBD", "edition": "single", "hero": "..." },
  "business-insider":{ "relay": true, "subject_label": "BI Today",         "deadline_jst": "TBD", "edition": "single", "hero": "..." },
  "skift":          { "relay": true, "subject_label": "Skift Daily",        "deadline_jst": "TBD", "edition": "single", "hero": "..." },
  "short-squeez":   { "relay": true, "subject_label": "Short Squeez",       "deadline_jst": "TBD", "edition": "single", "hero": "..." },
  "buysiders":      { "relay": true, "subject_label": "Buysiders", "irregular": true, "hero": "..." }
}
```

**版選択(edition)を「最新」ではなくルールで固定**（ChatGPT指摘＝冪等性）:
- `single`: その日1通。
- `morning_latest_by_deadline`（BN/OP＝**朝版で確定**）: 「対象日付のメールのうち**朝の締切(≈10:30 JST・要実測)までに届いた最も新しいもの**」を採用し、**採用後はロック**（＝再実行しても同じ版・締切後の午後/夜版では上書きしない）。**サイト表記に「朝版(morning edition)」を明記**する。

---

## 9. ブランチ構成・統合フロー

- **`relay-incoming`**: Mac が push する専用ブランチ。検証前の生成物置き場。
- **`relay-integrate.yml`**: `relay-incoming` への push で起動。
  1. 差分の `content/<src>/<date>.md` を tmp へ取り出し §5 検証。
  2. main の同ファイル generator と §4 突合 → 採否。
  3. 採用分を **main へ単一commit**（既存の集約commit方針を踏襲＝競合レス）→ deploy。
  4. 取り込み済みは `relay-incoming` 側を整理（毎回Macが最新を上書きpushする運用でも可）。
- **daily-translate.yml（改修）**: 06:00 は非relay12を従来どおり。relay8は §6 の締切後フォールバックのみ担当。

**concurrency**: main への統合/deploy は直列化。ただし**取り込み処理を途中キャンセルして記事を失わないよう**、取り込み系は cancel しない設定にし、deploy 系のみ最新優先にする（キャンセル方針を分離）。

---

## 10. Mac側の分離（障害境界）

`newsletter-automation` を **2つの独立ステップ**に:
1. **メール送信**（人間向け・従来）
2. **Markdown生成＋`relay-incoming` push**（機械向け・新規）

- push失敗は **pushだけ再実行**（メール再送しない）。冪等: 同一 `<src>/<date>` は上書きpush、`body_hash` 同一なら統合側で no-op。
- Mac→GitHub 認証は既存のGit運用（token/gh）を流用。**mainには触れない**ので事故時の影響が限定的。

---

## 11. 段階導入（各段階・承認制／実装はまだ）

- **Phase 0（決定確定・今ここ）**: 本v2で以下を固定 = ブランチ構成 / front matter追加3項目 / 上書き優先度 / 締切後フォールバック定義 / 検証条件 / hero方針。残る変数は各ソースの**実配信時刻の実測 → deadline確定**のみ。
- **Phase 1**: Mac側Markdown生成器を試作し、**過去のClaude本文で fixture 生成 → 現行md品質と目視比較**（GitHub未接続・pushしない）。
- **Phase 2**: `relay-integrate.yml`（検証＋優先度統合）を実装し、**canary 1ソース**だけ `relay: true`。当該ソースの実配信時刻に合う運用で観測。
- **Phase 3**: 締切後フォールバックの「repo generator判定」を daily-translate に実装（**これが入るまでフォールバックは有効化しない**）。
- **Phase 4**: 残りソース展開。BN/OP の edition/deadline を確定。
- **Phase 5（任意）**: 直近数日を突合する reconciliation（catch-up）を追加（Mac停止/取りこぼし回復）。個人運用では後回し可。
- **ロールバック**: `config/relay_sources.json` で該当ソース `relay:false` → 即 従来gpt-4o-mini。

---

## 12. 確定した仕様（このv2で fixed）
1. Mac は `content/<src>/<date>.md` を生成し **専用ブランチ `relay-incoming`** へ push（mainへ直接pushしない）。
2. front matter に **`generator` / `body_hash` / `source_date`** を追加。
3. 上書き優先度 **manual > claude-relay > gpt-fallback**（gpt既存→claude新規は昇格、claude/manual既存→gpt新規は却下）。
4. **締切前は即フォールバックせず**、締切後に「main に有効な claude-relay が無い」時のみ gpt-fallback。判定は**リポジトリの generator**。
5. 検証は **tmp で date一致・最小長・generator・body_hash** を確認してから main 反映（失敗時に既存正常ファイルを消さない）。
6. relayの hero は **ソース別固定画像**。
7. **email送信 と push は分離**。push失敗はpushのみ再実行。

## 13. 未確定（Phase1着手前に実測/決定）
- 各relayソースの**実配信時刻 → deadline_jst** の確定（launchd値と実受信のズレを実測）。BN/OPは**朝の締切(≈10:30)を実測で最終確定**。
- `relay-incoming` の取り込み後クリーン運用（毎回上書きpush方式で十分か）。

## 決定済（2026-07-22）
- **BN/OP は「朝版」で確定**。edition=`morning_latest_by_deadline`（朝締切≈10:30までの最新版を採用しロック・午後/夜版では上書きしない）。サイト表記に「朝版」を明記。

---

## 付録: ChatGPTレビューの採用判断（要約）
- **全面採用**: ④HTML逆変換の廃止＝Git-Relay化 / ②provenance優先度で上書き（フォールバック永久ブロックの解消）/ ③source_date分離 / YAML安全生成 / 検証合格まで既存ファイルを消さない / email送信とpush分離。
- **縮小採用**: provenanceは`generator`+`body_hash`+`source_date`の3点に限定 / 失敗状態は4分類 / 検証は最小項目 / 設定は小さなJSON1枚。
- **不採用（このスケールで過剰 or 誤読）**: 3時間帯ポーリング（Git-Relayで論点消滅）/ reconciliation必須（任意・後回し）/ 動的matrix prepare（任意）/ 「matrix同時pushで競合」（**現行は既に単一commit集約済み＝誤読**）/ リンク密度・全ソースhash一意性等の過剰検証 / 「10:00で出揃う/出揃わない」断定（実測で決める）。
