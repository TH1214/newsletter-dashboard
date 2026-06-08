/* ------------------------------------------------------------------
   ArticleDwellTracker — 記事詳細ページの「Dashboard 滞留時間」計測 (client)

   記事詳細ページにだけマウントする。
   - 表示中の経過時間 (タブが見えている間だけ) を秒で積算
   - 離脱時 (visibility hidden / pagehide / アンマウント) に
     dashboard_dwell_seconds として、対応する article_click doc に追記する
   - list→detail の SPA 遷移なら consumeClickRef で同じ doc に紐付け、
     直接着地 (リロード/外部リンク) なら新規 article_click を1件記録してそこに追記

   onSnapshot は使わない。書き込みは離脱時のみ (best-effort)。
   ------------------------------------------------------------------ */
'use client';

import { useEffect } from 'react';
import {
  consumeClickRef,
  recordEvent,
  writeDwellSeconds,
  type ReadingEventMeta,
} from '@/lib/interest/logger';

export function ArticleDwellTracker({ meta }: { meta: ReadingEventMeta }) {
  useEffect(() => {
    let eventIdPromise: Promise<string | null>;
    const existing = meta.article_id ? consumeClickRef(meta.article_id) : null;
    if (existing) {
      eventIdPromise = Promise.resolve(existing);
    } else {
      // 直接着地: この閲覧自体を article_click として1件記録し、それに滞留を追記
      eventIdPromise = recordEvent('article_click', meta, { dedupeKey: meta.article_id }).then(
        (r) => r?.event.event_id ?? null
      );
    }

    let activeMs = 0;
    let lastStart: number | null =
      typeof document !== 'undefined' && document.visibilityState === 'visible' ? Date.now() : null;
    let lastWritten = 0;

    const accumulate = () => {
      if (lastStart != null) {
        activeMs += Date.now() - lastStart;
        lastStart = null;
      }
    };

    const flush = async () => {
      accumulate();
      const seconds = Math.round(activeMs / 1000);
      if (seconds <= 0 || seconds === lastWritten) return;
      lastWritten = seconds;
      const id = await eventIdPromise;
      if (id) await writeDwellSeconds(id, 'dashboard_dwell_seconds', seconds);
    };

    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        void flush();
      } else {
        lastStart = Date.now();
      }
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', flush);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', flush);
      void flush(); // ルート遷移でアンマウントされた時点で確定
    };
    // meta は記事ごとに固定。article_id をキーに再マウントさせる
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta.article_id]);

  return null;
}
