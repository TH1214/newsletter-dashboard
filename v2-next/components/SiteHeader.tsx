'use client';
import Link from 'next/link';

export function SiteHeader({ onMenuClick }: { onMenuClick: () => void }) {
  return (
    <header className="gh">
      <Link href="/" className="gh-logo">
        Bolgheri<i>.</i>
      </Link>
      <span className="gh-mid">Foreign Press · Translated · Quietly</span>
      <div className="gh-right">
        <button className="gh-search" type="button" aria-label="Search">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="11" cy="11" r="7"></circle>
            <path d="M20 20l-3.5-3.5"></path>
          </svg>
        </button>
        <button className="menu-btn" type="button" onClick={onMenuClick} aria-label="Menu">
          <span className="bars"><span></span><span></span></span>
          <span className="label"><span className="closed">Index</span></span>
        </button>
      </div>
    </header>
  );
}
