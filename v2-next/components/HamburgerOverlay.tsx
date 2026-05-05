'use client';
import Link from 'next/link';
import { useEffect, useRef } from 'react';
import { SECTIONS } from '@/lib/sections';

export function HamburgerOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      document.body.classList.add('menu-open');
      // Focus close button when opened (small delay for transition)
      const t = setTimeout(() => closeRef.current?.focus(), 200);
      return () => clearTimeout(t);
    } else {
      document.body.classList.remove('menu-open');
    }
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className={`bm-backdrop ${open ? 'is-open' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Right-side drawer */}
      <aside
        className={`bm-drawer ${open ? 'is-open' : ''}`}
        aria-hidden={!open}
        aria-label="Site navigation"
      >
        <header className="bm-head">
          <Link href="/" className="bm-logo" onClick={onClose}>
            Bolgheri<i>.</i>
          </Link>
          <button
            ref={closeRef}
            className="bm-close"
            type="button"
            onClick={onClose}
            aria-label="Close menu"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M6 6L18 18M6 18L18 6" />
            </svg>
          </button>
        </header>

        <nav className="bm-nav">
          <ul className="bm-primary">
            <li>
              <Link href="/" onClick={onClose}>
                <span className="bm-label">Today</span>
                <span className="bm-arrow">→</span>
              </Link>
            </li>
            <li>
              <Link href="/archive/" onClick={onClose}>
                <span className="bm-label">Archive</span>
                <span className="bm-arrow">→</span>
              </Link>
            </li>
          </ul>

          <ul className="bm-sources">
            {SECTIONS.map((s) => (
              <li key={s.slug}>
                <Link href={`/sections/${s.slug}/`} onClick={onClose}>
                  <span className="bm-label">{s.label}</span>
                  <span className="bm-arrow">→</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <footer className="bm-foot">
          <p className="bm-foot-name">BOLGHERI LIMITED</p>
          <p className="bm-foot-tag">Editorial AI · Foreign Press</p>
          <p className="bm-foot-copy">© 2026</p>
        </footer>
      </aside>
    </>
  );
}
