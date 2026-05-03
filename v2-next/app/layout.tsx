import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Bolgheri — Editorial AI News Magazine',
  description:
    '海外メディア (NYT / WSJ / FT / The Economist 等) の記事を AI が翻訳・要約・解釈して日本語読者に届ける、静謐な雑誌的プロダクト。',
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
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&family=Newsreader:opsz,wght@6..72,200;6..72,300;6..72,400;6..72,500;6..72,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
