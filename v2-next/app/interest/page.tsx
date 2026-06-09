import type { Metadata } from 'next';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import { InterestDashboard, type ArticleCatalog } from '@/components/interest/InterestDashboard';
import { getAllArticles, getSectionInfo } from '@/lib/content';
import { resolveDisplayTitle } from '@/lib/interest/attrs';

export const metadata: Metadata = {
  title: 'My Interest',
  // 個人専用ダッシュボードのため検索エンジンには載せない
  robots: { index: false, follow: false },
};

export default function InterestPage() {
  // ビルド時に記事カタログを生成し、過去ログの粗いタイトルを表示時に補完する
  // (Firestore の過去データは更新しない。表示だけ現行記事データで上書き)
  const catalog: ArticleCatalog = {};
  for (const a of getAllArticles()) {
    catalog[a.slug] = {
      title: resolveDisplayTitle(a),
      source: getSectionInfo(a.section).label,
      section: a.section,
      category: a.tags[0] || '',
    };
  }

  return (
    <>
      <Chrome>
        <InterestDashboard catalog={catalog} />
      </Chrome>
      <SiteFooter />
    </>
  );
}
