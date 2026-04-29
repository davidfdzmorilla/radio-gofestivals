import { cn } from '@/lib/utils';

export type KpiAccent = 'default' | 'success' | 'warning' | 'destructive';

interface KpiCardProps {
  label: string;
  value: number | string;
  sublabel?: string;
  accent?: KpiAccent;
}

const ACCENT_CLASSES: Record<KpiAccent, string> = {
  default: 'border-fg-3/40 bg-bg-2/40',
  success: 'border-cyan/40 bg-cyan-soft/40',
  warning: 'border-warm/40 bg-magenta-soft/30',
  destructive: 'border-magenta/40 bg-magenta-soft/40',
};

const VALUE_TONE: Record<KpiAccent, string> = {
  default: 'text-fg-0',
  success: 'text-cyan',
  warning: 'text-warm',
  destructive: 'text-warm',
};

export function KpiCard({
  label,
  value,
  sublabel,
  accent = 'default',
}: KpiCardProps) {
  const display =
    typeof value === 'number' ? value.toLocaleString() : value;
  return (
    <div
      data-accent={accent}
      className={cn(
        'rounded-lg border p-4 transition-colors',
        ACCENT_CLASSES[accent],
      )}
    >
      <div className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
        {label}
      </div>
      <div
        className={cn(
          'mt-1 font-display text-3xl font-bold',
          VALUE_TONE[accent],
        )}
      >
        {display}
      </div>
      {sublabel ? (
        <div className="text-fg-2 mt-1 text-xs">{sublabel}</div>
      ) : null}
    </div>
  );
}
