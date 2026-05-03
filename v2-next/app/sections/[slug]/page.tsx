import Link from 'next/link';
import { notFound } from 'next/navigation';
import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import {
  SECTIONS,
  type SectionSlug,
  getArticlesBySection,
  getLatestIssue,
  getSectionInfo,
} from '@/lib/content';

export function generateStaticParams() {
  return SECTIONS.map((s) => ({ slug: s.slug }));
}

export default function SectionPage({
  params,
}: {
  params: { slug: string };
}) {
  const slug = params.slug as SectionSlug;
  if (!SECTIONS.find((s) => s.slug === slug)) return notFound();
  const sec = getSectionInfo(slug);
  const arts = getArticlesBySection(slug);
  const issue = getLatestIssue();

  return (
    <>
      <MetaBar issue={issue} suffix={sec.label} />
      <Chrome>
        {/* SECTION HERO */}
        <section className="wb-sec-hero">
          <p className="wb-eyebrow">{sec.eyebrow}</p>
          <h1 className="wb-h1">{sec.label}</h1>
          <p className="wb-deck">
            <strong>{arts.length}</strong> translated articles · Daily 06:00 JST · since 2026-04-01
          </p>
          <div className="wb-sec-back">
            <Link href="/archive/">← All Sources</Link>
            <Link href="/">Today →</Link>
          </div>
        </section>

        {/* CARD GRID — all articles in this section */}
        <section className="wb-sec-grid-section">
          <div className="wb-sec-grid-head">
            <span>ALL ARTICLES</span>
            <span className="wb-sec-grid-count">{arts.length}</span>
          </div>
          <div className="wb-sec-grid">
            {arts.map((a) => {
              const titleClean = a.title.split('｜')[0].split('|')[0];
              return (
                <Link
                  key={a.slug}
                  href={`/issues/${a.date}/${a.slug}/`}
                  className="wb-sec-card"
                >
                  <div
                    className="wb-sec-card-img"
                    style={{ backgroundImage: `url(${a.heroImage})` }}
                  />
                  <p className="wb-sec-card-date">{a.date}</p>
                  <h3 className="wb-sec-card-title">{titleClean}</h3>
                  <p className="wb-sec-card-deck">
                    {a.summary.length > 100 ? a.summary.slice(0, 100) + '…' : a.summary}
                  </p>
                  <p className="wb-sec-card-read">{a.readMinutes} MIN READ</p>
                </Link>
              );
            })}
          </div>
        </section>
      </Chrome>
      <SiteFooter />
    </>
  );
}
