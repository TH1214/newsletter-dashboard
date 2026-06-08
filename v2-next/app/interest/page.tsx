import type { Metadata } from 'next';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import { InterestDashboard } from '@/components/interest/InterestDashboard';

export const metadata: Metadata = {
  title: 'My Interest',
  // 個人専用ダッシュボードのため検索エンジンには載せない
  robots: { index: false, follow: false },
};

export default function InterestPage() {
  return (
    <>
      <Chrome>
        <InterestDashboard />
      </Chrome>
      <SiteFooter />
    </>
  );
}
