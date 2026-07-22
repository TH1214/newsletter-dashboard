/* ------------------------------------------------------------------
   My Interest — 共有スナップショットの読み取り専用ビュー
   Firebase を一切 import しない（ログイン不要で表示できる）。
   ------------------------------------------------------------------ */
'use client';

import type { BarRow, InterestSnapshot, SnapReadItem, SnapClickItem } from '@/lib/interest/snapshot';
import './interest.css';

function fmtSecs(s: number): string {
  if (s >= 60) return `${Math.floor(s / 60)}分${s % 60}秒`;
  return `${s}秒`;
}

function Bar({ rows }: { rows: BarRow[] }) {
  if (!rows || rows.length === 0) return <p className="il-empty">データなし</p>;
  const max = Math.max(1, ...rows.map((r) => r.value));
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

function ReadList({ items, withMeta }: { items: SnapReadItem[]; withMeta?: boolean }) {
  if (!items || items.length === 0) return <p className="il-empty">データなし</p>;
  return (
    <ul className="il-list">
      {items.map((r, i) => (
        <li key={r.title + i}>
          <span className="il-title">{r.title}</span>
          <br />
          <span className="il-meta">
            <span className="il-src">{r.source}</span>
            {withMeta && r.date ? <> · {r.date}</> : null}
            {withMeta && r.start ? <> · 読み始め {r.start}</> : null}
            {' · '}{fmtSecs(r.secs)}{withMeta ? '読了' : ''}
            {r.short && <span className="il-short"> · 短時間離脱</span>}
          </span>
          {withMeta && r.tags && r.tags.length > 0 && (
            <div className="il-tags">タグ: {r.tags.join(' / ')}</div>
          )}
        </li>
      ))}
    </ul>
  );
}

function ClickList({ items }: { items: SnapClickItem[] }) {
  if (!items || items.length === 0) return <p className="il-empty">データなし</p>;
  return (
    <ul className="il-list">
      {items.map((r, i) => (
        <li key={r.title + i}>
          <span className="il-title">{r.title}</span>
          <br />
          <span className="il-meta">
            <span className="il-src">{r.source}</span>
            {r.date ? <> · {r.date}</> : null}
            {r.clickedDate ? <> · {r.clickedDate} {r.time}</> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function SnapshotView({ snap }: { snap: InterestSnapshot }) {
  const gen = (() => {
    const d = new Date(snap.generatedAt);
    return isNaN(d.getTime())
      ? snap.generatedAt
      : d.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo', dateStyle: 'medium', timeStyle: 'short' });
  })();

  return (
    <div className="il-wrap">
      <div className="il-head">
        <h1>My Interest</h1>
        <span className="il-eyebrow">共有スナップショット · {gen} 時点 · 読み取り専用</span>
      </div>

      <div className="il-stats">
        <div className="il-stat"><span className="n">{fmtSecs(snap.stats.totalReadSecs)}</span><span className="k">合計読書時間</span></div>
        <div className="il-stat"><span className="n">{snap.stats.reads}</span><span className="k">読書セッション</span></div>
        <div className="il-stat"><span className="n">{fmtSecs(snap.stats.avgReadSecs)}</span><span className="k">平均読書時間</span></div>
        <div className="il-stat"><span className="n">{snap.stats.sources}</span><span className="k">読んだソース</span></div>
      </div>

      <div className="il-grid">
        <div className="il-card il-span2">
          <h2>最近読んだ記事 <span className="il-hint">読書セッション</span></h2>
          <ReadList items={snap.recentReads} withMeta />
        </div>

        <div className="il-card"><h2>ソース別 合計読書時間 <span className="il-hint">秒</span></h2><Bar rows={snap.bySourceSecs} /></div>
        <div className="il-card"><h2>カテゴリ別 合計読書時間 <span className="il-hint">秒</span></h2><Bar rows={snap.byCategorySecs} /></div>
        <div className="il-card"><h2>タグ別 合計読書時間 <span className="il-hint">秒</span></h2><Bar rows={snap.byTagSecs} /></div>
        <div className="il-card"><h2>デバイス別 合計読書時間 <span className="il-hint">秒</span></h2><Bar rows={snap.byDeviceSecs} /></div>
        <div className="il-card"><h2>曜日別 合計読書時間 <span className="il-hint">秒</span></h2><Bar rows={snap.byWeekdaySecs} /></div>
        <div className="il-card"><h2>時間帯別 合計読書時間 <span className="il-hint">秒</span></h2><Bar rows={snap.byHourSecs} /></div>

        <div className="il-card"><h2>読書時間が長い記事</h2><ReadList items={snap.longReads} /></div>
        <div className="il-card"><h2>クリックしたが短時間で離脱</h2><ReadList items={snap.shortLeave} /></div>

        <div className="il-card"><h2>クリック数（ソース別） <span className="il-hint">入口ログ</span></h2><Bar rows={snap.byClickSource} /></div>
        <div className="il-card il-span2">
          <h2>最近クリックした記事 <span className="il-hint">記事カードを開いた履歴</span></h2>
          <ClickList items={snap.recentClicks} />
        </div>
      </div>
    </div>
  );
}
