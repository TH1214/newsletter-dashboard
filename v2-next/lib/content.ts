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

/* front matter の date を YYYY-MM-DD 文字列へ正規化。
   YAML は無クオートの 2026-06-09 を Date に自動変換するため両対応する。 */
function toDateString(v: unknown): string {
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  if (typeof v === 'string') {
    const m = v.match(/^\d{4}-\d{2}-\d{2}/);
    if (m) return m[0];
  }
  return '';
}

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
      const stem = f.replace(/\.md$/, '');
      const raw = fs.readFileSync(path.join(dir, f), 'utf-8');
      const { data, content } = matter(raw);
      // ファイル名が YYYY-MM-DD なら従来どおり 1日1ファイル。
      // それ以外（例: nikkei-hack の nikkei-YYYYMMDD-NN-*.md）は front matter の
      // date を採用し、slug はファイル名から作る（1日に複数記事を許容）。
      const isDateStem = /^\d{4}-\d{2}-\d{2}$/.test(stem);
      const date = isDateStem ? stem : (toDateString(data.date) || stem);
      const slugId = isDateStem ? `${sec.slug}-${date}` : `${sec.slug}-${stem}`;
      // hero: hero_image が「明示的に空文字」なら画像なし（nikkei-hack v1）。
      // 省略時のみ従来の規約パス /images/<section>/<date>.png を使う。
      // P3 #5 (v3.2.2): WebP 優先 + PNG fallback
      let heroImage: string;
      if (data.hero_image === '') {
        heroImage = '';
      } else {
        const pngBasename = (data.hero_image as string) || `/images/${sec.slug}/${date}.png`;
        const webpAbsPath = path.join(process.cwd(), 'public', pngBasename.replace(/^\//, '').replace(/\.png$/, '.webp'));
        const useWebp = fs.existsSync(webpAbsPath);
        const h = useWebp ? pngBasename.replace(/\.png$/, '.webp') : pngBasename;
        heroImage = h.startsWith('http') ? h : '/newsletter-dashboard' + h.replace(/^\/+/, '/');
      }
      // 本文インライン画像 (例: 武者の図表) は basePath が自動付与されないため、
      // remarkHtml 出力の <img src="/images/..."> に basePath を補正する (加算的・既存ソース無影響)。
      const htmlRaw = String(remark().use(remarkGfm).use(remarkHtml).processSync(content));
      const html = htmlRaw.replace(/(<img[^>]+src=")\/images\//g, '$1/newsletter-dashboard/images/');
      const wordCount = content.replace(/\s+/g, ' ').trim().length;
      const readMinutes = Math.max(2, Math.round(wordCount / 600));
      out.push({
        section: sec.slug,
        date,
        slug: slugId,
        title: (data.title as string) || sec.label,
        summary: (data.summary as string) || '',
        tags: (data.tags as string[]) || [],
        heroImage,
        originalUrl: (data.original_url as string) || '',
        contentHtml: html,
        readMinutes,
      });
    }
  }
  // 日付降順。同一日付は SECTIONS の編集優先順で決定的に並べる
  // （旧: `a.date < b.date ? 1 : -1` は同値で 0 を返さず、同日グループが不定/逆順になり
  //  配列末尾の Axios 系が Today 上位を占める不具合があった）。
  const _order = new Map(SECTIONS.map((s, i) => [s.slug, i] as const));
  out.sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;
    return (_order.get(a.section) ?? 999) - (_order.get(b.section) ?? 999);
  });
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
