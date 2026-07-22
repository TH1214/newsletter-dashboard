/* ------------------------------------------------------------------
   My Interest — 共有スナップショット (read-only)

   ダッシュボードの集計結果を「その時点の凍結スナップショット」として
   URL ハッシュに埋め込める形にエンコード/デコードする。
   - Firebase / ログイン不要（純データ・ブラウザ実行）。
   - 生ログ(reading_events)は含めない。集計と最小限のリストのみ。
   - 本文スナップショットやメールアドレスは含めない（露出最小化）。
   ------------------------------------------------------------------ */

export interface BarRow {
  label: string;
  value: number;
}

export interface SnapReadItem {
  title: string;
  source: string;
  date?: string;
  start?: string;
  secs: number;
  short?: boolean;
  tags?: string[];
}

export interface SnapClickItem {
  title: string;
  source: string;
  date?: string;
  clickedDate?: string;
  time?: string;
}

export interface InterestSnapshot {
  v: 1;
  generatedAt: string; // ISO
  lookbackDays: number;
  stats: { totalReadSecs: number; reads: number; avgReadSecs: number; sources: number };
  bySourceSecs: BarRow[];
  byCategorySecs: BarRow[];
  byTagSecs: BarRow[];
  byDeviceSecs: BarRow[];
  byWeekdaySecs: BarRow[];
  byHourSecs: BarRow[];
  byClickSource: BarRow[];
  recentReads: SnapReadItem[];
  longReads: SnapReadItem[];
  shortLeave: SnapReadItem[];
  recentClicks: SnapClickItem[];
}

// --- UTF-8 safe base64url (日本語対応・ブラウザ専用) --------------------------
function bytesToB64Url(bytes: Uint8Array): string {
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64UrlToBytes(s: string): Uint8Array {
  let t = s.replace(/-/g, '+').replace(/_/g, '/');
  while (t.length % 4) t += '=';
  const bin = atob(t);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function encodeSnapshot(s: InterestSnapshot): string {
  const json = JSON.stringify(s);
  return bytesToB64Url(new TextEncoder().encode(json));
}

export function decodeSnapshot(str: string): InterestSnapshot | null {
  try {
    const json = new TextDecoder().decode(b64UrlToBytes(str));
    const obj = JSON.parse(json);
    if (obj && obj.v === 1 && obj.stats) return obj as InterestSnapshot;
    return null;
  } catch {
    return null;
  }
}
