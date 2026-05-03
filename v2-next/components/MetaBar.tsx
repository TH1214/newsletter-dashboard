import type { Issue } from '@/lib/content';

export function MetaBar({ issue, suffix }: { issue: Issue; suffix?: string }) {
  const d = new Date(issue.date + 'T06:00:00+09:00');
  const wd = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getUTCDay()];
  const month = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getUTCMonth()];
  const left = `Vol. 06 / ${d.getUTCFullYear()}` + ` · Issue ${issue.number}${suffix ? ' · ' + suffix : ''}`;
  return (
    <div className="meta-bar">
      <span className="left">{left.split(' · ').map((s, i, arr) => (
        <span key={i}>{s}{i < arr.length - 1 && <span className="dot"> ● </span>}</span>
      ))}</span>
      <span className="center">{wd} · {d.getUTCDate()} {month} · 06:00 JST</span>
      <span className="right">Explored · Curated · Briefed</span>
    </div>
  );
}
