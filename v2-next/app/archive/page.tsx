import Link from 'next/link';
import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import {
  SECTIONS,
  getAllArticles,
  getArticlesBySection,
  getLatestIssue,
  getSectionInfo,
} from '@/lib/content';

export default function ArchivePage() {
  const issue = getLatestIssue();
  const total = getAllArticles().length;

  return (
    <>
      <MetaBar issue={issue} suffix="Archive" />
      <Chrome>
        {/* ARCHIVE HERO */}
        <section className="archive-hero">
          <div className="ah-num">{total}</div>
          <p className="ah-sub">ARTICLES SINCE 2026-04-01</p>
          <p className="ah-deck">8 sources · 33 issues · all read in full · grouped by news source.</p>
        </section>

        {/* SECTIONS GROUPED */}
        {SECTIONS.map((sec) => {
          const arts = getArticlesBySection(sec.slug);
          if (arts.length === 0) return null;
          return (
            <section key={sec.slug} className="arch-sec">
              <div className="as-head">
                <div className="as-h">
                  <p className="eyebrow">{sec.eyebrow}</p>
                  <h2>{sec.label}</h2>
                </div>
                <div className="as-meta">
                  <span className="cnt">{arts.length}</span>
                  <span className="lbl">articles</span>
                  <Link href={`/sections/${sec.slug}/`} className="more">View section →</Link>
                </div>
              </div>
              <ul className="as-rows">
                {arts.slice(0, 12).map((a, i) => (
                  <li key={a.slug}>
                    <Link href={`/issues/${a.date}/${a.slug}/`}>
                      <span className="r-num">{String(i + 1).padStart(2, '0')}</span>
                      <span className="r-title">{a.title.split('｜')[0].split('|')[0]}</span>
                      <span className="r-date">{a.date}</span>
                      <span className="r-read">{a.readMinutes} min</span>
                    </Link>
                  </li>
                ))}
              </ul>
              {arts.length > 12 && (
                <div className="as-foot">
                  <Link href={`/sections/${sec.slug}/`}>
                    + {arts.length - 12} more in {sec.label} →
                  </Link>
                </div>
              )}
            </section>
          );
        })}
      </Chrome>
      <SiteFooter />
    </>
  );
}
