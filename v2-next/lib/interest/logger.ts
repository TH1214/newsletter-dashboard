/* ------------------------------------------------------------------
   Interest Logger core (client-only, framework-agnostic)

   役割:
   - 記事クリック / 外部リンククリックから reading_event を生成
   - 「クリック時に Firestore へ1書き込み」(1 click = 1 write)
   - write-ahead: まず localStorage の pending queue に積み、保存成功で除去。
     これで SPA 遷移や通信失敗でイベントを取りこぼさない。
   - 同じ event_id は setDoc(merge) で冪等 → 再送しても二重登録されない。
   - 外部リンクは outbound_click を記録し、戻り時間から
     estimated_external_dwell_seconds を「推定値」として同一 doc に追記。

   セキュリティ: 保存は許可メールでログイン済みのときのみ試行する。
   本体防御は Firestore Security Rules 側。
   ------------------------------------------------------------------ */
'use client';

import { doc, setDoc, serverTimestamp } from 'firebase/firestore';
import { getFirebase, isAllowedUser } from './firebaseClient';
import { COLLECTION, EXTERNAL_DWELL_CAP_SECONDS } from './config';
import type { User } from 'firebase/auth';

const DEVICE_KEY = 'il_device_id';
const SESSION_KEY = 'il_session_id';
const QUEUE_KEY = 'il_pending_queue';
const EXTERNAL_KEY = 'il_pending_external';

export type EventType =
  | 'article_click'
  | 'outbound_click'
  | 'dashboard_view'
  | 'interest_dashboard_view';

export interface ReadingEventMeta {
  article_id?: string;
  title?: string;
  source?: string;
  category?: string;
  section?: string;
  issue_date?: string;
  article_url?: string;
  referrer_type?: string;
  dashboard_dwell_seconds?: number;
  estimated_external_dwell_seconds?: number;
}

export interface ReadingEvent extends ReadingEventMeta {
  event_id: string;
  user_email: string;
  uid: string;
  device_id: string;
  session_id: string;
  clicked_at: string;        // ISO 8601
  clicked_date: string;      // YYYY-MM-DD (local)
  clicked_hour: number;      // 0–23 (local)
  weekday: string;           // Sun..Sat
  dashboard_page: string;    // クリック発生元ページ
  event_type: EventType;
  user_agent: string;
  viewport_width: number;
  viewport_height: number;
  is_mobile: boolean;
  created_at: string;        // ISO 8601 (client)
}

/* ---------- identity ---------- */

function randomId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return 'id-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function getDeviceId(): string {
  if (typeof localStorage === 'undefined') return 'no-storage';
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = randomId();
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export function getSessionId(): string {
  if (typeof sessionStorage === 'undefined') return 'no-session';
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = randomId();
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

/* ---------- current user (set by InterestLogger via auth listener) ---------- */

let _currentUser: User | null = null;
export function setCurrentUser(u: User | null) {
  _currentUser = u;
}
export function getCurrentUser(): User | null {
  return _currentUser;
}

/* ---------- event construction ---------- */

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function sanitizeDocId(s: string): string {
  // Firestore doc id は '/' 不可。安全な文字に正規化。
  return s.replace(/[^A-Za-z0-9_.:-]/g, '_').slice(0, 1400);
}

function buildEvent(eventType: EventType, meta: ReadingEventMeta): ReadingEvent {
  const now = new Date();
  const epochSec = Math.floor(now.getTime() / 1000);
  const deviceId = getDeviceId();
  const user = _currentUser;
  const pad = (n: number) => String(n).padStart(2, '0');
  const clickedDate = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const articleId = meta.article_id || 'none';

  // event_id は再送時も同一になるよう安定生成 (二重登録回避)
  const eventId = sanitizeDocId(`${eventType}_${deviceId}_${articleId}_${epochSec}`);

  return {
    event_id: eventId,
    user_email: user?.email || '',
    uid: user?.uid || '',
    device_id: deviceId,
    session_id: getSessionId(),
    clicked_at: now.toISOString(),
    clicked_date: clickedDate,
    clicked_hour: now.getHours(),
    weekday: WEEKDAYS[now.getDay()],
    article_id: meta.article_id || '',
    title: meta.title || '',
    source: meta.source || '',
    category: meta.category || '',
    section: meta.section || '',
    issue_date: meta.issue_date || '',
    article_url: meta.article_url || '',
    dashboard_page: typeof location !== 'undefined' ? location.pathname : '',
    referrer_type: meta.referrer_type || 'internal',
    event_type: eventType,
    user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
    viewport_width: typeof window !== 'undefined' ? window.innerWidth : 0,
    viewport_height: typeof window !== 'undefined' ? window.innerHeight : 0,
    is_mobile: typeof navigator !== 'undefined' ? /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) : false,
    dashboard_dwell_seconds: meta.dashboard_dwell_seconds ?? 0,
    estimated_external_dwell_seconds: meta.estimated_external_dwell_seconds ?? 0,
    created_at: now.toISOString(),
  };
}

/* ---------- pending queue (localStorage) ---------- */

export function getQueue(): ReadingEvent[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
  } catch {
    return [];
  }
}

