import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BarChart } from '@/components/admin/BarChart';

describe('<BarChart />', () => {
  it('shows "No data" when array is empty', () => {
    render(<BarChart data={[]} />);
    expect(screen.getByText(/No data/i)).toBeInTheDocument();
  });

  it('renders one bar per data item', () => {
    render(
      <BarChart
        data={[
          { label: 'A', value: 10 },
          { label: 'B', value: 5 },
          { label: 'C', value: 1 },
        ]}
      />,
    );
    const bars = screen.getAllByRole('progressbar');
    expect(bars).toHaveLength(3);
  });

  it('respects maxBars', () => {
    render(
      <BarChart
        data={[
          { label: 'A', value: 1 },
          { label: 'B', value: 2 },
          { label: 'C', value: 3 },
          { label: 'D', value: 4 },
        ]}
        maxBars={2}
      />,
    );
    expect(screen.getAllByRole('progressbar')).toHaveLength(2);
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
    expect(screen.queryByText('D')).not.toBeInTheDocument();
  });

  it('width is proportional to max value', () => {
    render(
      <BarChart
        data={[
          { label: 'A', value: 100 },
          { label: 'B', value: 50 },
        ]}
      />,
    );
    const bars = screen.getAllByRole('progressbar');
    // The inner div carries the width style.
    const inner0 = bars[0]!.firstElementChild as HTMLElement;
    const inner1 = bars[1]!.firstElementChild as HTMLElement;
    expect(inner0.style.width).toBe('100%');
    expect(inner1.style.width).toBe('50%');
  });

  it('formats large numbers with locale separators', () => {
    render(<BarChart data={[{ label: 'X', value: 1234 }]} />);
    expect(screen.getByText('1,234')).toBeInTheDocument();
  });
});
