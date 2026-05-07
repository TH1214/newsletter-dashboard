import type { MetadataRoute } from 'next';
import { getAllArticles, SECTIONS } from '@/lib/content';

const SITE_URL = 'https://th1214.github.io/newsletter-dashboard';

/**
 * P2.5: 検索エンジン向け sitemap.xml の自動生成
 * - / (TOP)
 * - /archive/
 * - /status/
 * - /sections/<slug>/ (9 sources)
 * - /issues/<date>/<slug>-<date>/ (全記事 ~200+)
 *
 * Next.js 14 App Router の規約に従い、本ファイルは sitemap.xml としてビルド時に生成される。
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const articles = getAllArticles();

  const staticPages: MetadataRoute.Sitemap = [
    {
      url: `${SITE_URL}/`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
    {
      url: `${SITE_URL}/archive/`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/status/`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.5,
    },
  ];

  const sectionPages: MetadataRoute.Sitemap = SECTIONS.map((sec) => ({
    url: `${SITE_URL}/sections/${sec.slug}/`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: 0.8,
  }));

  const articlePages: MetadataRoute.Sitemap = articles.map((art) => ({
    url: `${SITE_URL}/issues/${art.date}/${art.slug}/`,
    lastModified: new Date(art.date + 'T00:00:00Z'),
    changeFrequency: 'monthly' as const,
    priority: 0.7,
  }));

  return [...staticPages, ...sectionPages, ...articlePages];
}
