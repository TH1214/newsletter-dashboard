import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Bolgheri — Editorial AI News Magazine',
  description:
    '海外メディア (NYT / WSJ / FT / The Economist 等) の記事を AI が編集・要約・解釈して日本語読者に届ける、静謐な雑誌的プロダクト。',
  metadataBase: new URL('https://th1214.github.io/newsletter-dashboard'),
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
      </head>
      <body>{children}</body>
    </html>
  );
}
