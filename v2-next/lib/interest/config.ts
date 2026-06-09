/* ------------------------------------------------------------------
   Personal Interest Log — central configuration (single source of truth)

   設計コンセプト:
   - Firestore を正本にする。localStorage は通信失敗時の保険のみ。
   - Firebase Spark plan 無料範囲のみ (Firestore + Authentication)。
     Cloud Functions / Storage / Hosting / BigQuery / GA4 は一切使わない。
   - セキュリティの本体は Firestore Security Rules 側 (許可メールのみ read/write)。
     クライアント側の ALLOWED_EMAIL 判定は二重防御であり、依存はしない。
   ------------------------------------------------------------------ */

/** 記録・表示を許可する唯一の Google アカウント */
export const ALLOWED_EMAIL = 'hashiramoto@mellowps.com';

/** My Interest Dashboard が一度に読む最大件数 (無料枠保護) */
export const QUERY_LIMIT = 500;

/** Dashboard 初期表示の遡及日数 */
export const LOOKBACK_DAYS = 30;

/** 外部サイト滞留推定値の上限 (秒) — これ以上はノイズとして cap */
export const EXTERNAL_DWELL_CAP_SECONDS = 1800;

/** 記事詳細ページの読書滞留 (dashboard_dwell_seconds) の上限 (秒) */
export const READ_DWELL_CAP_SECONDS = 1800;

/** 記事本文スナップショットの最大文字数 (Firestore document size 保護) */
export const SNAPSHOT_MAX_CHARS = 20000;

/** これ未満は「短時間で離脱」とみなす閾値 (秒) */
export const SHORT_READ_SECONDS = 10;

/** Firestore collection 名 */
export const COLLECTION = 'reading_events';

/**
 * firebaseConfig — apiKey は秘密鍵ではなくフロントエンド公開前提の識別子。
 * 保護は Firestore Security Rules 側で担保する。
 */
export const firebaseConfig = {
  apiKey: 'AIzaSyDriHLuGFiF6cQeYM-U2EF4Vr1JBHnvHgk',
  authDomain: 'newsletter-interest-log.firebaseapp.com',
  projectId: 'newsletter-interest-log',
  storageBucket: 'newsletter-interest-log.firebasestorage.app',
  messagingSenderId: '246917811561',
  appId: '1:246917811561:web:add4636f26efd2b67a81f8',
};
