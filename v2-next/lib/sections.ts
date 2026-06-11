/* ------------------------------------------------------------------
   Pure-data section list. NO Node-only imports here.
   Safe to import from both server- and client-components.
   ------------------------------------------------------------------ */
export const SECTIONS = [
  { slug: 'nyt-bn',           label: 'NYT Breaking News', eyebrow: 'BREAKING · WORLD' },
  { slug: 'wsj',              label: 'WSJ 10-Point',      eyebrow: 'WALL STREET · BUSINESS' },
  { slug: 'dealbook',         label: 'NYT DealBook',      eyebrow: 'BRIEF · WALL STREET' },
  { slug: 'economist',        label: 'The Economist',     eyebrow: 'GLOBAL · POLICY' },
  { slug: 'business-insider', label: 'Business Insider',  eyebrow: 'BUSINESS · TECH' },
  { slug: 'skift',            label: 'Skift Daily',       eyebrow: 'TRAVEL · HOSPITALITY' },
  { slug: 'buysiders',        label: 'Buysiders OWS',     eyebrow: 'M&A · FINANCE' },
  { slug: 'short-squeez',     label: 'Short Squeez OWS',  eyebrow: 'WALL STREET · INTELLIGENCE' },
  { slug: 'nyt-op',           label: 'NYT Opinion Today', eyebrow: 'OPINION · COMMENTARY' },
  { slug: 'cnbc',             label: 'CNBC Breaking News', eyebrow: 'BREAKING · FINANCE' },
  { slug: 'cnbc-squawk',      label: 'CNBC Morning Squawk',          eyebrow: 'MARKETS · MORNING BRIEF' },
  { slug: 'hospitality-net', label: 'Hospitality Net Daily Brief',  eyebrow: 'HOSPITALITY · REAL ESTATE' },
  { slug: 'pere',            label: 'PERE',                         eyebrow: 'PRIVATE EQUITY · REAL ESTATE' },
  { slug: 'maverick',        label: 'Maverick AI',                  eyebrow: 'AI TOOLS · MAVERICK' },
  { slug: 'musha',           label: 'MUSHA',                        eyebrow: 'STRATEGY · MACRO' },
  { slug: 'nikkei-hack',     label: 'Nikkei Hack',                  eyebrow: 'NIKKEI · MY CLIPPINGS' },
] as const;

export type SectionSlug = (typeof SECTIONS)[number]['slug'];

export function getSectionInfo(slug: SectionSlug) {
  return SECTIONS.find((s) => s.slug === slug)!;
}
