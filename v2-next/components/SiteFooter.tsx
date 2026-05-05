/* === BOLGHERI LIMITED — Minimal black footer === */
export function SiteFooter() {
  return (
    <footer className="bl-footer">
      <div className="bl-footer-inner">
        {/* COL 1: Logo */}
        <div className="bl-col bl-col-logo">
          <p className="bl-logo">BOLGHERI LIMITED</p>
        </div>

        {/* COL 2: Explore */}
        <div className="bl-col">
          <h4 className="bl-h">EXPLORE</h4>
          <ul>
            <li><a href="#">Collections</a></li>
            <li><a href="#">Journal</a></li>
            <li><a href="#">Heritage</a></li>
            <li><a href="#">Membership</a></li>
          </ul>
        </div>

        {/* COL 3: Social icons (design only — no href) */}
        <div className="bl-col bl-col-social">
          <div className="bl-social">
            {/* Instagram */}
            <span className="bl-icon" aria-label="Instagram">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="5" ry="5"></rect>
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
              </svg>
            </span>
            {/* X (Twitter) */}
            <span className="bl-icon" aria-label="X">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zM17.083 19.77h1.833L7.084 4.126H5.117z"/>
              </svg>
            </span>
            {/* Facebook */}
            <span className="bl-icon" aria-label="Facebook">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"></path>
              </svg>
            </span>
            {/* Spotify */}
            <span className="bl-icon" aria-label="Spotify">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.42 1.56-.299.421-1.02.599-1.56.3z"/>
              </svg>
            </span>
            {/* YouTube */}
            <span className="bl-icon" aria-label="YouTube">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </span>
          </div>
        </div>
      </div>

      {/* Hairline */}
      <div className="bl-hairline"></div>

      {/* Disclaimer + legal + copyright */}
      <div className="bl-footer-bottom">
        <p className="bl-disclaimer">
          Bolgheri Limited is an independent editorial platform for curated
          briefings. All original content and intellectual property rights
          belong to their respective publishers (NYT, WSJ, etc.). We are not
          affiliated with these outlets.
        </p>
        <div className="bl-bottom-row">
          <ul className="bl-legal">
            <li><a href="#">Privacy Policy</a></li>
            <li><a href="#">Terms</a></li>
            <li><a href="#">Contact</a></li>
          </ul>
          <p className="bl-copy">© 2026 BOLGHERI LIMITED.</p>
        </div>
      </div>
    </footer>
  );
}
