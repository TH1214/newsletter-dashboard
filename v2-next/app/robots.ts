import type { MetadataRoute } from 'next';

/**
 * P2.5: robots.txt の自動生成
 * - 全クローラーに公開 (private / pro 領域は無し)
 * - sitemap.xml の場所を明示
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
      },
    ],
    sitemap: 'https://th1214.github.io/newsletter-dashboard/sitemap.xml',
  };
}
