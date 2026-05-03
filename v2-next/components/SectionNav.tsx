import Link from 'next/link';
import { SECTIONS } from '@/lib/sections';

export function SectionNav() {
  return (
    <nav className="bl-secnav" aria-label="Sections">
      <Link href="/" className="bl-secnav-h">TODAY</Link>
      {SECTIONS.map((s) => (
        <Link key={s.slug} href={`/sections/${s.slug}/`} className="bl-secnav-link">
          {s.label}
        </Link>
      ))}
      <Link href="/archive/" className="bl-secnav-link bl-secnav-archive">
        ARCHIVE →
      </Link>
    </nav>
  );
}
