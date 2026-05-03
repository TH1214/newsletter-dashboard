import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { remark } from 'remark';
import remarkGfm from 'remark-gfm';
import remarkHtml from 'remark-html';
import { SECTIONS, type SectionSlug } from './sections';

/* ------------------------------------------------------------------
   Source-of-truth: Hugo content/ + static/images/ are bundled into
   this Next.js project under /content and /public/images/.
   SECTIONS / SectionSlug are now defined in ./sections (pure data).
   ------------------------------------------------------------------ */
export { SECTIONS, type SectionSlug, getSectionInfo } from './sections';

const CONTENT_ROOT = path.join(process.cwd(), 'content');

export interface Article {
  section: SectionSlug;
  date: string;          // YYYY-MM-DD
  slug: string;          // section-YYYY-MM-DD
  title: string;
  summary: string;
  tags: string[];
  heroImage: string;     // public-served path: /images/<section>/<date>.png
  originalUrl: string;
  contentHtml: string;
  readMinutes: number;
}

let _cache: Article[] | null = null;

export function getAllArticles(): Article[] {
  if (_cache) return _cache;
  const out: Article[] = [];
  for (const sec of SECTIONS) {
    const dir = path.join(CONTENT_ROOT, sec.slug);
    if (!fs.existsSync(dir)) continue;
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith('.md') || f.startsWith('_')) continue;
      const date = f.replace(/\.md$/, '');
      const raw = fs.readFileSync(path.join(dir, f), 'utf-8');
      const { data, content } = matter(raw);
      const heroImage = (data.hero_image as string) || `/images/${sec.slug}/${date}.png`;
      const html = String(remark().use(remarkGfm).use(remarkHtml).processSync(content));
      const wordCount = content.replace(/\s+/g, ' ').trim().length;
      const readMinutes = Math.max(2, Math.round(wordCount / 600));
      out.push({
        section: sec.slug,
        date,
        slug: `${sec.slug}-${date}`,
        title: (data.title as string) || sec.label,
        summary: (data.summary as string) || '',
        tags: (data.tags as string[]) || [],
        heroImage: '/newsletter-dashboard' + heroImage.replace(/^\/+/, '/'),
        originalUrl: (data.original_url as string) || '',
        contentHtml: html,
        readMinutes,
      });
    }
  }
  out.sort((a, b) => (a.date < b.date ? 1 : -1));
  _cache = out;
  return out;
}

export function getArticleBySlug(slug: string): Article | undefined {
  return getAllArticles().find((a) => a.slug === slug);
}

export function getArticlesBySection(section: SectionSlug): Article[] {
  return getAllArticles().filter((a) => a.section === section);
}

/* ------------------------------------------------------------------
   Issue model: 1 day = 1 Issue. Issue 1 = first content date.
   ------------------------------------------------------------------ */
export interface Issue {
  number: number;        // 1, 2, 3 ...
  date: string;          // YYYY-MM-DD
  articles: Article[];
}

export function getAllIssueDates(): string[] {
  const set = new Set<string>();
  for (const a of getAllArticles()) set.add(a.date);
  return Array.from(set).sort();   // ascending
}

export function getIssue(date: string): Issue | undefined {
  const dates = getAllIssueDates();
  const idx = dates.indexOf(date);
  if (idx < 0) return undefined;
  return {
    number: idx + 1,
    date,
    articles: getAllArticles().filter((a) => a.date === date),
  };
}

export function getLatestIssue(): Issue {
  const dates = getAllIssueDates();
  const last = dates[dates.length - 1];
  return getIssue(last)!;
}

export function getAllIssues(): Issue[] {
  return getAllIssueDates().map((d, i) => ({
    number: i + 1,
    date: d,
    articles: getAllArticles().filter((a) => a.date === d),
  }));
}
