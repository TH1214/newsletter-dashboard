import Link from 'next/link';
import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import {
  getLatestIssue,
  getAllIssues,
  getAllArticles,
  getSectionInfo,
} from '@/lib/content';

export default function HomePage() {
  const issue = getLatestIssue();
  const totalIssues = getAllIssues().length;
  const totalArticles = getAllArticles().length;

  // 全Issue横断・日付降順で最新8記事
  const latest8 = getAllArticles().slice(0, 8);

  return (
    <>
      <MetaBar issue={issue} />
      <Chrome>
        {/* WIRED-style hero: lead headline + deck */}
        <section className="wb-hero">
          <p className="wb-eyebrow">ISSUE {String(issue.number).padStart(3, '0')} · {issue.date}</p>
          <h1 className="wb-h1">
            {latest8[0].title.split('｜')[0].split('|')[0]}
          </h1>
          <p className="wb-deck">{latest8[0].summary}</p>
          <div className="wb-byline">
            <span>By <strong>Bolgheri AI</strong></span>
            <span className="dot">·</span>
            <span>{getSectionInfo(latest8[0].section).label}</span>
            <span className="dot">·</span>
            <Link href={`/issues/${latest8[0].date}/${latest8[0].slug}/`} className="wb-cta">
              Read Lead →
            </Link>
          </div>
        </section>

        {/* WIRED-style 4-col card grid - latest 8 articles */}
        <section className="wb-grid-section">
          <div className="wb-grid-head">
            <h2>Latest <em>Curations</em></h2>
            <Link href="/archive/" className="wb-grid-archive">View Archive →</Link>
          </div>
          <div className="wb-grid">
            {latest8.map((a) => {
              const sec = getSectionInfo(a.section);
              const titleClean = a.title.split('｜')[0].split('|')[0];
              return (
                <Link key={a.slug} href={`/issues/${a.date}/${a.slug}/`} className="wb-card">
                  <div
                    className="wb-card-img"
                    style={{ backgroundImage: `url(${a.heroImage})` }}
                  />
                  <p className="wb-card-eyebrow">{sec.eyebrow}</p>
                  <h3 className="wb-card-title">{titleClean}</h3>
                  <p className="wb-card-deck">
                    {a.summary.length > 110 ? a.summary.slice(0, 110) + '…' : a.summary}
                  </p>
                  <p className="wb-card-by">
                    BY BOLGHERI AI · {a.date}
                  </p>
                </Link>
              );
            })}
          </div>
        </section>

        {/* ARCHIVE STATS */}
        <section className="archive-cta">
          <div className="ac-num">{totalIssues} <span className="lbl">ISSUES</span></div>
          <div className="ac-grid">
            <div><span className="k">Sections</span><span className="v">9</span></div>
            <div><span className="k">Articles</span><span className="v">{totalArticles}</span></div>
            <div><span className="k">Languages</span><span className="v">EN → JP</span></div>
            <div><span className="k">Cadence</span><span className="v">Daily 06:00 JST</span></div>
          </div>
          <Link href="/archive/" className="ac-cta">
            Browse the Archive <span className="arrow">→</span>
          </Link>
        </section>
      </Chrome>
      <SiteFooter />
    </>
  );
}
