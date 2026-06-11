'use client';
import { useEffect, useState } from 'react';

/**
 * 全ページ共通「ページ最上部へ戻る」ボタン。
 * 一定量スクロールしたら右下に出現し、クリックで最上部へスムーズスクロール。
 * デザインは既存トーン（白黒・非装飾）に合わせた控えめなもの。
 */
export function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 600);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <button
      type="button"
      className={`back-to-top ${visible ? 'is-visible' : ''}`}
      aria-label="ページ最上部へ戻る"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    </button>
  );
}
