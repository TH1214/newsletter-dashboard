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
        <section className="wb-arch-hero">
          <p className="wb-eyebrow">ARCHIVE · ALL EDITIONS</p>
          <h1 className="wb-h1">The <em>Archive</em></h1>
          <p className="wb-deck">
            {total} briefings across {SECTIONS.length} sources, since 2026-04-01.
            Curated daily 06:00 JST. Browse by news source below.
          </p>
        </section>

        {/* SECTION NAV (jump links) */}
        <section className="wb-arch-jump">
          <p className="wb-arch-jump-h">JUMP TO</p>
          <ul className="wb-arch-jump-list">
            {SECTIONS.map((sec) => {
              const cnt = getArticlesBySection(sec.slug).length;
              if (cnt === 0) return null;
              return (
                <li key={sec.slug}>
                  <a href={`#sec-${sec.slug}`}>
                    <span>{sec.label}</span>
                    <span className="cnt">{cnt}</span>
                  </a>
                </li>
              );
            })}
          </ul>
        </section>

        {/* PER-SECTION CARD GRID */}
        {SECTIONS.map((sec) => {
          const arts = getArticlesBySection(sec.slug);
          if (arts.length === 0) return null;
          return (
            <section key={sec.slug} id={`sec-${sec.slug}`} className="wb-arch-sec">
              <div className="wb-arch-sec-head">
                <div>
                  <p className="wb-eyebrow">{sec.eyebrow}</p>
                  <h2 className="wb-arch-sec-title">{sec.label}</h2>
                </div>
                <div className="wb-arch-sec-meta">
                  <span><strong>{arts.length}</strong> articles</span>
                  <Link href={`/sections/${sec.slug}/`} className="wb-arch-sec-more">
                    View all →
                  </Link>
                </div>
              </div>

              <div className="wb-arch-grid">
                {arts.slice(0, 9).map((a) => {
                  const titleClean = a.title.split('｜')[0].split('|')[0];
                  return (
                    <Link
                      key={a.slug}
                      href={`/issues/${a.date}/${a.slug}/`}
                      className="wb-arch-card"
                    >
                      <div
                        className="wb-arch-card-img"
                        style={{ backgroundImage: `url(${a.heroImage})` }}
                      />
                      <p className="wb-arch-card-date">{a.date}</p>
                      <h3 className="wb-arch-card-title">{titleClean}</h3>
                      <p className="wb-arch-card-deck">
                        {a.summary.length > 90 ? a.summary.slice(0, 90) + '…' : a.summary}
                      </p>
                    </Link>
                  );
                })}
              </div>

              {arts.length > 9 && (
                <div className="wb-arch-sec-foot">
                  <Link href={`/sections/${sec.slug}/`} className="wb-arch-sec-foot-cta">
                    + {arts.length - 9} more in {sec.label} →
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
