/* ------------------------------------------------------------------
   "Night Desk" トップページ用の純データ + 整形ヘルパー。
   Node-only import を持たないため server / client どちらからも安全。

   このモジュールは design_handoff_top_page_night_desk/README.md の
   Design Tokens を単一の正として写経したもの。
   実データ（各ソースの最新号日付・WSJ 目次・カバー）は page.tsx 側で
   lib/content.ts からビルド時に解決し、ここには "静的トークン" だけ置く。
   ------------------------------------------------------------------ */
import type { SectionSlug } from './sections';

/* ヘッダー下のピルナビ（README navPills — 全ソースではなく編集部の厳選12件・順序固定）。
   TODAY のみルート、それ以外は各セクション。href は basePath 無しの root-relative
   （Next.js が /newsletter-dashboard を自動付与する）。 */
export interface NavPill {
  label: string;
  href: string;
}
export const ND_PILLS: NavPill[] = [
  { label: 'TODAY', href: '/' },
  { label: 'WSJ', href: '/sections/wsj/' },
  { label: 'NYT Breaking', href: '/sections/nyt-bn/' },
  { label: 'DealBook', href: '/sections/dealbook/' },
  { label: 'Economist', href: '/sections/economist/' },
  { label: 'Business Insider', href: '/sections/business-insider/' },
  { label: 'Skift', href: '/sections/skift/' },
  { label: 'Buysiders', href: '/sections/buysiders/' },
  { label: 'Short Squeez', href: '/sections/short-squeez/' },
  { label: 'NYT Opinion', href: '/sections/nyt-op/' },
  { label: 'CNBC', href: '/sections/cnbc/' },
  { label: 'PERE', href: '/sections/pere/' },
];

/* Today's Desk のカード（README sources 表を順序どおりに写経）。
   name / tag / beat は確定トークン。date は各セクションの最新号から注入するため
   ここには持たせない（slug をキーに page.tsx が解決）。 */
export interface DeskSource {
  slug: SectionSlug;
  name: string;
  tag: string;
  beat: string;
}
export const ND_SOURCES: DeskSource[] = [
  { slug: 'wsj',              name: 'WSJ 10-Point',        tag: 'WSJ',   beat: '米金融・政治・テックの朝の10本' },
  { slug: 'nyt-bn',           name: 'NYT Breaking',        tag: 'NYT',   beat: 'ニューヨーク・タイムズの速報' },
  { slug: 'dealbook',         name: 'NYT DealBook',        tag: 'DEAL',  beat: 'M&A・ディール・ウォール街' },
  { slug: 'economist',        name: 'The Economist',       tag: 'ECON',  beat: '世界経済・政治の週次分析' },
  { slug: 'business-insider', name: 'Business Insider',    tag: 'BI',    beat: 'ビジネス・テックの深掘り' },
  { slug: 'skift',            name: 'Skift Daily',         tag: 'SKIFT', beat: '旅行・ホスピタリティ業界動向' },
  { slug: 'hospitality-net',  name: 'Hospitality Net',     tag: 'HN',    beat: 'ホテル業界デイリーブリーフ' },
  { slug: 'hi',               name: 'Hospitality Investor', tag: 'HI',   beat: 'ホスピタリティ投資の視点' },
  { slug: 'buysiders',        name: 'Buysiders OWS',       tag: 'BUY',   beat: 'Overheard on Wall Street' },
  { slug: 'short-squeez',     name: 'Short Squeez',        tag: 'SS',    beat: 'ウォール街の裏話とOWS' },
  { slug: 'nyt-op',           name: 'NYT Opinion',         tag: 'OP',    beat: 'オピニオン・論説の要約' },
  { slug: 'cnbc',             name: 'CNBC Breaking',       tag: 'CNBC',  beat: 'マーケット速報' },
  { slug: 'cnbc-squawk',      name: 'CNBC Squawk',         tag: 'SQWK',  beat: '朝のマーケット・ブリーフ' },
  { slug: 'pere',             name: 'PERE',                tag: 'PERE',  beat: 'プライベート不動産投資' },
  { slug: 'maverick',         name: 'Maverick AI',         tag: 'MAV',   beat: 'AI・テクノロジーの最前線' },
  { slug: 'musha',            name: 'MUSHA',               tag: 'MUSHA', beat: '投資戦略コラム' },
  { slug: 'axios-daily',      name: 'Axios Daily',         tag: 'AXIO',  beat: '今日の要点を1分で' },
  { slug: 'axios-ai',         name: 'Axios AI/Deals',      tag: 'AX·AI', beat: 'AI＋PE/M&A/VC' },
  { slug: 'axios-frontier',   name: 'Axios Frontier',      tag: 'AX·F',  beat: '防衛・車・2028' },
  { slug: 'nikkei-hack',      name: 'My CLIP',             tag: 'CLIP',  beat: '本人クリップ' },
];

/* YYYY-MM-DD → "MM·DD"（Desk カード日付 / WSJ strip 日付）。 */
export function fmtMonthDay(date: string): string {
  const m = date.match(/^\d{4}-(\d{2})-(\d{2})/);
  return m ? `${m[1]}·${m[2]}` : date;
}

/* YYYY-MM-DD → "YYYY·MM·DD"（hero キッカー）。 */
export function fmtDotDate(date: string): string {
  const m = date.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[1]}·${m[2]}·${m[3]}` : date;
}
