import Link from 'next/link';
import { SECTIONS } from '@/lib/sections';

// Compact display labels for the horizontal nav (full names live in SECTIONS).
const SHORT: Record<string, string> = {
  'wsj': 'WSJ',
  'economist': 'Economist',
  'nyt-bn': 'NYT Breaking',
  'nyt-op': 'NYT Opinion',
  'buysiders': 'Buysiders',
  'short-squeez': 'Short Squeez',
  'skift': 'Skift',
  'business-insider': 'Business Insider',
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
