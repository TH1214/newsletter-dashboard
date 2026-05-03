'use client';
import { useState } from 'react';
import { SiteHeader } from './SiteHeader';
import { HamburgerOverlay } from './HamburgerOverlay';

export function Chrome({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <SiteHeader onMenuClick={() => setOpen(true)} />
      <HamburgerOverlay open={open} onClose={() => setOpen(false)} />
      {children}
    </>
  );
}
