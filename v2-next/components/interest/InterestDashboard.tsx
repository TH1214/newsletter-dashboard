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
  SHORT_READ_SECONDS,
} from '@/lib/interest/config';
import {
  setCurrentUser,
  recordEvent,
  getQueueCount,
  flushQueue,
  flushReadSessions,
} from '@/lib/interest/logger';
import { encodeSnapshot, type InterestSnapshot } from '@/lib/interest/snapshot';
import './interest.css';

interface EventRow {
  event_type?: string;
  article_id?: string;
  title?: string;
  source?: string;
  category?: string;
  section?: string;
  tags?: string[];
  issue_date?: string;
  clicked_at?: string;
  clicked_date?: string;
  clicked_hour?: number;
  weekday?: string;
  device_id?: string;
  is_mobile?: boolean;
  dashboard_dwell_seconds?: number;
  estimated_external_dwell_seconds?: number;
  read_started_at?: string;
  read_ended_at?: string;
  updated_at?: string;
  // その時点の記事スナップショット
  article_snapshot_title?: string;
  article_snapshot_summary?: string;
  article_snapshot_body_text?: string;
  article_snapshot_source?: string;
  article_snapshot_section?: string;
  article_snapshot_category?: string;
  article_snapshot_tags?: string[];
  article_snapshot_issue_date?: string;
}

/** ビルド時に生成する記事カタログ (article_id → 現行の表示情報)。過去ログのタイトル補完に使う。 */
export type ArticleCatalog = Record<
  string,
  { title: string; source: string; section: string; category: string }
>;

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

function topRows(m: Map<string, number>, n = 12) {
  return [...m.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([label, value]) => ({ label, value }));
}

/** イベントの表示用フィールドを解決。優先: スナップショット → カタログ補完 → イベント値。 */
function resolveDisplay(r: EventRow, catalog: ArticleCatalog) {
  const cat = (r.article_id && catalog[r.article_id]) || undefined;
  const rawTitle = (r.title || '').trim();
  const looksLikeSourceName = !!(cat && (rawTitle === cat.source || rawTitle === cat.section));
  const title =
    (r.article_snapshot_title || '').trim() ||
    cat?.title ||
    (rawTitle && !looksLikeSourceName ? rawTitle : '') ||
    r.article_id ||
    '(無題)';
  const tags = (r.article_snapshot_tags && r.article_snapshot_tags.length
    ? r.article_snapshot_tags
    : r.tags) || [];
  return {
    title,
    source: r.article_snapshot_source || cat?.source || r.source || '',
    section: r.article_snapshot_section || cat?.section || r.section || '',
    category: r.article_snapshot_category || cat?.category || r.category || '',
    tags,
    bodyText: r.article_snapshot_body_text || '',
  };
}

/** 読書秒数 (Dashboard滞留)。 */
function readSecs(r: EventRow): number {
  return r.dashboard_dwell_seconds || 0;
}

/** イベントの代表時刻 (読了時刻 → クリック時刻)。 */
function eventTime(r: EventRow): string {
  return r.read_ended_at || r.updated_at || r.clicked_at || '';
}

/** 秒の表示整形。 */
function fmtSecs(s: number): string {
  if (s >= 60) return `${Math.floor(s / 60)}分${s % 60}秒`;
  return `${s}秒`;
}

