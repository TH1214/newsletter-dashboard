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

`event_id` を doc id に採用、`setDoc(merge)` で冪等＝再送しても二重登録されない。

### イベント種別（KPI は「読書時間」中心）

| event_type | 位置づけ | 説明 |
|---|---|---|
| **`article_detail_read`** | **最重要（主分析対象）** | 記事詳細ページの読書セッション。開いた時点で1 doc作成し、滞留秒数とその時点の記事スナップショットを保存。離脱のたびに `setDoc(merge)` で更新 |
| `article_click` | 入口ログ（補助） | 一覧/トップで記事カードをクリック |
| `outbound_click` | 補助 | 記事詳細の「View original ↗」で外部原文へ離脱 |
| `interest_dashboard_view` | 補助 | My Interest を開いた（セッション1回・最小限） |

`article_detail_read` の doc id（= read session id）は `article_detail_read_{device_id}_{session_id}_{article_id}`。同じ session × 同じ記事は同じ doc を merge 更新する。

### 主なフィールド

共通: `event_id, event_type, user_email, uid, device_id, session_id, clicked_at, clicked_date, clicked_hour, weekday, article_id, title, source, section, category, tags, issue_date, article_url, is_mobile, created_at, updated_at, synced_at`

`article_detail_read` 追加: `read_started_at, read_ended_at, dashboard_dwell_seconds`

**記事スナップショット**（CMS が将来変わっても当時読んだ内容を再現するため）:
```
article_snapshot_title, article_snapshot_summary, article_snapshot_body_text,
article_snapshot_source, article_snapshot_section, article_snapshot_category,
article_snapshot_tags, article_snapshot_issue_date, article_snapshot_url,
article_snapshot_captured_at
```

- `article_id` は既存の安定 ID（`"{section}-YYYY-MM-DD"`）。`title` は記事 frontmatter の `summary`（この CMS の `title` は「ソース名｜日付」で個別見出しが無いため）。
- `dashboard_dwell_seconds` は **Dashboard 内の記事詳細を読んでいた秒数**（整数・上限 1800 秒）。これが本命の指標。
- `article_snapshot_body_text` は記事詳細に表示中の本文プレーンテキスト（最大 20,000 文字で truncate）。取得できなくても summary/tags/source/section/issue_date は保存。
- `estimated_external_dwell_seconds` は **外部サイト滞留の推定値（補助・不正確）**。外部リンククリック〜Dashboard 復帰の差分、**上限 30 分（1800 秒）で cap**。

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

最重要は **`article_detail_read`（記事詳細ページの読書セッション）**。外部リンクは補助。

### 手順（Mac）

1. Mac Safari で `https://th1214.github.io/newsletter-dashboard/` を開く。
2. ナビの **「★ My Interest」** → **Sign in with Google** → `hashiramoto@mellowps.com` でログイン。
3. トップへ戻り、記事カードを1つクリック → **記事詳細ページを約10秒開いて**から戻る/別ページへ。
4. 別の記事詳細を **約30秒開いて**から戻る。
5. 記事詳細の **「View original ↗」** も押す（→ 補助の `outbound_click`）。
6. Firebase Console → Firestore Database → `reading_events` で `event_type == article_detail_read` の document を確認。

### 手順（iPhone・5G）

7. iPhone Safari を **Wi-Fi を切って 5G** にして同じ URL を開く。
8. 同じ Google アカウントでログイン。
9. 記事詳細ページを開いて数十秒読む。
10. Mac で `/interest/`（My Interest）を開き、**iPhone の読書セッションも統合表示**されることを確認（同期ボタン・export/import なし）。

### Firestore 上で確認すべきフィールド（`article_detail_read` の document）

| 確認項目 | フィールド | 期待値 |
|---|---|---|
| 読書セッションが残るか | `event_type` | `article_detail_read` |
| 読書秒数（約10秒/約30秒） | `dashboard_dwell_seconds` | 整数秒（例 約10 / 約30）、上限1800 |
| 実タイトル | `title` / `article_snapshot_title` | summary（ソース名でない） |
| 本文スナップショット | `article_snapshot_body_text` | プレーン本文（最大2万字） |
| 要約スナップショット | `article_snapshot_summary` | 1行要約 |
| ソース | `source` / `article_snapshot_source` | 例: `NYT DealBook` |
| セクション/カテゴリ/タグ | `section` / `category` / `tags` | slug / タグ / 配列 |
| 記事URL | `article_url` | `/issues/{date}/{slug}/` |
| 本人記録 | `user_email` | `hashiramoto@mellowps.com` |
| 端末識別 | `device_id` / `is_mobile` | Mac/iPhone で別 `device_id`、iPhone は `is_mobile=true` |
| （補助）外部滞留推定 | `estimated_external_dwell_seconds` | 0より大・最大1800・推定 |

**合格ライン**: `article_detail_read` が保存され、`dashboard_dwell_seconds` が秒で入り、`article_snapshot_summary`/`article_snapshot_body_text` と `source` が入っていること。My Interest の「最近読んだ記事」に実タイトル＋読書秒数が出て、ソース別・カテゴリ別が**読書秒数ベース**で表示され、iPhone の読書も Mac に統合表示されること。

### うまくいかない場合

- `/interest/` にログインボタンが出ない / Google ログイン後に戻ってこない → Firebase Authentication の **Authorized domains に `th1214.github.io`** が入っているか再確認（登録済みのはず）。
- 記録されない → ブラウザのコンソールで Firestore 権限エラーが出ていないか、ログイン中メールが許可メールと一致しているかを確認。書き込みの本体ガードは Security Rules 側。
