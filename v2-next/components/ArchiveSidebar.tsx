import Link from 'next/link';
import { SECTIONS } from '@/lib/sections';
import { getAllIssues, getSectionInfo, type Article } from '@/lib/content';

interface Props {
  excludeSlug?: string;   // 現在表示中の記事を除外
}

export function ArchiveSidebar({ excludeSlug }: Props) {
  const issues = getAllIssues().slice().reverse(); // 新→古
  const recent: { date: string; number: number; articles: Article[] }[] = issues;

  // セクション別記事数
  const sectionCount: Record<string, number> = {};
  for (const a of issues.flatMap((i) => i.articles)) {
    sectionCount[a.section] = (sectionCount[a.section] || 0) + 1;
  }

  return (
    <aside className="wb-archive-side" aria-label="Archive">
      <p className="wb-as-h">ARCHIVE</p>
      <p className="wb-as-sub">{issues.length} Issues · {issues.flatMap((i) => i.articles).length} Articles</p>

      <p className="wb-as-h2">By Section</p>
      <ul className="wb-as-sections">
        {SECTIONS.map((s) => (
          <li key={s.slug}>
            <Link href={`/sections/${s.slug}/`}>
              <span className="wb-as-sec-label">{s.label}</span>
              <span className="wb-as-sec-count">{sectionCount[s.slug] || 0}</span>
            </Link>
          </li>
        ))}
      </ul>

      <p className="wb-as-h2">Past Issues</p>
      <ul className="wb-as-issues">
        {recent.map((iss) => {
          const lead = iss.articles[0];
          if (!lead) return null;
          return (
            <li key={iss.date}>
              <Link href={`/issues/${iss.date}/${lead.slug}/`}>
                <span className="wb-as-iss-num">No.{String(iss.number).padStart(3, '0')}</span>
                <span className="wb-as-iss-date">{iss.date}</span>
                <span className="wb-as-iss-cnt">{iss.articles.length} articles</span>
              </Link>
            </li>
          );
        })}
      </ul>

      <Link href="/archive/" className="wb-as-cta">
        Browse Full Archive →
      </Link>
    </aside>
  );
}
