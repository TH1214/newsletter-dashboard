/* ------------------------------------------------------------------
   My Interest Dashboard (client)

   - 未ログイン → Sign in with Google
   - ログイン済みかつ許可メール → Firestore から直近 LOOKBACK_DAYS / QUERY_LIMIT 件のみ
     getDocs で読み込み (onSnapshot は使わない)。集計はブラウザ側。
   - 許可メール以外 → 権限なし表示。Firestore は読み書きしない。

   無料枠保護: Dashboard を開いた時だけ getDocs。orderBy('clicked_at') + limit の
   単一フィールドなので複合インデックス不要。日付フィルタは JS 側で行う。
   ------------------------------------------------------------------ */
'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  collection,
  query,
  orderBy,
  limit,
  getDocs,
} from 'firebase/firestore';
import {
  getFirebase,
  isAllowedUser,
  signInWithGoogle,
  signOutUser,
  watchAuth,
  type User,
} from '@/lib/interest/firebaseClient';
import {
  ALLOWED_EMAIL,
  COLLECTION,
  LOOKBACK_DAYS,
  QUERY_LIMIT,
} from '@/lib/interest/config';
import {
  setCurrentUser,
  recordEvent,
  getQueueCount,
  flushQueue,
} from '@/lib/interest/logger';
import { SECTIONS } from '@/lib/sections';
import './interest.css';

interface EventRow {
  event_type?: string;
  article_id?: string;
  title?: string;
  source?: string;
  category?: string;
  section?: string;
  issue_date?: string;
  clicked_at?: string;
  clicked_hour?: number;
  weekday?: string;
  device_id?: string;
  is_mobile?: boolean;
  estimated_external_dwell_seconds?: number;
}

type AuthState = 'loading' | 'signed-out' | 'denied' | 'allowed';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function Bar({ rows }: { rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.length === 0) return <p className="il-empty">データなし</p>;
  return (
    <>
      {rows.map((r) => (
        <div className="il-bar-row" key={r.label}>
          <span className="il-bar-label" title={r.label}>{r.label}</span>
          <span className="il-bar-track">
            <span className="il-bar-fill" style={{ width: `${(r.value / max) * 100}%` }} />
          </span>
          <span className="il-bar-val">{r.value}</span>
        </div>
      ))}
    </>
  );
}

function countBy(rows: EventRow[], key: (r: EventRow) => string | undefined) {
  const m = new Map<string, number>();
  for (const r of rows) {
    const k = key(r);
    if (!k) continue;
    m.set(k, (m.get(k) || 0) + 1);
  }
  return m;
}

function topRows(m: Map<string, number>, n = 12) {
  return [...m.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([label, value]) => ({ label, value }));
}

