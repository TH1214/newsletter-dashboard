/* ------------------------------------------------------------------
   Article link data attributes (pure — server & client safe)

   記事カードの <Link> / <a> に展開して付与する data-* 属性を生成する。
   グローバルなクリック委譲ハンドラ (InterestLogger) が dataset から
   メタデータを読み取るため、テンプレートを大改修せず属性付与だけで済む。

   NOTE: getSectionInfo は lib/sections (純データ) 由来なので
         server component から呼んでも安全。
   ------------------------------------------------------------------ */
import { getSectionInfo, type SectionSlug } from '../sections';

export interface ArticleLinkMeta {
  slug: string;        // article_id (= "{section}-YYYY-MM-DD")
  section: SectionSlug;
  date: string;        // issue_date (YYYY-MM-DD)
  title: string;
  tags?: string[];
}

/**
 * 記事リンク用の data-* 属性オブジェクト。
 * `<Link {...articleLinkAttrs(meta)} ... />` の形で展開する。
 */
export function articleLinkAttrs(meta: ArticleLinkMeta): Record<string, string> {
  const sec = getSectionInfo(meta.section);
  const titleClean = meta.title.split('｜')[0].split('|')[0].trim();
  const category = (meta.tags && meta.tags[0]) || sec.eyebrow.split('·')[0].trim();
  return {
    'data-il': 'article',
    'data-il-id': meta.slug,
    'data-il-title': titleClean,
    'data-il-source': sec.label,
    'data-il-section': meta.section,
    'data-il-category': category,
    'data-il-issue-date': meta.date,
    'data-il-url': `/issues/${meta.date}/${meta.slug}/`,
  };
}

/**
 * 外部 (原文) リンク用の data-* 属性。outbound_click + 外部滞留推定の対象。
 */
export function outboundLinkAttrs(meta: ArticleLinkMeta, url: string): Record<string, string> {
  const base = articleLinkAttrs(meta);
  return {
    ...base,
    'data-il': 'outbound',
    'data-il-url': url,
  };
}
