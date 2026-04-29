import Link from 'next/link';
import type { ActivityEntry } from '@/lib/admin/dashboard';
import { cn } from '@/lib/utils';

interface ActivityFeedProps {
  entries: ActivityEntry[];
}

export function formatRelative(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const diffMs = now.getTime() - date.getTime();
  if (diffMs < 0) return 'just now';
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

const DECISION_STYLES: Record<string, string> = {
  approve: 'bg-cyan-soft text-cyan',
  reject: 'bg-magenta-soft text-warm',
  reclassify: 'bg-bg-3 text-fg-1',
  edit_metadata: 'bg-wave-soft text-warm',
  toggle_curated: 'bg-magenta-soft text-warm',
  change_status: 'bg-cyan-soft/60 text-cyan',
};

export function ActivityFeed({ entries }: ActivityFeedProps) {
  if (entries.length === 0) {
    return (
      <p className="text-fg-2 py-4 text-center text-sm">No activity yet</p>
    );
  }
  return (
    <ul className="divide-fg-3/30 divide-y" data-testid="activity-feed">
      {entries.map((entry) => {
        const decisionClass =
          DECISION_STYLES[entry.decision] ?? 'bg-bg-3 text-fg-1';
        return (
          <li
            key={entry.id}
            className="flex items-start gap-2 py-2 text-sm"
          >
            <span
              className={cn(
                'shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest',
                decisionClass,
              )}
            >
              {entry.decision}
            </span>
            <div className="min-w-0 flex-1">
              {entry.station_slug ? (
                <Link
                  href={`/admin/stations/${entry.station_id}`}
                  className="text-fg-0 hover:text-magenta block truncate font-medium transition-colors"
                >
                  {entry.station_name ?? entry.station_slug}
                </Link>
              ) : (
                <span className="text-fg-2 italic">(deleted station)</span>
              )}
              {entry.notes ? (
                <p className="text-fg-2 truncate text-xs">{entry.notes}</p>
              ) : null}
              {entry.admin_email ? (
                <p className="text-fg-3 truncate font-mono text-[10px] uppercase tracking-widest">
                  {entry.admin_email}
                </p>
              ) : null}
            </div>
            <time
              dateTime={entry.created_at}
              className="text-fg-2 shrink-0 font-mono text-[10px] uppercase tracking-widest"
            >
              {formatRelative(entry.created_at)}
            </time>
          </li>
        );
      })}
    </ul>
  );
}
