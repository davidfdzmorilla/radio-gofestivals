import { cn } from '@/lib/utils';

interface CuratedToggleProps {
  curated: boolean;
  onClick: () => void;
  disabled?: boolean;
  ariaLabel?: string;
}

export function CuratedToggle({
  curated,
  onClick,
  disabled,
  ariaLabel = 'Toggle curated',
}: CuratedToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={curated}
      aria-label={ariaLabel}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-magenta',
        'disabled:cursor-not-allowed disabled:opacity-50',
        curated ? 'bg-magenta' : 'bg-bg-3',
      )}
    >
      <span
        className={cn(
          'inline-block h-4 w-4 rounded-full bg-fg-0 shadow transition-transform duration-150',
          curated ? 'translate-x-[18px]' : 'translate-x-0.5',
        )}
      />
    </button>
  );
}
