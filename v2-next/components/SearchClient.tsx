'use client';
import { useMemo, useState } from 'react';
import Link from 'next/link';

export interface SearchRecord {
  title: string;
  summary: string;
  tags: string[];
  section: string;
  sectionLabel: string;
  eyebrow: string;
  date: string;
  href: string;
}

const MAX_RESULTS = 80;

function norm(s: string): string {
  return (s || '').toLowerCase();
}

export function SearchClient({ index }: { index: SearchRecord[] }) {
  const [q, setQ] = useState('');

  // 各レコードの検索対象文字列を事前結合（初回のみ）
  const haystacks = useMemo(
    () =>
      index.map((r) =>
        norm([r.title, r.summary, r.tags.join(' '), r.sectionLabel, r.date].join(' ')),
      ),
    [index],
  );

  const terms = norm(q).split(/\s+/).filter(Boolean);

  const results = useMemo(() => {
    if (terms.length === 0) return [];
    const out: SearchRecord[] = [];
    for (let i = 0; i < index.length && out.length < MAX_RESULTS; i++) {
      const hay = haystacks[i];
      if (terms.every((t) => hay.includes(t))) out.push(index[i]);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, index, haystacks]);

  const hasQuery = terms.length > 0;

  return (
    <div className="wb-search">
      <label className="wb-search-box">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
          <circle cx="11" cy="11" r="7"></circle>
          <path d="M20 20l-3.5-3.5"></path>
        </svg>
        <input
          className="wb-search-input"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="キーワードで記事を検索（タイトル・要約・タグ・ソース）"
          aria-label="記事検索"
          autoFocus
        />
        {q && (
          <button type="button" className="wb-search-clear" onClick={() => setQ('')} aria-label="クリア">
            ×
          </button>
        )}
      </label>

      <p className="wb-search-status">
        {!hasQuery
          ? `${index.length} 記事から検索します。キーワードを入力してください。`
          : results.length === 0
            ? `「${q}」に一致する記事はありません。`
            : `「${q}」の検索結果 ${results.length}${results.length >= MAX_RESULTS ? '+' : ''} 件`}
      </p>

      <ul className="wb-search-results">
        {results.map((r) => (
          <li key={r.href} className="wb-search-item">
            <Link href={r.href} className="wb-search-link">
              <p className="wb-search-eyebrow">
                {r.eyebrow} · {r.date}
              </p>
              <h3 className="wb-search-title">{r.title}</h3>
              {r.summary && <p className="wb-search-deck">{r.summary}</p>}
              {r.tags.length > 0 && (
                <p className="wb-search-tags">
                  {r.tags.slice(0, 6).map((t) => (
                    <span key={t} className="wb-search-tag">
                      {t}
                    </span>
                  ))}
                </p>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