function writeQueue(events: ReadingEvent[]) {
  if (typeof localStorage === 'undefined') return;
  try {
    // 暴走防止: 直近500件までに制限
    localStorage.setItem(QUEUE_KEY, JSON.stringify(events.slice(-500)));
  } catch {
    /* quota 超過などは無視 (保険機構のため) */
  }
}

function enqueue(ev: ReadingEvent) {
  const q = getQueue();
  if (q.some((e) => e.event_id === ev.event_id)) return; // 既にキュー済み
  q.push(ev);
  writeQueue(q);
}

function dequeue(eventId: string) {
  writeQueue(getQueue().filter((e) => e.event_id !== eventId));
}

export function getQueueCount(): number {
  return getQueue().length;
}

/* ---------- Firestore save ---------- */

async function saveEvent(ev: ReadingEvent): Promise<boolean> {
  const fb = getFirebase();
  if (!fb) return false;
  if (!isAllowedUser(_currentUser)) return false; // 許可メール以外は書き込まない
  // ログイン前にキューされたイベントは、再送時点の本人 identity を補完する
  const identity = {
    user_email: ev.user_email || _currentUser!.email || '',
    uid: ev.uid || _currentUser!.uid || '',
  };
  try {
    await setDoc(
      doc(fb.db, COLLECTION, ev.event_id),
      { ...ev, ...identity, synced_at: serverTimestamp() },
      { merge: true } // 同一 event_id は冪等 → 二重登録なし
    );
    return true;
  } catch {
    return false;
  }
}

/* ---------- rapid-click dedupe ---------- */

const _lastClick = new Map<string, number>();
const DEDUPE_MS = 3000;

function isDuplicateRapidClick(key: string): boolean {
  const now = Date.now();
  const prev = _lastClick.get(key);
  _lastClick.set(key, now);
  return prev !== undefined && now - prev < DEDUPE_MS;
}

/* ---------- public: record an event ---------- */

/**
 * イベントを記録する。
 * write-ahead: 先に queue に積み、保存成功で除去。失敗時は queue に残り自動再送される。
 * 返り値は「即時保存に成功したか」。
 */
export async function recordEvent(
  eventType: EventType,
  meta: ReadingEventMeta,
  opts: { dedupeKey?: string } = {}
): Promise<{ saved: boolean; event: ReadingEvent } | null> {
  if (opts.dedupeKey && isDuplicateRapidClick(`${eventType}:${opts.dedupeKey}`)) {
    return null; // 数秒以内の連打は無駄な書き込みを避ける
  }
  const ev = buildEvent(eventType, meta);
  enqueue(ev); // write-ahead
  const saved = await saveEvent(ev);
  if (saved) dequeue(ev.event_id);
  return { saved, event: ev };
}

/** pending queue を自動再送する (ユーザー操作不要)。 */
export async function flushQueue(): Promise<number> {
  if (!isAllowedUser(_currentUser)) return 0;
  const q = getQueue();
  let sent = 0;
  for (const ev of q) {
    const ok = await saveEvent(ev);
    if (ok) {
      dequeue(ev.event_id);
      sent++;
    }
  }
  return sent;
}

/* ---------- external (outbound) dwell tracking ---------- */

interface PendingExternal {
  event_id: string;
  startEpoch: number;
  meta: ReadingEventMeta;
}

/** 外部リンククリック: outbound_click を記録し、戻り時間計測を開始する。 */
export async function recordOutboundClick(meta: ReadingEventMeta): Promise<void> {
  const res = await recordEvent(
    'outbound_click',
    { ...meta, referrer_type: 'outbound' },
    { dedupeKey: meta.article_url || meta.article_id }
  );
  if (!res) return;
  const pending: PendingExternal = {
    event_id: res.event.event_id,
    startEpoch: Math.floor(Date.now() / 1000),
    meta,
  };
  try {
    localStorage.setItem(EXTERNAL_KEY, JSON.stringify(pending));
  } catch {
    /* ignore */
  }
}

/**
 * Dashboard へ戻ってきた時点で呼ぶ。外部滞留の推定値を計算し、
 * 同一 outbound_click doc に estimated_external_dwell_seconds を追記する。
 * 正確な外部滞留ではなく「推定値」である点に注意。
 */
export async function resolveExternalDwell(): Promise<void> {
  if (typeof localStorage === 'undefined') return;
  const raw = localStorage.getItem(EXTERNAL_KEY);
  if (!raw) return;
  let pending: PendingExternal;
  try {
    pending = JSON.parse(raw);
  } catch {
    localStorage.removeItem(EXTERNAL_KEY);
    return;
  }
  localStorage.removeItem(EXTERNAL_KEY);
  const elapsed = Math.floor(Date.now() / 1000) - pending.startEpoch;
  if (elapsed <= 0) return;
  const capped = Math.min(elapsed, EXTERNAL_DWELL_CAP_SECONDS); // 上限30分で cap
  const fb = getFirebase();
  if (!fb || !isAllowedUser(_currentUser)) return;
  try {
    await setDoc(
      doc(fb.db, COLLECTION, pending.event_id),
      { estimated_external_dwell_seconds: capped, synced_at: serverTimestamp() },
      { merge: true }
    );
  } catch {
    /* 失敗しても推定値なので致命ではない */
  }
}
