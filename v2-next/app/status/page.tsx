import Link from 'next/link';
import { MetaBar } from '@/components/MetaBar';
import { Chrome } from '@/components/Chrome';
import { SiteFooter } from '@/components/SiteFooter';
import {
  SECTIONS,
  getAllArticles,
  getArticlesBySection,
  getLatestIssue,
} from '@/lib/content';

export const metadata = {
  title: 'Status — Bolgheri Daily Brief',
  description: 'Pipeline health and delivery status for the past 7 days',
};

interface DailyDelivery {
  date: string;
  count: number;        // 0..9 sources delivered for this date
  sources: string[];    // which sources delivered
}

function getRecentDays(days: number): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = 0; i < days; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

export default function StatusPage() {
  const articles = getAllArticles();
  const issue = getLatestIssue();

  // 過去 14 日間の配信実績 (今日を含む)
  const days = getRecentDays(14);
  const deliveries: DailyDelivery[] = days.map((date) => {
    const todayArticles = articles.filter((a) => a.date === date);
    return {
      date,
      count: todayArticles.length,
      sources: todayArticles.map((a) => a.section),
    };
  });

  // 過去 7 日の delivery rate (target = 8 sources/day, buysiders は週次で除外)
  const last7 = deliveries.slice(0, 7);
  const TARGET_DAILY = 8;
  const totalDelivered = last7.reduce((s, d) => s + Math.min(d.count, TARGET_DAILY), 0);
  const totalExpected = last7.length * TARGET_DAILY;
  const successRate = totalExpected > 0 ? Math.round((totalDelivered / totalExpected) * 100) : 0;

  // ソース別の最終配信日
  const sourceLastDelivery = SECTIONS.map((sec) => {
    const arts = getArticlesBySection(sec.slug);
    const last = arts.length > 0 ? arts[0] : null; // arts is sorted desc by date
    const lastDate = last ? last.date : null;
    const totalCount = arts.length;
    let staleness: 'fresh' | 'recent' | 'stale' | 'none' = 'none';
    if (lastDate) {
      const daysSince = Math.floor(
        (Date.now() - new Date(lastDate + 'T00:00:00Z').getTime()) / (1000 * 60 * 60 * 24)
      );
      if (daysSince <= 1) staleness = 'fresh';
      else if (daysSince <= 7) staleness = 'recent';
      else staleness = 'stale';
    }
    return {
      slug: sec.slug,
      label: sec.label,
      lastDate,
      totalCount,
      staleness,
    };
  });

  return (
    <>
      <MetaBar issue={issue} suffix="Status" />
      <Chrome>
        <section className="wb-arch-hero">
          <p className="wb-eyebrow">PIPELINE · HEALTH</p>
          <h1 className="wb-h1">Status</h1>
          <p className="wb-deck">
            Pipeline health and delivery status for the past 14 days. Target: 8 daily sources
            (Buysiders runs on weekly cadence and is excluded from the daily target).
          </p>
        </section>

        {/* ─── Key metrics ─── */}
        <section style={{ padding: '32px 0', borderTop: '1px solid var(--rule)' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 24,
            }}
          >
            <Metric label="7-Day Delivery Rate" value={`${successRate}%`} />
            <Metric label="Articles (7 days)" value={String(totalDelivered)} sublabel={`of ${totalExpected} target`} />
            <Metric label="Total Archive" value={String(articles.length)} sublabel="briefings since 2026-04-01" />
            <Metric label="Latest Issue" value={`#${String(issue.number).padStart(3, '0')}`} sublabel={issue.date} />
          </div>
        </section>

        {/* ─── Per-day delivery heatmap ─── */}
        <section style={{ padding: '32px 0', borderTop: '1px solid var(--rule)' }}>
          <h2 className="wb-h2" style={{ marginBottom: 18 }}>Daily Delivery (Last 14 Days)</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--ink)' }}>
                <th style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600 }}>Date</th>
                <th style={{ textAlign: 'right', padding: '8px 12px', fontWeight: 600 }}>Delivered</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600 }}>Sources</th>
              </tr>
            </thead>
            <tbody>
              {deliveries.map((d) => {
                const dow = new Date(d.date + 'T00:00:00Z').toLocaleDateString('en-US', {
                  weekday: 'short',
                  timeZone: 'UTC',
                });
                const color = d.count >= 7 ? '#1a7f37' : d.count >= 4 ? '#bf8700' : d.count >= 1 ? '#cf222e' : '#8c959f';
                return (
                  <tr key={d.date} style={{ borderBottom: '1px solid var(--rule)' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ color: 'var(--walnut)', fontSize: 11, letterSpacing: '0.18em', marginRight: 8, textTransform: 'uppercase' }}>{dow}</span>
                      {d.date}
                    </td>
                    <td style={{ textAlign: 'right', padding: '10px 12px', color, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                      {d.count} / {TARGET_DAILY}
                    </td>
                    <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--walnut)' }}>
                      {d.sources.join(', ') || '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        {/* ─── Per-source health ─── */}
        <section style={{ padding: '32px 0', borderTop: '1px solid var(--rule)' }}>
          <h2 className="wb-h2" style={{ marginBottom: 18 }}>Per-Source Health</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--ink)' }}>
                <th style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600 }}>Source</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600 }}>Status</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600 }}>Last Delivery</th>
                <th style={{ textAlign: 'right', padding: '8px 12px', fontWeight: 600 }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {sourceLastDelivery.map((s) => {
                const statusColor =
                  s.staleness === 'fresh' ? '#1a7f37' :
                  s.staleness === 'recent' ? '#bf8700' :
                  s.staleness === 'stale' ? '#cf222e' : '#8c959f';
                const statusLabel =
                  s.staleness === 'fresh' ? '● Fresh' :
                  s.staleness === 'recent' ? '● Recent' :
                  s.staleness === 'stale' ? '● Stale' : '○ None';
                return (
                  <tr key={s.slug} style={{ borderBottom: '1px solid var(--rule)' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <Link href={`/sections/${s.slug}/`} style={{ color: 'var(--ink)', borderBottom: '1px dotted var(--walnut)' }}>
                        {s.label}
                      </Link>
                    </td>
                    <td style={{ padding: '10px 12px', color: statusColor, fontWeight: 600 }}>
                      {statusLabel}
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--walnut)', fontVariantNumeric: 'tabular-nums' }}>
                      {s.lastDate || '—'}
                    </td>
                    <td style={{ textAlign: 'right', padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}>
                      {s.totalCount}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        {/* ─── Pipeline architecture ─── */}
        <section style={{ padding: '32px 0', borderTop: '1px solid var(--rule)' }}>
          <h2 className="wb-h2" style={{ marginBottom: 18 }}>Pipeline</h2>
          <p style={{ color: 'var(--walnut)', lineHeight: 1.7 }}>
            毎朝 06:00 JST に <strong>GitHub Actions</strong> が起動し、Gmail 受信箱から最新ニュースレターを取得 →
            Gemini 2.5-flash で日本語編集 (Groq / GitHub Models フォールバック内蔵) → Hero 画像を Pollinations.ai で生成 →
            Next.js でサイト再ビルド → GitHub Pages へ配信。全工程 1〜3 分。人的介入は存在しない。
          </p>
          <p style={{ color: 'var(--walnut)', marginTop: 12, fontSize: 13 }}>
            <strong>Reliability features</strong>: Triple-backend fallback chain · Matrix-parallel processing (max 3 concurrent) ·
            File integrity validation · Auto-issue creation on critical failure · workflow_run-based deploy trigger
          </p>
        </section>
      </Chrome>
      <SiteFooter />
    </>
  );
}

function Metric({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string;
  sublabel?: string;
}) {
  return (
    <div style={{ padding: '16px 20px', border: '1px solid var(--rule)', background: 'var(--paper)' }}>
      <p style={{ fontSize: 10.5, letterSpacing: '0.22em', textTransform: 'uppercase', color: 'var(--walnut)', marginBottom: 8 }}>
        {label}
      </p>
      <p style={{ fontSize: 32, fontWeight: 600, lineHeight: 1, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </p>
      {sublabel && (
        <p style={{ fontSize: 12, color: 'var(--walnut)', marginTop: 6 }}>{sublabel}</p>
      )}
    </div>
  );
}
