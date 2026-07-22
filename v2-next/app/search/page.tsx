import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import { getAllArticles, getLatestIssue, getSectionInfo } from '@/lib/content';
import { SearchClient, type SearchRecord } from '@/components/SearchClient';

export const metadata = {
  title: 'Search · Bolgheri Daily Brief',
};

export default function SearchPage() {
  const issue = getLatestIssue();

  // ビルド時に軽量索引を生成（本文は含めず title/summary/tags/section/date のみ ≒160KB）
  const index: SearchRecord[] = getAllArticles().map((a) => {
    const sec = getSectionInfo(a.section);
    return {
      title: a.title.split('｜')[0].split('|')[0],
      summary: a.summary,
      tags: a.tags,
      section: a.section,
      sectionLabel: sec.label,
      eyebrow: sec.eyebrow,
      date: a.date,
      href: `/issues/${a.date}/${a.slug}/`,
    };
  });

  return (
    <>
      <MetaBar issue={issue} suffix="Search" />
      <Chrome>
        <section className="wb-search-hero">
          <p className="wb-eyebrow">SEARCH · ALL EDITIONS</p>
          <h1 className="wb-h1">
            Search the <em>Archive</em>
          </h1>
          <p className="wb-deck">
            全 {index.length} 記事をタイトル・要約・タグ・ソースから検索します。
          </p>
        </section>
        <SearchClient index={index} />
      </Chrome>
      <SiteFooter />
    </>
  );
}
