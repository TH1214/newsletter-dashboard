/* ------------------------------------------------------------------
   ArticleDwellTracker — 記事詳細ページの読書セッション (= 最重要ログ)

   記事詳細ページにだけマウントする。
   - 開いた時点で article_detail_read document を作成 (スナップショット付き)
   - 表示中の経過秒を積算し、離脱時 (visibilitychange hidden / pagehide /
     beforeunload / アンマウント=route change) に dashboard_dwell_seconds を更新
   - 「その時点の記事内容」(title/summary/body_text/tags/source/section/
     issue_date/url) をスナップショット保存し、将来 CMS が変わっても再現可能にする
   - 本文は表示中の .wb-art-body のテキストを採用 (プレーン, 最大 SNAPSHOT_MAX_CHARS)

   onSnapshot は使わない。書き込みは開始時＋離脱時のみ。
   ------------------------------------------------------------------ */
'use client';

import { useEffect } from 'react';
import {
  buildReadSessionId,
  upsertReadSession,
  type ArticleSnapshot,
} from '@/lib/interest/logger';
import { SNAPSHOT_MAX_CHARS } from '@/lib/interest/config';

export interface ReadTrackerMeta {
  article_id: string;
  title: string;          // 表示タイトル (= summary を解決済み)
  summary: string;
  source: string;
  section: string;
  category: string;
  issue_date: string;
  article_url: string;
  tags: string[];
}

export function ArticleDwellTracker({ meta }: { meta: ReadTrackerMeta }) {
  useEffect(() => {
    const articleId = meta.article_id;
    if (!articleId) return;
    const readId = buildReadSessionId(articleId);

    // --- その時点の記事スナップショット ---
    const bodyText = (
      (document.querySelector('.wb-art-body') as HTMLElement | null)?.innerText || ''
    )
      .replace(/\n{3,}/g, '\n\n')
      .trim()
      .slice(0, SNAPSHOT_MAX_CHARS);
    const capturedAt = new Date().toISOString();
    const snapshot: ArticleSnapshot = {
      article_snapshot_title: meta.title,
      article_snapshot_summary: meta.summary,
      article_snapshot_body_text: bodyText,
      article_snapshot_source: meta.source,
      article_snapshot_section: meta.section,
      article_snapshot_category: meta.category,
      article_snapshot_tags: meta.tags,
      article_snapshot_issue_date: meta.issue_date,
      article_snapshot_url: meta.article_url,
      article_snapshot_captured_at: capturedAt,
    };

    const base = {
      article_id: articleId,
      title: meta.title,
      source: meta.source,
      section: meta.section,
      category: meta.category,
      tags: meta.tags,
      issue_date: meta.issue_date,
      article_url: meta.article_url,
    };

    // --- 滞留秒数 (同 session の再訪は積算) ---
    const startKey = `il_read_start_${readId}`;
    const secsKey = `il_read_secs_${readId}`;
    let startedAt = '';
    try {
      startedAt = sessionStorage.getItem(startKey) || '';
      if (!startedAt) {
        startedAt = capturedAt;
        sessionStorage.setItem(startKey, startedAt);
      }
    } catch {
      startedAt = capturedAt;
    }
    let prevSecs = 0;
    try {
      prevSecs = parseInt(sessionStorage.getItem(secsKey) || '0', 10) || 0;
    } catch {
      prevSecs = 0;
    }

    let activeMs = 0;
    let lastStart: number | null = document.visibilityState === 'visible' ? Date.now() : null;
    let lastWritten = -1;

    const totalSecs = () => prevSecs + Math.round(activeMs / 1000);

    // 開始時に作成 (スナップショット付き)
    void upsertReadSession(readId, {
      ...base,
      read_started_at: startedAt,
      read_ended_at: capturedAt,
      dashboard_dwell_seconds: prevSecs,
      snapshot,
    });

    const flush = () => {
      if (lastStart != null) {
        activeMs += Date.now() - lastStart;
        lastStart = document.visibilityState === 'visible' ? Date.now() : null;
      }
      const secs = totalSecs();
      try {
        sessionStorage.setItem(secsKey, String(secs));
      } catch {
        /* ignore */
      }
      if (secs === lastWritten) return;
      lastWritten = secs;
      // 以降は dwell + 終了時刻のみ更新 (スナップショットは初回で保存済み)
      void upsertReadSession(readId, {
        ...base,
        read_started_at: startedAt,
        read_ended_at: new Date().toISOString(),
        dashboard_dwell_seconds: secs,
      });
    };

    const onVisibility = () => {
      if (document.visibilityState === 'hidden') flush();
      else lastStart = Date.now();
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', flush);
    window.addEventListener('beforeunload', flush);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', flush);
      window.removeEventListener('beforeunload', flush);
      flush(); // route change によるアンマウントで確定
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta.article_id]);

  return null;
}
