import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface Props extends HTMLAttributes<HTMLSpanElement> {
  sticker?: boolean;
  tone?: 'neutral' | 'magenta' | 'cyan' | 'wave';
}

const toneMap: Record<NonNullable<Props['tone']>, string> = {
  neutral: 'border-fg-3 bg-bg-2 text-fg-1',
  magenta: 'border-magenta/60 bg-magenta-soft text-fg-0',
  cyan: 'border-cyan/60 bg-cyan-soft text-fg-0',
  wave: 'border-wave/60 bg-wave-soft text-fg-0',
};

export function Badge({ className, sticker = false, tone = 'neutral', ...props }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide',
        toneMap[tone],
        sticker && 'shadow-sticker-sm -rotate-1',
        className,
      )}
      {...props}
    />
  );
}
