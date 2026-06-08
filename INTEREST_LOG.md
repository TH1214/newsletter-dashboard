# Personal Interest Log / My Interest Dashboard

運営者本人（`hashiramoto@mellowps.com`）が「自分がどの記事を読んだか／どのソース・カテゴリに興味が偏っているか」を可視化する **個人専用** の Reading Interest Log。一般訪問者向けのアクセス解析ではない。

公開サイト: https://th1214.github.io/newsletter-dashboard/
My Interest: https://th1214.github.io/newsletter-dashboard/interest/

実装は本番サイト本体である **Next.js (`v2-next/`)** に組み込まれている（リポジトリ直下の Hugo `layouts/` は旧 v1 で本番未使用）。

---

## Firebase セットアップ（設定済み）

- **プラン: Spark plan（無料）。Billing 未登録。** 支払い方法登録・Blaze へのアップグレードは行わない。
- 使用する Firebase 機能は **Firestore と Firebase Authentication のみ**。
- project: `newsletter-interest-log` / Firestore location: `asia-northeast1`（東京）
- Authentication: Google ログイン有効。
- `firebaseConfig` の `apiKey` は秘密鍵ではなくフロントエンド公開前提の識別子。保護は Firestore Security Rules 側で担保する。

### 使っていないもの（意図的に不使用）

Blaze plan / Billing account / Cloud Functions / Cloud Storage / **Firebase Hosting**（公開は GitHub Pages のまま）/ BigQuery 連携 / AI 系機能 / SQL Connect / Google Analytics・GA4。

---

## Authorized domains

Firebase Authentication の Authorized domains に以下が登録されている必要がある:

- `th1214.github.io` … 本番（登録済み）
- `localhost` … ローカル確認用（`npm run dev` でのログインに必要。未登録なら追加すること）

---

## Firestore collection: `reading_events`

記事クリック 1 回につき 1 document（`event_id` を doc id に採用、`setDoc(merge)` で冪等＝再送しても二重登録されない）。

主なフィールド:

```
event_id, user_email, uid, device_id, session_id,
clicked_at, clicked_date, clicked_hour, weekday,
article_id, title, source, category, section, issue_date, article_url,
dashboard_page, referrer_type, event_type,
user_agent, viewport_width, viewport_height, is_mobile,
dashboard_dwell_seconds, estimated_external_dwell_seconds,
created_at, synced_at
```

`event_type`: `article_click` / `outbound_click` / `dashboard_view` / `interest_dashboard_view`

- `article_id` は既存の安定 ID（`"{section}-YYYY-MM-DD"`）をそのまま使用。
- `estimated_external_dwell_seconds` は **外部サイト滞留の推定値**。外部リンククリック時刻と Dashboard へ戻った時刻の差分で、**上限 30 分（1800 秒）で cap**。正確な外部滞留時間ではない。

---

## Firestore Security Rules（公開済み）

