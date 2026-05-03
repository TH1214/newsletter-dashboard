'use client';
import Link from 'next/link';
import { useEffect } from 'react';

export function HamburgerOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (open) document.body.classList.add('menu-open');
    else document.body.classList.remove('menu-open');
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  return (
    <div className="overlay" aria-hidden={!open}>
      <div className="overlay-head">
        <Link href="/" className="gh-logo" onClick={onClose}>
          Bolgheri<i>.</i>
        </Link>
        <span className="gh-mid">Index · Sections · Editions</span>
        <button className="menu-btn" type="button" onClick={onClose} aria-label="Close menu">
          <span className="bars"><span></span><span></span></span>
          <span className="label"><span className="open">Close</span></span>
        </button>
      </div>
      <div className="overlay-body">
        <ul className="overlay-nav">
          <li><Link href="/" onClick={onClose}><span className="num">01</span><span>Today<em>.</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/archive/" onClick={onClose}><span className="num">02</span><span>The <em>Archive</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/wsj/" onClick={onClose}><span className="num">03</span><span>WSJ <em>10-Point</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/economist/" onClick={onClose}><span className="num">04</span><span>The <em>Economist</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/nyt-bn/" onClick={onClose}><span className="num">05</span><span>NYT <em>Breaking</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/nyt-op/" onClick={onClose}><span className="num">06</span><span>NYT <em>Opinion</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/buysiders/" onClick={onClose}><span className="num">07</span><span>Buysiders <em>OWS</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/short-squeez/" onClick={onClose}><span className="num">08</span><span>Short <em>Squeez</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/skift/" onClick={onClose}><span className="num">09</span><span>Skift <em>Daily</em></span><span className="arrow">→</span></Link></li>
          <li><Link href="/sections/business-insider/" onClick={onClose}><span className="num">10</span><span>Business <em>Insider</em></span><span className="arrow">→</span></Link></li>
        </ul>
      </div>
      <div className="overlay-foot">
        <span className="left">© 2026 BOLGHERI LIMITED</span>
        <span className="center">Press Esc to close</span>
        <span className="right">Index · v2</span>
      </div>
    </div>
  );
}
