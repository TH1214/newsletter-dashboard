import Link from 'next/link';
import { notFound } from 'next/navigation';
import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import {
  getAllArticles,
  getArticleBySlug,
  getIssue,
  getSectionInfo,
} from '@/lib/content';

export function generateStaticParams() {
  return getAllArticles().map((a) => ({ date: a.date, slug: a.slug }));
}

export default function ArticlePage({
  params,
}: {
  params: { date: string; slug: string };
}) {
  const article = getArticleBySlug(params.slug);
  const issue = getIssue(params.date);
  if (!article || !issue) return notFound();
  const sec = getSectionInfo(article.section);

  // 同じ Issue から関連3件
  const related = issue.articles
    .filter((a) => a.slug !== article.slug)
    .slice(0, 3);

  const titleClean = article.title.split('｜')[0].split('|')[0];

  return (
    <>
      <div className="progress"><div className="bar"></div></div>
      <MetaBar issue={issue} suffix={`Article ${issue.articles.findIndex((a) => a.slug === article.slug) + 1}`} />
      <Chrome>
        {/* ARTICLE HERO */}
        <section className="art-hero">
          <p className="eyebrow">{sec.eyebrow}</p>
          <h1>{titleClean}</h1>
          <p className="deck">{article.summary}</p>
          <div className="byline">
            <span>By <strong>Bolgheri AI</strong> · translated from {sec.label}</span>
            <span className="dot">·</span>
            <span>{article.date}</span>
            <span className="dot">·</span>
            <span>{article.readMinutes} min read</span>
          </div>
        </section>

        {/* HERO IMAGE */}
        <div className="art-image" style={{ backgroundImage: `url(${article.heroImage})` }}></div>

        {/* INTERPRETER STRIPE */}
        <section className="interpreter-stripe">
          <div className="is-label"><span>Interpreter</span></div>
          <div className="is-body">
            <p className="is-summary">{article.summary}</p>
            {article.tags.length > 0 && (
              <ul className="is-tags">
                {article.tags.map((t) => (
                  <li key={t}><span className="dot">●</span>{t}</li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* BODY */}
        <article className="art-body">
          <div className="ab-main"
            dangerouslySetInnerHTML={{ __html: article.contentHtml }} />
          <aside className="ab-side">
            <p className="side-h">Source</p>
            <p className="side-body">
              {sec.label}<br />
              {article.originalUrl && (
                <a href={article.originalUrl} target="_blank" rel="noopener">View original ↗</a>
              )}
            </p>
            <p className="side-h">Translated</p>
            <p className="side-body">{article.date} 06:00 JST</p>
            {article.tags.length > 0 && (
              <>
                <p className="side-h">Tags</p>
                <ul className="side-tags">
                  {article.tags.map((t) => (<li key={t}>{t}</li>))}
                </ul>
              </>
            )}
          </aside>
        </article>

        {/* RELATED */}
        {related.length > 0 && (
          <section className="related">
            <div className="rel-head">
              <h2>Also in <em>Issue {issue.number}</em></h2>
              <span className="meta">{related.length} more from today</span>
            </div>
            <div className="rel-grid">
              {related.map((a) => {
                const sec2 = getSectionInfo(a.section);
                return (
                  <Link key={a.slug} href={`/issues/${issue.date}/${a.slug}/`} className="rel-card">
                    <span className="src">{sec2.label}</span>
                    <h3>{a.title.split('｜')[0].split('|')[0]}</h3>
                    <span className="read">{a.readMinutes} min read · {a.date}</span>
                  </Link>
                );
              })}
            </div>
          </section>
        )}
      </Chrome>
      <SiteFooter />
    </>
  );
}