/** 読み始めた時刻を「M/D HH:MM」(JST)で表示。無ければ空。 */
function fmtReadStart(r: EventRow): string {
  const iso = r.read_started_at || r.clicked_at || r.updated_at || '';
  if (!iso) return '';
  const dt = new Date(iso);
  if (isNaN(dt.getTime())) return '';
  return dt.toLocaleString('ja-JP', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/** keyFn ごとに値(秒など)を合計。 */
function sumBy(rows: EventRow[], key: (r: EventRow) => string | undefined, val: (r: EventRow) => number) {
  const m = new Map<string, number>();
  for (const r of rows) {
    const k = key(r);
    if (!k) continue;
    m.set(k, (m.get(k) || 0) + val(r));
  }
  return m;
}

export function InterestDashboard({ catalog = {} }: { catalog?: ArticleCatalog }) {
  const [auth, setAuth] = useState<AuthState>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [events, setEvents] = useState<EventRow[] | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [shareMsg, setShareMsg] = useState<string>('');

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
      await flushReadSessions();
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

  /* ---------- render: allowed dashboard (読書時間中心) ---------- */

  const rows = events || [];
  const reads = rows.filter((r) => r.event_type === 'article_detail_read'); // 主分析対象
  const clicks = rows.filter((r) => r.event_type === 'article_click');       // 入口ログ (補助)
  const outbounds = rows.filter((r) => r.event_type === 'outbound_click');   // 外部 (補助)

  // --- 読書秒数ベースの集計 ---
  const bySourceSecs = topRows(sumBy(reads, (r) => resolveDisplay(r, catalog).source, readSecs));
  const byCategorySecs = topRows(sumBy(reads, (r) => resolveDisplay(r, catalog).category, readSecs));
  const byWeekdaySecs = WEEKDAYS.map((w) => ({
    label: w,
    value: reads.filter((r) => r.weekday === w).reduce((s, r) => s + readSecs(r), 0),
  }));
  const byHourSecs = Array.from({ length: 24 }, (_, h) => ({
    label: `${String(h).padStart(2, '0')}時`,
    value: reads.filter((r) => r.clicked_hour === h).reduce((s, r) => s + readSecs(r), 0),
  })).filter((r) => r.value > 0);
  const byDeviceSecs = topRows(
    sumBy(reads, (r) => (r.is_mobile ? '📱 Mobile' : '💻 Desktop') + ' · ' + (r.device_id || '').slice(0, 6), readSecs),
    8
  );

  // タグ別 読書秒数
  const tagMap = new Map<string, number>();
  for (const r of reads) {
    const s = readSecs(r);
    for (const t of resolveDisplay(r, catalog).tags) {
      if (!t) continue;
      tagMap.set(t, (tagMap.get(t) || 0) + s);
    }
  }
  const byTagSecs = topRows(tagMap);

  const totalReadSecs = reads.reduce((s, r) => s + readSecs(r), 0);
  const avgReadSecs = reads.length ? Math.round(totalReadSecs / reads.length) : 0;

  // クリック履歴 (入口ログ) — 記録は InterestLogger が article_click で実施済み
  const recentClicks = clicks.slice().sort((a, b) => (eventTime(a) < eventTime(b) ? 1 : -1)).slice(0, 15);
  const byClickSource = topRows(sumBy(clicks, (r) => resolveDisplay(r, catalog).source, () => 1));

  const recentReads = reads.slice().sort((a, b) => (eventTime(a) < eventTime(b) ? 1 : -1)).slice(0, 15);
  const longReads = reads.filter((r) => readSecs(r) > 0).sort((a, b) => readSecs(b) - readSecs(a)).slice(0, 10);
  const shortLeave = reads
    .filter((r) => readSecs(r) < SHORT_READ_SECONDS)
    .sort((a, b) => readSecs(a) - readSecs(b))
    .slice(0, 10);
  const recentOutbounds = outbounds
    .slice()
    .sort((a, b) => (eventTime(a) < eventTime(b) ? 1 : -1))
    .slice(0, 8);

  // --- 友人共有: その時点の集計を凍結スナップショット化して read-only リンクを作る ---
  const buildSnapshot = (): InterestSnapshot => ({
    v: 1,
    generatedAt: new Date().toISOString(),
    lookbackDays: LOOKBACK_DAYS,
    stats: { totalReadSecs, reads: reads.length, avgReadSecs, sources: bySourceSecs.length },
    bySourceSecs,
    byCategorySecs,
    byTagSecs,
    byDeviceSecs,
    byWeekdaySecs,
    byHourSecs,
    byClickSource,
    recentReads: recentReads.slice(0, 12).map((r) => {
      const d = resolveDisplay(r, catalog);
      return {
        title: d.title.slice(0, 90),
        source: d.source,
        date: r.issue_date,
        start: fmtReadStart(r),
        secs: readSecs(r),
        short: readSecs(r) < SHORT_READ_SECONDS,
        tags: d.tags.slice(0, 5),
      };
    }),
    longReads: longReads.slice(0, 10).map((r) => {
      const d = resolveDisplay(r, catalog);
      return { title: d.title.slice(0, 90), source: d.source, secs: readSecs(r) };
    }),
    shortLeave: shortLeave.slice(0, 10).map((r) => {
      const d = resolveDisplay(r, catalog);
      return { title: d.title.slice(0, 90), source: d.source, secs: readSecs(r) };
    }),
    recentClicks: recentClicks.slice(0, 12).map((r) => {
      const d = resolveDisplay(r, catalog);
      return {
        title: d.title.slice(0, 90),
        source: d.source,
        date: r.issue_date,
        clickedDate: r.clicked_date,
        time: (r.clicked_at || '').slice(11, 16),
      };
    }),
  });

  const onShare = async () => {
    try {
      const enc = encodeSnapshot(buildSnapshot());
      const base = location.href.split('/interest')[0];
      const url = `${base}/interest/shared/#${enc}`;
      let copied = false;
      try {
        await navigator.clipboard.writeText(url);
        copied = true;
      } catch {
        copied = false;
      }
      setShareMsg(
        copied
          ? `共有リンクをコピーしました（読み取り専用スナップショット · 約${Math.max(1, Math.round(url.length / 1024))}KB）。友人に送ってください。`
          : `コピーできませんでした。次のURL全体を手動でコピーしてください:\n${url}`,
      );
    } catch {
      setShareMsg('共有リンクの生成に失敗しました。再読み込み後にお試しください。');
    }
  };

  return (
    <div className="il-wrap">
      <div className="il-head">
        <h1>My Interest</h1>
        <span className="il-eyebrow">直近 {LOOKBACK_DAYS} 日 / 最大 {QUERY_LIMIT} 件 · 読書時間ベース</span>
      </div>
      <div className="il-userline">
        <span>● {user?.email}</span>
        {pending > 0 && <span className="il-pending">未送信 {pending} 件（次回自動再送）</span>}
        <button className="il-btn-ghost" onClick={() => loadData()} disabled={loadingData}>
          {loadingData ? '更新中…' : '再読み込み'}
        </button>
        <button
          className="il-btn-ghost"
          onClick={onShare}
          disabled={loadingData || reads.length + clicks.length === 0}
          title="その時点の集計を読み取り専用リンクにして友人に共有します（ログイン不要）"
        >
          友人に共有リンクを作成
        </button>
        <button className="il-btn-ghost" onClick={() => signOutUser()}>サインアウト</button>
      </div>

      {shareMsg && <p className="il-note" style={{ whiteSpace: 'pre-wrap', color: 'var(--signal)' }}>{shareMsg}</p>}
      {error && <p className="il-note" style={{ color: '#b00' }}>{error}</p>}

      <div className="il-stats">
        <div className="il-stat"><span className="n">{fmtSecs(totalReadSecs)}</span><span className="k">合計読書時間</span></div>
        <div className="il-stat"><span className="n">{reads.length}</span><span className="k">読書セッション</span></div>
        <div className="il-stat"><span className="n">{fmtSecs(avgReadSecs)}</span><span className="k">平均読書時間</span></div>
        <div className="il-stat"><span className="n">{bySourceSecs.length}</span><span className="k">読んだソース</span></div>
      </div>

      {/* === 主表示: 最近読んだ記事 === */}
      <div className="il-grid">
        <div className="il-card il-span2">
          <h2>最近読んだ記事 <span className="il-hint">記事詳細ページの読書セッション</span></h2>
          {recentReads.length === 0 ? (
            <p className="il-empty">まだ読書記録がありません。記事詳細ページを開くと自動で記録されます。</p>
          ) : (
            <ul className="il-list">
              {recentReads.map((r, i) => {
                const d = resolveDisplay(r, catalog);
                return (
                  <li key={(r.article_id || '') + i}>
                    <span className="il-title">{d.title}</span>
                    <br />
                    <span className="il-meta">
                      <span className="il-src">{d.source}</span> · {r.issue_date}
                      {fmtReadStart(r) && <> · 読み始め {fmtReadStart(r)}</>} · {fmtSecs(readSecs(r))}読了
                      {readSecs(r) < SHORT_READ_SECONDS && <span className="il-short"> · 短時間離脱</span>}
                    </span>
                    {d.tags.length > 0 && <div className="il-tags">タグ: {d.tags.join(' / ')}</div>}
                    {d.bodyText ? (
                      <details className="il-snap">
                        <summary>本文スナップショットあり（クリックで表示）</summary>
                        <pre className="il-snap-body">{d.bodyText}</pre>
                      </details>
                    ) : (
                      <div className="il-meta">本文スナップショット: なし</div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* === 集計 (読書秒数ベース) === */}
        <div className="il-card">
          <h2>ソース別 合計読書時間 <span className="il-hint">秒</span></h2>
          <Bar rows={bySourceSecs} />
        </div>
        <div className="il-card">
          <h2>カテゴリ別 合計読書時間 <span className="il-hint">秒</span></h2>
          <Bar rows={byCategorySecs} />
        </div>
        <div className="il-card">
          <h2>タグ別 合計読書時間 <span className="il-hint">秒</span></h2>
          <Bar rows={byTagSecs} />
        </div>
        <div className="il-card">
          <h2>デバイス別 合計読書時間 <span className="il-hint">秒</span></h2>
          <Bar rows={byDeviceSecs} />
        </div>
        <div className="il-card">
          <h2>曜日別 合計読書時間 <span className="il-hint">秒</span></h2>
          <Bar rows={byWeekdaySecs} />
        </div>
        <div className="il-card">
          <h2>時間帯別 合計読書時間 <span className="il-hint">秒</span></h2>
          <Bar rows={byHourSecs} />
        </div>

        <div className="il-card">
          <h2>読書時間が長い記事</h2>
          {longReads.length === 0 ? (
            <p className="il-empty">データなし</p>
          ) : (
            <ul className="il-list">
              {longReads.map((r, i) => {
                const d = resolveDisplay(r, catalog);
                return (
                  <li key={(r.article_id || '') + i}>
                    <span className="il-title">{d.title}</span>
                    <br />
                    <span className="il-meta"><span className="il-src">{d.source}</span> · {fmtSecs(readSecs(r))}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="il-card">
          <h2>クリックしたが短時間で離脱 <span className="il-hint">{SHORT_READ_SECONDS}秒未満</span></h2>
          {shortLeave.length === 0 ? (
            <p className="il-empty">データなし</p>
          ) : (
            <ul className="il-list">
              {shortLeave.map((r, i) => {
                const d = resolveDisplay(r, catalog);
                return (
                  <li key={(r.article_id || '') + i}>
                    <span className="il-title">{d.title}</span>
                    <br />
                    <span className="il-meta"><span className="il-src">{d.source}</span> · {fmtSecs(readSecs(r))}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* === クリック履歴 (入口ログ) === */}
        <div className="il-card">
          <h2>クリック数（ソース別） <span className="il-hint">入口ログ</span></h2>
          <Bar rows={byClickSource} />
        </div>

        <div className="il-card il-span2">
          <h2>最近クリックした記事 <span className="il-hint">一覧/トップで記事カードを開いた履歴</span></h2>
          {recentClicks.length === 0 ? (
            <p className="il-empty">まだクリック履歴がありません。記事カードを押すと記録されます。</p>
          ) : (
            <ul className="il-list">
              {recentClicks.map((r, i) => {
                const d = resolveDisplay(r, catalog);
                const time = (r.clicked_at || '').slice(11, 16);
                return (
                  <li key={(r.article_id || '') + i}>
                    <span className="il-title">{d.title}</span>
                    <br />
                    <span className="il-meta">
                      <span className="il-src">{d.source}</span> · {r.issue_date} · {r.clicked_date} {time}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* === 補助: 外部リンククリック === */}
        <div className="il-card il-span2">
          <h2>外部原文クリック（補助） <span className="il-hint">クリック {clicks.length} 件 / 外部 {outbounds.length} 件 · 推定外部滞留は不正確・上限30分</span></h2>
          {recentOutbounds.length === 0 ? (
            <p className="il-empty">外部原文へのクリックはまだありません。</p>
          ) : (
            <ul className="il-list">
              {recentOutbounds.map((r, i) => {
                const d = resolveDisplay(r, catalog);
                const ext = r.estimated_external_dwell_seconds || 0;
                return (
                  <li key={(r.article_id || '') + i}>
                    <span className="il-title">{d.title}</span>
                    <br />
                    <span className="il-meta">
                      <span className="il-src">{d.source}</span> · {ext > 0 ? `推定外部滞留 ${fmtSecs(ext)}（推定）` : '推定外部滞留 未計測'}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
