import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { DeleteButton } from '@/components/admin/DeleteButton';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

describe('<DeleteButton />', () => {
  it('starts with the default label', () => {
    render(<DeleteButton onDelete={() => {}} />);
    expect(screen.getByRole('button')).toHaveTextContent(/delete/i);
    expect(screen.getByRole('button')).not.toHaveTextContent(/confirm/i);
  });

  it('first click switches to confirm state', () => {
    render(<DeleteButton onDelete={() => {}} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toHaveTextContent(/confirm delete/i);
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('second click within timeout fires onDelete', () => {
    const spy = vi.fn();
    render(<DeleteButton onDelete={spy} />);
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByRole('button'));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('auto-cancels after timeoutMs without second click', () => {
    render(<DeleteButton onDelete={() => {}} timeoutMs={500} />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toHaveTextContent(/confirm/i);

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(screen.getByRole('button')).not.toHaveTextContent(/confirm/i);
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('disabled prevents both clicks', () => {
    const spy = vi.fn();
    render(<DeleteButton onDelete={spy} disabled />);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(spy).not.toHaveBeenCalled();
    expect(btn).not.toHaveTextContent(/confirm/i);
  });
});
