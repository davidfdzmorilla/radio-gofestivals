interface BarChartProps {
  data: { label: string; value: number; sublabel?: string }[];
  maxBars?: number;
}

export function BarChart({ data, maxBars }: BarChartProps) {
  const visible = maxBars ? data.slice(0, maxBars) : data;
  if (visible.length === 0) {
    return (
      <p className="text-fg-2 py-4 text-center text-sm">No data</p>
    );
  }
  const max = Math.max(...visible.map((d) => d.value), 1);

  return (
    <ul className="space-y-2" data-testid="bar-chart">
      {visible.map((item, i) => (
        <li key={`${item.label}-${i}`} className="space-y-1">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className="text-fg-1 truncate font-medium">
              {item.label}
              {item.sublabel ? (
                <span className="text-fg-2 ml-2 font-mono">
                  {item.sublabel}
                </span>
              ) : null}
            </span>
            <span className="text-fg-2 font-mono">
              {item.value.toLocaleString()}
            </span>
          </div>
          <div
            className="bg-bg-3/60 h-2 overflow-hidden rounded-full"
            role="progressbar"
            aria-valuenow={item.value}
            aria-valuemin={0}
            aria-valuemax={max}
          >
            <div
              className="bg-magenta h-full transition-all"
              style={{ width: `${(item.value / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
