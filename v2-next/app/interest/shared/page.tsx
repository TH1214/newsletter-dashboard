import type { Metadata } from 'next';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import { SharedInterestClient } from '@/components/interest/SharedInterestClient';

export const metadata: Metadata = {
  title: 'My Interest — 共有スナップショット',
  robots: { index: false, follow: false },
};

// 静的シェルを書き出し、実データは URL ハッシュからクライアントで復元する
export default function SharedInterestPage() {
  return (
    <>
      <Chrome>
        <SharedInterestClient />
      </Chrome>
      <SiteFooter />
    </>
  );
}
