import Link from 'next/link';
import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import { getLatestIssue, getAllIssues, getSectionInfo } from '@/lib/content';

export default function HomePage() {
  const issue = getLatestIssue();
  const totalIssues = getAllIssues().length;
  const lead = issue.articles[0]; // first article = today's lead

  return (
    <>
      <MetaBar issue={issue} />
      <Chrome>
        {/* HERO */}
        <section className="hero">
          <div className="hero-meta">
            <p className="ai-badge"><span className="dot"></span>AI Interpreter · v2</p>
            <div className="src">
              <div className="row"><span>Source</span><strong>{getSectionInfo(lead.section).label}</strong></div>
              <div className="row"><span>Issue</span><strong>{String(issue.number).padStart(3, '0')}</strong></div>
              <div className="row"><span>Read</span><strong>{lead.readMinutes} min</strong></div>
              <div className="row"><span>Date</span><strong>{issue.date}</strong></div>
            </div>
          </div>
          <h1>
            {lead.title.split('｜')[0].split('|')[0]}
            <em>.</em>
          </h1>
          <p className="deck">{lead.summary}</p>
          <div className="read">
            <Link href={`/issues/${issue.date}/${lead.slug}/`}>
              Read Today's Lead <span className="arrow">→</span>
            </Link>
          </div>
        </section>

        {/* INTERPRETER BAND */}
        <section className="interpreter">
          <div className="int-label"><span>Interpreter</span></div>
          <div className="int-body">
            <p className="int-summary">
              本日 Issue {issue.number} は {issue.articles.length} 本の翻訳を Index に並べる。
              {lead.summary && (lead.summary.length > 60 ? lead.summary.slice(0, 80) + '…' : lead.summary)}
            </p>
            <ol className="int-keys">
              {issue.articles.slice(0, 3).map((a, i) => (
                <li key={a.slug}>
                  <span className="num">{String(i + 1).padStart(2, '0')}</span>
                  <span>{a.title.split('｜')[0].split('|')[0]}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* INDEX LIST */}
        <section className="index-list">
          <div className="ix-head">
            <h2>Today's <em>Index</em></h2>
            <span className="meta">Issue {issue.number} · {issue.articles.length} articles</span>
          </div>
          <ul className="ix-rows">
            {issue.articles.map((a, i) => {
              const sec = getSectionInfo(a.section);
              const titleClean = a.title.split('｜')[0].split('|')[0];
              return (
                <li key={a.slug}>
                  <Link href={`/issues/${issue.date}/${a.slug}/`}>
                    <span className="ix-num">{String(i + 1).padStart(2, '0')}</span>
                    <span className="ix-title">{titleClean}</span>
                    <span className="ix-src">{sec.label}</span>
                    <span className="ix-read">{a.readMinutes} min</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>

        {/* SPREAD */}
        <section className="spread">
          <div className="sp-head">
            <h2>The <em>Spread</em></h2>
            <span className="meta">Featured visuals · Issue {issue.number}</span>
          </div>
          <div className="sp-cards">
            {issue.articles.slice(0, 3).map((a) => (
              <Link key={a.slug} href={`/issues/${issue.date}/${a.slug}/`} className="sp-card">
                <div className="sp-img" style={{ backgroundImage: `url(${a.heroImage})` }}></div>
                <div className="sp-meta">
                  <span className="src">{getSectionInfo(a.section).label}</span>
                  <h3>{a.title.split('｜')[0].split('|')[0]}</h3>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* ARCHIVE CTA */}
        <section className="archive-cta">
          <div className="ac-num">{totalIssues} <span className="lbl">ISSUES</span></div>
          <div className="ac-grid">
            <div><span className="k">Sections</span><span className="v">8</span></div>
            <div><span className="k">Articles</span><span className="v">{getAllIssues().reduce((s, i) => s + i.articles.length, 0)}</span></div>
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
