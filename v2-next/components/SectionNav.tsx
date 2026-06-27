import Link from 'next/link';
import { SECTIONS } from '@/lib/sections';

// Compact display labels for the horizontal nav (full names live in SECTIONS).
const SHORT: Record<string, string> = {
  'nyt-bn': 'NYT Breaking',
  'wsj': 'WSJ',
  'dealbook': 'DealBook',
  'economist': 'Economist',
  'business-insider': 'Business Insider',
  'skift': 'Skift',
  'buysiders': 'Buysiders',
  'short-squeez': 'Short Squeez',
  'nyt-op': 'NYT Opinion',
  'cnbc': 'CNBC',
  'cnbc-squawk': 'Squawk',
  'hospitality-net': 'HN',
  'pere': 'PERE',
  'maverick': 'Maverick',
  'musha': 'MUSHA',
  'axios-daily': 'Axios Daily',
  'axios-ai': 'Axios AI/Deals',
  'axios-frontier': 'Axios Def/CAR/2028',
};

export function SectionNav() {
  return (
    <nav className="bl-secnav" aria-label="Sections">
      <div className="bl-secnav-inner">
        <Link href="/" className="bl-secnav-h">TODAY</Link>
        <span className="bl-secnav-sep" aria-hidden="true" />
        {SECTIONS.map((s) => (
          <Link
            key={s.slug}
            href={`/sections/${s.slug}/`}
            className="bl-secnav-link"
          >
            {SHORT[s.slug] ?? s.label}
          </Link>
        ))}
        <Link href="/archive/" className="bl-secnav-link bl-secnav-archive">
          Archive →
        </Link>
        {/* 運営者本人専用の Personal Interest Dashboard 導線 */}
        <Link href="/interest/" className="bl-secnav-link bl-secnav-archive" title="My Interest (本人専用)">
          ★ My Interest
        </Link>
      </div>
    </nav>
  );
}
