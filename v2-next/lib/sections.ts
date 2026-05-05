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
  { slug: 'short-squeez',     label: 'Short Squeez OWS',  eyebrow: 'WALL STREET · GOSSIP' },
  { slug: 'nyt-op',           label: 'NYT Opinion Today', eyebrow: 'OPINION · COMMENTARY' },
] as const;

export type SectionSlug = (typeof SECTIONS)[number]['slug'];

export function getSectionInfo(slug: SectionSlug) {
  return SECTIONS.find((s) => s.slug === slug)!;
}
