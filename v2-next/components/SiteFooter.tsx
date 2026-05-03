import Link from 'next/link';

export function SiteFooter() {
  return (
    <footer className="gf">
      <div className="gf-inner">
        <div className="gf-col">
          <p className="gf-h">Bolgheri<i>.</i></p>
          <p className="gf-body">海外メディアの記事を AI が翻訳・要約・解釈して日本語読者に届ける、静謐な雑誌的プロダクト。</p>
        </div>
        <div className="gf-col">
          <p className="gf-h">Sections</p>
          <ul>
            <li><Link href="/sections/wsj/">WSJ 10-Point</Link></li>
            <li><Link href="/sections/economist/">The Economist</Link></li>
            <li><Link href="/sections/nyt-bn/">NYT Breaking</Link></li>
            <li><Link href="/sections/nyt-op/">NYT Opinion</Link></li>
          </ul>
        </div>
        <div className="gf-col">
          <p className="gf-h">More</p>
          <ul>
            <li><Link href="/sections/short-squeez/">Short Squeez</Link></li>
            <li><Link href="/sections/skift/">Skift Daily</Link></li>
            <li><Link href="/sections/business-insider/">Business Insider</Link></li>
            <li><Link href="/sections/buysiders/">Buysiders</Link></li>
          </ul>
        </div>
        <div className="gf-col">
          <p className="gf-h">About</p>
          <ul>
            <li><Link href="/archive/">The Archive</Link></li>
            <li><a href="https://github.com/th1214/newsletter-dashboard">GitHub</a></li>
          </ul>
        </div>
      </div>
      <div className="gf-bottom">
        <span>© MMXXVI Bolgheri · Tokyo</span>
        <span>Edited by T. Hashiramoto · Powered by AI</span>
      </div>
    </footer>
  );
}
