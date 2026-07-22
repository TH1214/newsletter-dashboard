'use client';
import { useEffect, useState } from 'react';

/* ライブ JST 時計。トップページで唯一のクライアント状態（README State Management）。
   HH:MM:SS を毎秒更新し、常に Asia/Tokyo で計算する（閲覧者のタイムゾーン非依存）。
   点滅ドットは CSS の @keyframes nd-blink（prefers-reduced-motion で停止）。 */
function jstNow(): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Tokyo',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date());
}

export function NightDeskClock() {
  // SSR/初期HTMLは固定文字列にし、hydration 後に実時刻へ（mismatch 回避）。
  const [clock, setClock] = useState('--:--:--');

  useEffect(() => {
    setClock(jstNow());
    const t = setInterval(() => setClock(jstNow()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <span className="nd-clock">
      <span className="nd-dot" aria-hidden="true" />
      {clock} JST
    </span>
  );
}
