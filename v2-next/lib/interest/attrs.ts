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
  title: string;       // CMS の title は "{SourceLabel}｜YYYY年MM月DD日" (= source+date)
  summary?: string;    // 実質的な「記事タイトル」= 1行要約。表示タイトルに採用する
  tags?: string[];
}

/**
 * 表示用タイトルの解決。
 * この CMS の `title` は「ソース名＋日付」で個別見出しが無いため、
 * 意味のある summary を優先する。source/section/category 名は title にしない。
 *   優先: 1. summary  →  2. titleClean (｜以降を除去)  →  3. article_id
 */
export function resolveDisplayTitle(meta: { title?: string; summary?: string; slug?: string }): string {
  const summary = (meta.summary || '').trim();
  if (summary) return summary;
  const titleClean = (meta.title || '').split('｜')[0].split('|')[0].trim();
  if (titleClean) return titleClean;
  return meta.slug || '';
}

/**
 * 記事リンク用の data-* 属性オブジェクト。
 * `<Link {...articleLinkAttrs(meta)} ... />` の形で展開する。
 */
export function articleLinkAttrs(meta: ArticleLinkMeta): Record<string, string> {
  const sec = getSectionInfo(meta.section);
  const category = (meta.tags && meta.tags[0]) || sec.eyebrow.split('·')[0].trim();
  return {
    'data-il': 'article',
    'data-il-id': meta.slug,
    'data-il-title': resolveDisplayTitle(meta),   // = 実質タイトル (summary)
    'data-il-source': sec.label,                  // = NYT DealBook / WSJ など
    'data-il-section': meta.section,              // = dealbook / wsj など slug
    'data-il-category': category,                 // = AI / 金融 など tag
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
