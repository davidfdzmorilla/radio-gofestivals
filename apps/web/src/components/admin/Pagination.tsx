import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PaginationProps {
  page: number;
  pages: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pages, onChange }: PaginationProps) {
  const atStart = page <= 1;
  const atEnd = page >= pages;

  const btn =
    'inline-flex h-8 w-8 items-center justify-center rounded-md border border-fg-3/40 text-fg-2 hover:border-magenta hover:text-fg-0 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-fg-3/40 disabled:hover:text-fg-2 transition-colors';

  return (
    <nav
      className="flex items-center justify-center gap-2 py-2"
      aria-label="Pagination"
    >
      <button
        type="button"
        onClick={() => onChange(1)}
        disabled={atStart}
        className={btn}
        aria-label="First page"
      >
        <ChevronsLeft size={16} />
      </button>
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={atStart}
        className={btn}
        aria-label="Previous page"
      >
        <ChevronLeft size={16} />
      </button>
      <span className={cn('px-3 font-mono text-xs uppercase tracking-widest text-fg-2')}>
        {page} / {pages}
      </span>
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={atEnd}
        className={btn}
        aria-label="Next page"
      >
        <ChevronRight size={16} />
      </button>
      <button
        type="button"
        onClick={() => onChange(pages)}
        disabled={atEnd}
        className={btn}
        aria-label="Last page"
      >
        <ChevronsRight size={16} />
      </button>
    </nav>
  );
}
