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
      </div>
    </nav>
  );
}
