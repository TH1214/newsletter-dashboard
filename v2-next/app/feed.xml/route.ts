import { getAllArticles, getSectionInfo } from '@/lib/content';

export const dynamic = 'force-static';

const SITE_URL = 'https://th1214.github.io/newsletter-dashboard';
const SITE_TITLE = 'Bolgheri Daily Brief';
const SITE_DESCRIPTION =
  '海外メディア (NYT / WSJ / FT / The Economist 等) の記事を AI が編集・要約・解釈して日本語読者に届ける、静謐な雑誌的プロダクト。毎朝 06:00 JST 配信。';
const FEED_AUTHOR = 'Bolgheri AI';

/**
 * P3 #6 (v3.2.2): RSS 2.0 feed 自動生成
 * URL: /newsletter-dashboard/feed.xml
 *
 * 直近 50 記事を pubDate 降順で配信。
 * RSS reader (Feedly / Inoreader / NetNewsWire 等) で購読可能。
 */
function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function rfc822(dateStr: string): string {
  // YYYY-MM-DD → RFC 822 形式 (06:00 JST 配信時刻として固定)
  // 例: "Wed, 07 May 2026 06:00:00 +0900"
  const d = new Date(dateStr + 'T06:00:00+09:00');
  return d.toUTCString().replace('GMT', '+0000');
}

export async function GET(): Promise<Response> {
  const articles = getAllArticles().slice(0, 50); // 直近 50 記事

  const lastBuildDate = articles.length > 0 ? rfc822(articles[0].date) : new Date().toUTCString();

  const items = articles.map((art) => {
    const section = getSectionInfo(art.section);
    const link = `${SITE_URL}/issues/${art.date}/${art.slug}/`;
    const sectionLabel = section?.label ?? art.section;
    return `    <item>
      <title>${escapeXml(art.title)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${rfc822(art.date)}</pubDate>
      <category>${escapeXml(sectionLabel)}</category>
      <description>${escapeXml(art.summary || `${sectionLabel} - ${art.date}`)}</description>
    </item>`;
  }).join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(SITE_TITLE)}</title>
    <link>${SITE_URL}/</link>
    <description>${escapeXml(SITE_DESCRIPTION)}</description>
    <language>ja</language>
    <managingEditor>noreply@bolgheri.example (${escapeXml(FEED_AUTHOR)})</managingEditor>
    <copyright>© Bolgheri Limited</copyright>
    <generator>Next.js 14 (Bolgheri Daily Brief)</generator>
    <ttl>360</ttl>
    <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  });
}
