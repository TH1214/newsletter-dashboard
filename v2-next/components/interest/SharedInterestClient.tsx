'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { decodeSnapshot, type InterestSnapshot } from '@/lib/interest/snapshot';
import { SnapshotView } from './SnapshotView';
import './interest.css';

export function SharedInterestClient() {
  const [snap, setSnap] = useState<InterestSnapshot | null>(null);
  const [state, setState] = useState<'loading' | 'ok' | 'empty' | 'bad'>('loading');

  useEffect(() => {
    const raw = (typeof window !== 'undefined' ? window.location.hash : '').replace(/^#/, '');
    if (!raw) {
      setState('empty');
      return;
    }
    const s = decodeSnapshot(raw);
    if (s) {
      setSnap(s);
      setState('ok');
    } else {
      setState('bad');
    }
  }, []);

  if (state === 'loading') {
    return <div className="il-wrap"><div className="il-head"><h1>My Interest</h1></div><p className="il-note">読み込み中…</p></div>;
  }

  if (state === 'empty' || state === 'bad') {
    return (
      <div className="il-wrap">
        <div className="il-head"><h1>My Interest</h1><span className="il-eyebrow">共有スナップショット</span></div>
        <div className="il-signin">
          <p>
            {state === 'empty'
              ? '共有データが見つかりません。共有リンクは末尾に「#…」のデータが付いた URL 全体が必要です。'
              : '共有データを読み取れませんでした。リンクが途中で切れている可能性があります（URL 全体をコピーして開いてください）。'}
          </p>
          <p className="il-note">
            <Link href="/" className="il-src">← Bolgheri Daily Brief トップへ</Link>
          </p>
        </div>
      </div>
    );
  }

  return <SnapshotView snap={snap!} />;
}
