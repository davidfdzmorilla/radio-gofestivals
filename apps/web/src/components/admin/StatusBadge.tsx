import { cn } from '@/lib/utils';

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-cyan-soft text-cyan',
  broken: 'bg-magenta-soft text-warm',
  inactive: 'bg-bg-3 text-fg-2',
  pending: 'bg-wave-soft text-warm',
  rejected: 'bg-magenta-soft text-warm',
  duplicate: 'bg-wave-soft text-fg-1',
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? 'bg-bg-3 text-fg-2';
  return (
    <span
      className={cn(
        'inline-block rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest',
        style,
      )}
    >
      {status}
    </span>
  );
}
