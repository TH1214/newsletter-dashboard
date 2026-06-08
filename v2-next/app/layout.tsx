import type { Metadata } from 'next';
import './globals.css';
import { InterestLogger } from '@/components/interest/InterestLogger';

export const metadata: Metadata = {
  title: {
    default: 'Bolgheri — Editorial AI News Magazine',
    template: '%s — Bolgheri Daily Brief',
  },
  description:
    '海外メディア (NYT / WSJ / FT / The Economist 等) の記事を AI が編集・要約・解釈して日本語読者に届ける、静謐な雑誌的プロダクト。',
  metadataBase: new URL('https://th1214.github.io/newsletter-dashboard'),
  openGraph: {
    type: 'website',
    siteName: 'Bolgheri Daily Brief',
    title: 'Bolgheri — Editorial AI News Magazine',
    description:
      '海外メディア (NYT / WSJ / FT / The Economist 等) の記事を AI が編集・要約・解釈して日本語読者に届ける、静謐な雑誌的プロダクト。毎朝 06:00 JST 配信。',
    locale: 'ja_JP',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Bolgheri — Editorial AI News Magazine',
    description:
      '海外メディアの記事を AI が編集・要約して日本語で届ける、静謐な雑誌的プロダクト。毎朝 06:00 JST 配信。',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  // GitHub Pages の Jekyll 処理を無効化 (一部 _ プレフィックスファイル対応)
  other: {
    'google-site-verification': '',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <head>
        {/* WIRED.jp uses an all-system Helvetica/Yu Gothic stack with no web fonts,
            plus a custom 'WiredMono' for caps labels.  We keep JetBrains Mono as a
            fallback for the mono caps style; everything else is system-served. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        {/* P3 #6 (v3.2.2): RSS feed auto-discovery */}
        <link
          rel="alternate"
          type="application/rss+xml"
          title="Bolgheri Daily Brief — RSS Feed"
          href="/newsletter-dashboard/feed.xml"
        />
      </head>
      <body>
        {children}
        {/* Personal Interest Log — 全ページ共通のクリック記録ランナー (renders null) */}
        <InterestLogger />
      </body>
    </html>
  );
}