export function InterestDashboard() {
  const [auth, setAuth] = useState<AuthState>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [events, setEvents] = useState<EventRow[] | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // auth 監視
  useEffect(() => {
    setPending(getQueueCount());
    const unsub = watchAuth((u) => {
      setCurrentUser(u);
      setUser(u);
      if (!u) setAuth('signed-out');
      else if (isAllowedUser(u)) setAuth('allowed');
      else setAuth('denied');
    });
    return unsub;
  }, []);

  const loadData = useCallback(async () => {
    const fb = getFirebase();
    if (!fb || !isAllowedUser(user)) return;
    setLoadingData(true);
    setError(null);
    try {
      // Dashboard を開いた時だけ読む。単一フィールド orderBy + limit (index不要)。
      const snap = await getDocs(
        query(collection(fb.db, COLLECTION), orderBy('clicked_at', 'desc'), limit(QUERY_LIMIT))
      );
      const cutoff = new Date(Date.now() - LOOKBACK_DAYS * 86400 * 1000).toISOString();
      const rows: EventRow[] = [];
      snap.forEach((d) => {
        const r = d.data() as EventRow;
        if ((r.clicked_at || '') >= cutoff) rows.push(r);
      });
      setEvents(rows);
      // 自動再送 + interest_dashboard_view を最小限記録 (セッション1回)
      await flushQueue();
      setPending(getQueueCount());
      if (typeof sessionStorage !== 'undefined' && !sessionStorage.getItem('il_idv')) {
        sessionStorage.setItem('il_idv', '1');
        void recordEvent('interest_dashboard_view', {});
      }
    } catch (e) {
      setError('読み込みに失敗しました。時間をおいて再度お試しください。');
    } finally {
      setLoadingData(false);
    }
  }, [user]);

  // 許可ユーザーになったら一度だけ自動ロード
  useEffect(() => {
    if (auth === 'allowed' && events === null && !loadingData) void loadData();
  }, [auth, events, loadingData, loadData]);

  /* ---------- render: auth gates ---------- */

  if (auth === 'loading') {
    return (
      <div className="il-wrap"><div className="il-head"><h1>My Interest</h1></div>
        <p className="il-note">読み込み中…</p>
      </div>
    );
  }

  if (auth === 'signed-out') {
    return (
      <div className="il-wrap">
        <div className="il-head">
          <h1>My Interest</h1>
          <span className="il-eyebrow">Personal Reading Log</span>
        </div>
        <div className="il-signin">
          <p>あなた専用の読書傾向ダッシュボードです。<br />閲覧には Google ログインが必要です。</p>
          <button className="il-btn" onClick={() => signInWithGoogle().catch(() => setError('ログインに失敗しました'))}>
            Sign in with Google
          </button>
          {error && <p className="il-note" style={{ color: '#b00' }}>{error}</p>}
          <p className="il-note">記録・表示は {ALLOWED_EMAIL} のアカウントのみ有効です。</p>
        </div>
      </div>
    );
  }

  if (auth === 'denied') {
    return (
      <div className="il-wrap">
        <div className="il-head"><h1>My Interest</h1></div>
        <div className="il-denied">
          <p>このアカウント（{user?.email}）には閲覧権限がありません。</p>
          <p className="il-note">許可されたアカウントでログインし直してください。</p>
          <button className="il-btn-ghost" onClick={() => signOutUser()}>サインアウト</button>
        </div>
      </div>
    );
  }

  /* ---------- render: allowed dashboard ---------- */

  const rows = events || [];
  const clicks = rows.filter((r) => r.event_type === 'article_click');
  const outbounds = rows.filter((r) => r.event_type === 'outbound_click');

  const bySource = topRows(countBy(clicks, (r) => r.source));
  const byCategory = topRows(countBy(clicks, (r) => r.category));
  const byWeekday = WEEKDAYS.map((w) => ({
    label: w,
    value: clicks.filter((r) => r.weekday === w).length,
  }));
  const byHour = Array.from({ length: 24 }, (_, h) => ({
    label: `${String(h).padStart(2, '0')}時`,
    value: clicks.filter((r) => r.clicked_hour === h).length,
  })).filter((r) => r.value > 0);
  const byDevice = topRows(
    countBy(clicks, (r) => (r.is_mobile ? '📱 Mobile' : '💻 Desktop') + ' · ' + (r.device_id || '').slice(0, 6)),
    8
  );

  // セクション別クリック数 (0 件含む) → あまり読んでいないカテゴリ算出に使う
  const secCount = countBy(clicks, (r) => r.section);
  const leastRead = SECTIONS
    .map((s) => ({ label: s.label, value: secCount.get(s.slug) || 0 }))
    .sort((a, b) => a.value - b.value)
    .slice(0, 6);

  const recent = clicks.slice(0, 12);
  const longDwell = outbounds
    .filter((r) => (r.estimated_external_dwell_seconds || 0) > 0)
    .sort((a, b) => (b.estimated_external_dwell_seconds || 0) - (a.estimated_external_dwell_seconds || 0))
    .slice(0, 8);

  return (
    <div className="il-wrap">
      <div className="il-head">
        <h1>My Interest</h1>
        <span className="il-eyebrow">直近 {LOOKBACK_DAYS} 日 / 最大 {QUERY_LIMIT} 件</span>
      </div>
      <div className="il-userline">
        <span>● {user?.email}</span>
        {pending > 0 && <span className="il-pending">未送信 {pending} 件（次回自動再送）</span>}
        <button className="il-btn-ghost" onClick={() => loadData()} disabled={loadingData}>
          {loadingData ? '更新中…' : '再読み込み'}
        </button>
        <button className="il-btn-ghost" onClick={() => signOutUser()}>サインアウト</button>
      </div>

      {error && <p className="il-note" style={{ color: '#b00' }}>{error}</p>}

      <div className="il-stats">
        <div className="il-stat"><span className="n">{clicks.length}</span><span className="k">Article clicks</span></div>
        <div className="il-stat"><span className="n">{outbounds.length}</span><span className="k">Outbound</span></div>
        <div className="il-stat"><span className="n">{bySource.length}</span><span className="k">Sources</span></div>
        <div className="il-stat"><span className="n">{new Set(clicks.map((r) => r.device_id)).size}</span><span className="k">Devices</span></div>
      </div>

      <div className="il-grid">
        <div className="il-card">
          <h2>よく読むソース</h2>
          <Bar rows={bySource} />
        </div>
        <div className="il-card">
          <h2>カテゴリ別クリック数</h2>
          <Bar rows={byCategory} />
        </div>
        <div className="il-card">
          <h2>曜日別クリック数</h2>
          <Bar rows={byWeekday} />
        </div>
        <div className="il-card">
          <h2>時間帯別クリック数</h2>
          <Bar rows={byHour} />
        </div>
        <div className="il-card">
          <h2>デバイス別クリック数</h2>
          <Bar rows={byDevice} />
        </div>
        <div className="il-card">
          <h2>あまり読んでいないカテゴリ</h2>
          <Bar rows={leastRead} />
        </div>

        <div className="il-card il-span2">
          <h2>最近クリックした記事</h2>
          {recent.length === 0 ? (
            <p className="il-empty">まだクリック履歴がありません。記事を開くと自動で記録されます。</p>
          ) : (
            <ul className="il-list">
              {recent.map((r, i) => (
                <li key={(r.article_id || '') + i}>
                  <span className="il-src">{r.source}</span> {r.title || r.article_id}
                  <br />
                  <span className="il-meta">{r.issue_date} · {r.clicked_at?.slice(0, 16).replace('T', ' ')}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="il-card il-span2">
          <h2>推定滞留が長い記事 <span className="il-hint">外部サイト滞留の推定値（不正確・上限30分）</span></h2>
          {longDwell.length === 0 ? (
            <p className="il-empty">外部リンクの滞留推定データはまだありません。</p>
          ) : (
            <ul className="il-list">
              {longDwell.map((r, i) => (
                <li key={(r.article_id || '') + i}>
                  <span className="il-src">{r.source}</span> {r.title || r.article_id}
                  <span className="il-meta"> — 約 {Math.round((r.estimated_external_dwell_seconds || 0) / 60)} 分（推定）</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
