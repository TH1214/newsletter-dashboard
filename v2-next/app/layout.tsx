import type { Metadata } from 'next';
import './globals.css';
import { InterestLogger } from '@/components/interest/InterestLogger';
import { BackToTop } from '@/components/BackToTop';

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

// Cloudflare Web Analytics のビーコン用トークン。
// Cloudflare ダッシュボード → Web Analytics → th1214.github.io を追加 → 発行される
// data-cf-beacon の token 値をここに設定すると計測が有効化される（空文字なら無効・何も読み込まない）。
// トークンは秘密情報ではなく、公開ページに埋め込まれる公開識別子。
const CF_BEACON_TOKEN: string = '';

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
        {/* Night Desk トップページ用フォント一式（Archivo/DM Mono はヘッダー専用、
            Space Grotesk/Noto Sans JP/JetBrains Mono は全体UI）。加算的で他ページ無影響。 */}
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&family=Archivo:wght@600;700;800;900&family=DM+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        {/* P3 #6 (v3.2.2): RSS feed auto-discovery */}
        <link
          rel="alternate"
          type="application/rss+xml"
          title="Bolgheri Daily Brief — RSS Feed"
          href="/newsletter-dashboard/feed.xml"
        />
        {/* Cloudflare Web Analytics（プライバシー配慮・Cookieなし・DNS/プロキシ変更不要）。
            トークン未設定のうちは何も読み込まない。 */}
        {CF_BEACON_TOKEN ? (
          <script
            defer
            src="https://static.cloudflareinsights.com/beacon.min.js"
            data-cf-beacon={`{"token": "${CF_BEACON_TOKEN}"}`}
          />
        ) : null}
      </head>
      <body>
        {children}
        {/* Personal Interest Log — 全ページ共通のクリック記録ランナー (renders null) */}
        <InterestLogger />
        {/* 全ページ共通「Topに戻る」ボタン */}
        <BackToTop />
      </body>
    </html>
  );
}
