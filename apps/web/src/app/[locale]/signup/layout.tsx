import type { Metadata } from 'next';

// Página privada/transaccional: el disallow de robots.txt no impide que
// Google indexe la URL si está enlazada — hace falta el meta noindex.
export const metadata: Metadata = { robots: { index: false } };

export default function NoIndexLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
