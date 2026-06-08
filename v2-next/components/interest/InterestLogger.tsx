/* ------------------------------------------------------------------
   InterestLogger — 全ページ共通でマウントされるクリック記録ランナー

   app/layout.tsx に1つだけ置く (renders null)。
   - auth 状態を監視し、許可メールでログイン済みのときだけ記録/再送
   - 記事カード ([data-il="article"]) クリック → article_click を1書き込み
   - 外部リンク ([data-il="outbound"]) クリック → outbound_click + 滞留計測開始
   - 次回ロード / ログイン完了 / online 復帰 / Dashboard 復帰時に pending queue を自動再送
   - Dashboard 復帰時に外部滞留の推定値を解決

   onSnapshot は使わない。書き込みはクリック時のみ。
   ------------------------------------------------------------------ */
'use client';

import { useEffect } from 'react';
import { watchAuth } from '@/lib/interest/firebaseClient';
import {
  getDeviceId,
  getSessionId,
  setCurrentUser,
  recordEvent,
  recordOutboundClick,
  flushQueue,
  resolveExternalDwell,
  type ReadingEventMeta,
} from '@/lib/interest/logger';

function metaFromElement(el: HTMLElement): ReadingEventMeta {
  const d = el.dataset;
  return {
    article_id: d.ilId,
    title: d.ilTitle,
    source: d.ilSource,
    category: d.ilCategory,
    section: d.ilSection,
    issue_date: d.ilIssueDate,
    article_url: d.ilUrl,
  };
}

export function InterestLogger() {
  useEffect(() => {
    // 端末識別子を初期化 (どの端末からでも自動記録)
    getDeviceId();
    getSessionId();

    // --- auth 監視: ログイン状態が変わるたびに current user を更新し再送 ---
    const unsub = watchAuth(async (user) => {
      setCurrentUser(user);
      // ログイン完了時に未送信キューを自動再送 (ユーザー操作不要)
      await flushQueue();
    });

    // --- クリック委譲: 記事カード / 外部リンク ---
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const node = target.closest<HTMLElement>('[data-il]');
      if (!node) return;
      const kind = node.dataset.il;
      const meta = metaFromElement(node);
      if (kind === 'outbound') {
        // 外部サイトへ離脱 → outbound_click + 滞留計測開始 (await 不要・取りこぼし防止に write-ahead 済み)
        void recordOutboundClick({ ...meta, referrer_type: 'outbound' });
      } else if (kind === 'article') {
        // 記事リンク = 主イベント (1クリック1書き込み)
        void recordEvent('article_click', meta, { dedupeKey: meta.article_id });
      }
    };
    document.addEventListener('click', onClick, { capture: true });

    // --- 復帰系: 外部滞留の解決 + 自動再送 ---
    const onReturn = async () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
      await resolveExternalDwell();
      await flushQueue();
    };
    document.addEventListener('visibilitychange', onReturn);
    window.addEventListener('focus', onReturn);
    window.addEventListener('pageshow', onReturn);
    // online 復帰時にも自動再送
    const onOnline = () => void flushQueue();
    window.addEventListener('online', onOnline);

    // 初回ロード時にも一度再送を試みる (前回失敗分の自動リカバリ)
    void flushQueue();

    return () => {
      unsub();
      document.removeEventListener('click', onClick, { capture: true } as EventListenerOptions);
      document.removeEventListener('visibilitychange', onReturn);
      window.removeEventListener('focus', onReturn);
      window.removeEventListener('pageshow', onReturn);
      window.removeEventListener('online', onOnline);
    };
  }, []);

  return null;
}
