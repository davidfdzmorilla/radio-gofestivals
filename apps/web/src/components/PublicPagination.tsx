import Link from 'next/link';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PublicPaginationProps {
  currentPage: number;
  totalPages: number;
  /**
   * Given a page number, returns the absolute href for that page with all
   * other query params (country, curated…) preserved by the caller.
   */
  buildHref: (page: number) => string;
  pageLabel: string;
  prevLabel: string;
  nextLabel: string;
}

const buttonBase =
  'inline-flex items-center gap-1 rounded-md border border-fg-3 px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-fg-1 transition-colors';

const buttonActive = 'hover:border-magenta hover:text-fg-0 hover:bg-bg-2';

const buttonDisabled = 'cursor-not-allowed opacity-40';

export function PublicPagination({
  currentPage,
  totalPages,
  buildHref,
  pageLabel,
  prevLabel,
  nextLabel,
}: PublicPaginationProps) {
  if (totalPages <= 1) return null;

  const hasPrev = currentPage > 1;
  const hasNext = currentPage < totalPages;

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-center gap-3 py-6"
    >
      {hasPrev ? (
        <Link
          href={buildHref(currentPage - 1)}
          aria-label={prevLabel}
          rel="prev"
          className={cn(buttonBase, buttonActive)}
        >
          <ChevronLeft size={16} />
          <span className="hidden sm:inline">{prevLabel}</span>
        </Link>
      ) : (
        <span
          aria-disabled="true"
          aria-label={prevLabel}
          className={cn(buttonBase, buttonDisabled)}
        >
          <ChevronLeft size={16} />
          <span className="hidden sm:inline">{prevLabel}</span>
        </span>
      )}

      <span
        aria-current="page"
        className="px-2 font-mono text-xs uppercase tracking-widest text-fg-2"
      >
        {pageLabel}
      </span>

      {hasNext ? (
        <Link
          href={buildHref(currentPage + 1)}
          aria-label={nextLabel}
          rel="next"
          className={cn(buttonBase, buttonActive)}
        >
          <span className="hidden sm:inline">{nextLabel}</span>
          <ChevronRight size={16} />
        </Link>
      ) : (
        <span
          aria-disabled="true"
          aria-label={nextLabel}
          className={cn(buttonBase, buttonDisabled)}
        >
          <span className="hidden sm:inline">{nextLabel}</span>
          <ChevronRight size={16} />
        </span>
      )}
    </nav>
  );
}
