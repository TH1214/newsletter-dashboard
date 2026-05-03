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
  const latest = arts[0];

  return (
    <>
      <MetaBar issue={issue} suffix={sec.label} />
      <Chrome>
        {/* SECTION HERO */}
        <section className="sec-hero">
          <p className="eyebrow">{sec.eyebrow}</p>
          <h1>{sec.label}</h1>
          {latest && (
            <p className="deck">
              Most recent: <Link href={`/issues/${latest.date}/${latest.slug}/`}>{latest.title.split('｜')[0].split('|')[0]}</Link> · {latest.date}
            </p>
          )}
          <div className="sh-meta">
            <span><strong>{arts.length}</strong> articles</span>
            <span className="dot">·</span>
            <span>Translated daily 06:00 JST</span>
          </div>
        </section>

        {/* ALL ARTICLES OF THIS SECTION */}
        <section className="sec-list">
          <ul className="ix-rows">
            {arts.map((a, i) => (
              <li key={a.slug}>
                <Link href={`/issues/${a.date}/${a.slug}/`}>
                  <span className="ix-num">{String(arts.length - i).padStart(2, '0')}</span>
                  <span className="ix-title">{a.title.split('｜')[0].split('|')[0]}</span>
                  <span className="ix-src">{a.date}</span>
                  <span className="ix-read">{a.readMinutes} min</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </Chrome>
      <SiteFooter />
    </>
  );
}
