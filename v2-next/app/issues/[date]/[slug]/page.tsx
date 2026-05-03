import Link from 'next/link';
import { notFound } from 'next/navigation';
import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import { ArchiveSidebar } from '@/components/ArchiveSidebar';
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

  const titleClean = article.title.split('｜')[0].split('|')[0];

  return (
    <>
      <div className="progress"><div className="bar"></div></div>
      <MetaBar issue={issue} suffix={`Article ${issue.articles.findIndex((a) => a.slug === article.slug) + 1}`} />
      <Chrome>
        {/* WIRED-style 2-column article layout */}
        <article className="wb-art">
          <div className="wb-art-main">
            {/* Hero block: eyebrow + headline + deck */}
            <p className="wb-art-eyebrow">{sec.eyebrow}</p>
            <h1 className="wb-art-h1">{titleClean}</h1>
            <p className="wb-art-deck">{article.summary}</p>

            {/* Hero image */}
            <figure className="wb-art-figure">
              <div
                className="wb-art-img"
                style={{ backgroundImage: `url(${article.heroImage})` }}
              />
              <figcaption className="wb-art-credit">
                ILLUSTRATION · BOLGHERI AI
              </figcaption>
            </figure>

            {/* Byline */}
            <div className="wb-art-byline">
              <span>By <strong>Bolgheri AI</strong></span>
              <span className="dot">·</span>
              <span>translated from {sec.label}</span>
              <span className="dot">·</span>
              <span>{article.date}</span>
              <span className="dot">·</span>
              <span>{article.readMinutes} min read</span>
            </div>

            {/* Body */}
            <div
              className="wb-art-body"
              dangerouslySetInnerHTML={{ __html: article.contentHtml }}
            />

            {/* Source footer */}
            <div className="wb-art-source">
              <p className="wb-as-h">Source</p>
              <p>
                {sec.label}
                {article.originalUrl && (
                  <>
                    {' · '}
                    <a href={article.originalUrl} target="_blank" rel="noopener">
                      View original ↗
                    </a>
                  </>
                )}
              </p>
              {article.tags.length > 0 && (
                <ul className="wb-art-tags">
                  {article.tags.map((t) => <li key={t}>#{t}</li>)}
                </ul>
              )}
            </div>
          </div>

          {/* Right sidebar: Full Archive */}
          <ArchiveSidebar excludeSlug={article.slug} />
        </article>
      </Chrome>
      <SiteFooter />
    </>
  );
}
