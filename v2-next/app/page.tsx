import Link from 'next/link';
import {
  getLatestIssue,
  getAllArticles,
  getArticlesBySection,
  getSectionInfo,
} from '@/lib/content';
import { articleLinkAttrs, resolveDisplayTitle } from '@/lib/interest/attrs';
import { NightDeskClock } from '@/components/NightDeskClock';
import {
  ND_PILLS,
  ND_SOURCES,
  fmtMonthDay,
  fmtDotDate,
} from '@/lib/nightdesk';

/* ------------------------------------------------------------------
   トップページ "Night Desk"（design_handoff_top_page_night_desk/README.md）。
   README を単一の正として実装。参照 HTML (Bolgheri Top.dc.html) は見た目確認用で
   コードは流用しない。データ（カバー・各ソース最新号・WSJ 目次）は既存の号データから
   ビルド時に解決し、ライブ JST 時計だけ client（NightDeskClock）。
   ------------------------------------------------------------------ */
export default function HomePage() {
  const issue = getLatestIssue();
  const all = getAllArticles();

  // カバー = 最新号の先頭記事（getAllArticles は date 降順 → SECTIONS 編集順）。
  const cover = all[0];
  const coverSec = getSectionInfo(cover.section);
  // deck 段落: 号別ロング要約は非保有のため、そのソースの beat を supporting text に使う
  // （捏造しない）。summary は見出し(H1)へ回す。
  const coverBeat =
    ND_SOURCES.find((s) => s.slug === cover.section)?.beat ?? coverSec.eyebrow;

  // 各ソースの最新号日付（Desk カードに注入）。
  const latestDateBySlug = new Map<string, string>();
  for (const src of ND_SOURCES) {
    const arts = getArticlesBySection(src.slug);
    if (arts.length) latestDateBySlug.set(src.slug, arts[0].date);
  }

  // WSJ 最新 5 件（strip）。
  const wsjLatest = getArticlesBySection('wsj').slice(0, 5);

  return (
    <div className="nd-root">
      {/* ===== sticky header ===== */}
      <header className="nd-header">
        <div className="nd-header-top nd-wrap">
          <Link href="/" className="nd-wordmark">
            Bolgheri<span className="nd-slash">/</span>Brief
          </Link>
          <div className="nd-meta">
            <span className="nd-vol">VOL.06 · ISSUE {issue.number}</span>
            <NightDeskClock />
            <Link href="/search/" className="nd-metalink nd-index">Index</Link>
            <Link href="/archive/" className="nd-metalink">Archive →</Link>
          </div>
        </div>
        <nav className="nd-pills nd-wrap" aria-label="Sources">
          {ND_PILLS.map((p) => (
            <Link key={p.label} href={p.href} className="nd-pill">
              {p.label}
            </Link>
          ))}
        </nav>
      </header>

      {/* ===== hero cover ===== */}
      <section className="nd-hero nd-wrap">
        <div className="nd-hero-grid">
          <div className="nd-hero-main">
            <p className="nd-kicker">
              // TODAY&apos;S COVER — {coverSec.label.toUpperCase()} · {fmtDotDate(cover.date)}
            </p>
            <div className="nd-hero-line">
              <span className="nd-hero-num">{issue.number}</span>
              <h1 className="nd-hero-title">{resolveDisplayTitle(cover)}</h1>
            </div>
            <p className="nd-hero-deck">{coverBeat}</p>
            <Link
              href={`/issues/${cover.date}/${cover.slug}/`}
              className="nd-cta"
              {...articleLinkAttrs(cover)}
            >
              全文を読む · {cover.readMinutes} MIN READ →
            </Link>
          </div>
          <div
            className="nd-hero-img"
            style={cover.heroImage ? { backgroundImage: `url(${cover.heroImage})` } : undefined}
          >
            {!cover.heroImage && (
              <span className="nd-hero-img-cap">COVER IMAGE</span>
            )}
          </div>
        </div>
      </section>

      {/* ===== today's desk: all sources ===== */}
      <section className="nd-desk nd-wrap">
        <div className="nd-desk-head">
          <h2 className="nd-h2">Today&apos;s Desk</h2>
          <span className="nd-desk-meta">{ND_SOURCES.length} SOURCES · DAILY 06:00 JST</span>
        </div>
        <div className="nd-desk-grid">
          {ND_SOURCES.map((s) => {
            const date = latestDateBySlug.get(s.slug);
            return (
              <Link key={s.slug} href={`/sections/${s.slug}/`} className="nd-card">
                <div className="nd-card-top">
                  <span className="nd-card-tag">{s.tag}</span>
                  {date && <span className="nd-card-date">{fmtMonthDay(date)}</span>}
                </div>
                <div className="nd-card-name">{s.name}</div>
                <div className="nd-card-beat">{s.beat}</div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* ===== WSJ latest strip ===== */}
      <section className="nd-wsj nd-wrap">
        <div className="nd-wsj-head">
          <h2 className="nd-h2 nd-wsj-h">WSJ 10-Point — 最新の目次</h2>
          <Link href="/sections/wsj/" className="nd-wsj-all">すべて見る →</Link>
        </div>
        {wsjLatest.map((w) => (
          <Link
            key={w.slug}
            href={`/issues/${w.date}/${w.slug}/`}
            className="nd-wsj-row"
            {...articleLinkAttrs(w)}
          >
            <span className="nd-wsj-date">{fmtMonthDay(w.date)}</span>
            <span className="nd-wsj-title">{resolveDisplayTitle(w)}</span>
            <span className="nd-wsj-mins">{w.readMinutes} MIN</span>
          </Link>
        ))}
      </section>

      {/* ===== footer ===== */}
      <footer className="nd-footer nd-wrap">
        <div className="nd-foot-left">
          <div className="nd-foot-mark">Bolgheri<span className="nd-slash">/</span>Brief</div>
          <div className="nd-foot-desc">
            海外メディア (NYT / WSJ / FT / The Economist 等) の記事を AI が編集・要約・解釈して
            日本語で届ける、静謐な雑誌的プロダクト。毎朝 06:00 JST 配信。
          </div>
        </div>
        <div className="nd-foot-right">
          <div>Editorial AI · Foreign Press</div>
          <div>© 2026 BOLGHERI</div>
        </div>
      </footer>
    </div>
  );
}
