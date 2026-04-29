import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { RunButton } from '@/components/admin/RunButton';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

describe('<RunButton />', () => {
  it('starts with the default label', () => {
    render(<RunButton onRun={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/^Run$/);
  });

  it('first click switches to confirm state', () => {
    render(<RunButton onRun={() => {}} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toHaveTextContent(/confirm/i);
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('second click within timeout fires onRun', () => {
    const spy = vi.fn();
    render(<RunButton onRun={spy} />);
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByRole('button'));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('auto-cancels after timeout without second click', () => {
    render(<RunButton onRun={() => {}} timeoutMs={500} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toHaveTextContent(/confirm/i);
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(screen.getByRole('button')).toHaveTextContent(/^Run$/);
  });

  it('disabled prevents both clicks', () => {
    const spy = vi.fn();
    render(<RunButton onRun={spy} disabled />);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(spy).not.toHaveBeenCalled();
  });
});