セキュリティの本体は Rules 側。許可メールのみ `reading_events` を read/write できる。

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /reading_events/{eventId} {
      allow read, write: if request.auth != null
        && request.auth.token.email == "hashiramoto@mellowps.com";
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

クライアント側にも `ALLOWED_EMAIL` 判定を入れているが、これは二重防御であり依存しない。

---

## 動作

- **記録**: 記事カード／原文リンクをクリックした瞬間にイベント生成 → まず Firestore へ 1 書き込み。失敗時のみ localStorage の pending queue に退避し、次回アクセス時・ログイン完了時・online 復帰時・Dashboard 復帰時に **自動再送**（ユーザー操作の同期ボタンは無い）。
- write-ahead 方式（先に queue に積み、保存成功で除去）のため、ページ遷移や通信失敗でも取りこぼさない。
- 数秒以内の連打は dedupe して無駄な書き込みを避ける。
- **正本は Firestore**。localStorage は通信失敗時の保険のみ。
- どの端末（iPhone 5G / Mac / iPad 等）からでも、ログイン済みなら自動記録され、Dashboard で統合表示される。

### 無料枠保護

- 1 クリック 1 書き込み。
- Dashboard を開いた時だけ Firestore を読む（直近 30 日 / 最大 500 件）。
- **`onSnapshot`（リアルタイム購読）は使わない。** `getDocs` で必要時のみ。集計はブラウザ側。
- 単一フィールド `orderBy('clicked_at') + limit` のみ使用 → 複合インデックス不要。

---

## 設定値（1 か所に集約）

`v2-next/lib/interest/config.ts`:

```
ALLOWED_EMAIL              = "hashiramoto@mellowps.com"
QUERY_LIMIT                = 500
LOOKBACK_DAYS              = 30
EXTERNAL_DWELL_CAP_SECONDS = 1800
COLLECTION                 = "reading_events"
```

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `v2-next/lib/interest/config.ts` | 設定値・firebaseConfig 集約 |
| `v2-next/lib/interest/firebaseClient.ts` | Firebase modular SDK 初期化・Auth(Google)・Firestore・許可メール判定 |
| `v2-next/lib/interest/logger.ts` | event 生成・Firestore 保存・pending queue・自動再送・外部滞留推定 |
| `v2-next/lib/interest/attrs.ts` | 記事リンクへ付与する `data-*` 属性生成（server/client 兼用） |
| `v2-next/components/interest/InterestLogger.tsx` | 全ページ共通のクリック委譲ランナー（layout に mount） |
| `v2-next/components/interest/InterestDashboard.tsx` | My Interest Dashboard 本体（auth・query・集計・描画） |
| `v2-next/components/interest/interest.css` | Dashboard 専用スタイル |
| `v2-next/app/interest/page.tsx` | `/interest/` ルート（`noindex`） |

---

## ローカル確認

```bash
cd v2-next
npm install        # firebase を含む依存を取得
npm run dev        # http://localhost:3210/newsletter-dashboard/interest/
npm run build      # 静的エクスポート (output: 'export')
```

`localhost` が Authorized domains に入っていれば、ローカルでも Google ログイン→記録→Dashboard 表示まで確認できる。

---

## 受け入れ確認チェックリスト（本番 = main マージ後）

ログは大きく 2 種類ある。両方が記録されることを確認する。

1. **`article_click`** — トップ／一覧の記事カードをクリック（内部の `/issues/{date}/{slug}/` 記事詳細へ遷移）したときの記録。
2. **`outbound_click`** — 記事詳細ページ内の外部原文リンク **「View original ↗」** を押し、外部サイトへ飛んだときの記録。戻ると同 doc に `estimated_external_dwell_seconds`（推定値）が追記される。

> 本当に見たい指標は「どの記事を開いたか」だけでなく「どの記事から外部原文へ飛んだか／どのソースへ飛んだか／飛んでから戻るまでの推定時間」。
> そのため確認では **記事カードのクリックだけでなく、必ず記事詳細ページの外部リンクも押すこと。**

### 手順（Mac）

1. Mac Safari で `https://th1214.github.io/newsletter-dashboard/` を開く。
2. ナビの **「★ My Interest」** → **Sign in with Google** → `hashiramoto@mellowps.com` でログイン。
3. トップへ戻り、**記事カードを1つクリック**（→ `article_click`）。
4. 開いた記事詳細ページ末尾の **「View original ↗」を押す**（→ `outbound_click`）。外部サイトを数秒見てタブを戻る（→ `estimated_external_dwell_seconds` 追記）。
5. Firebase Console → Firestore Database → `reading_events` collection を開いて document を確認。

### 手順（iPhone・5G）

6. iPhone Safari を **Wi-Fi を切って 5G** にして同じ URL を開く。
7. 同じ Google アカウントでログイン。
8. **記事カードを1つクリック**（→ `article_click`）。可能なら記事詳細で **View original** も押す（→ `outbound_click`）。
9. Mac で `/interest/`（My Interest）を開き、**iPhone でクリックした履歴も統合表示**されることを確認（同期ボタン・export/import なし）。

### Firestore 上で確認すべきフィールド（`reading_events` の各 document）

| 確認項目 | フィールド | 期待値 |
|---|---|---|
| 記事クリックが残るか | `event_type` | `article_click` |
| 外部原文クリックが残るか | `event_type` | `outbound_click` |
| ソースが入っているか | `source` | 例: `WSJ 10-Point` / `NYT Breaking News` |
| カテゴリ/セクションが入っているか | `category` または `section` | `category`=タグ等 / `section`=`wsj` 等の slug |
| 記事URLが入っているか | `article_url` | `/issues/{date}/{slug}/` |
| 外部滞留の推定値（戻り後） | `estimated_external_dwell_seconds` | 0 より大、最大 1800（30分cap・推定値） |
| 本人記録か | `user_email` | `hashiramoto@mellowps.com` |
| 端末識別 | `device_id` / `is_mobile` | Mac と iPhone で別 `device_id`、iPhone は `is_mobile=true` |

**合格ライン（実用上 OK）**: `article_click` と `outbound_click` の両方が保存され、`source`・(`section` または `category`)・`article_url` が入っており、iPhone のログが Mac の `/interest/` に出ること。

### うまくいかない場合

- `/interest/` にログインボタンが出ない / Google ログイン後に戻ってこない → Firebase Authentication の **Authorized domains に `th1214.github.io`** が入っているか再確認（登録済みのはず）。
- 記録されない → ブラウザのコンソールで Firestore 権限エラーが出ていないか、ログイン中メールが許可メールと一致しているかを確認。書き込みの本体ガードは Security Rules 側。
