import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CuratedToggle } from '@/components/admin/CuratedToggle';

describe('<CuratedToggle />', () => {
  it('renders aria-checked=true when curated', () => {
    render(<CuratedToggle curated onClick={() => {}} />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('renders aria-checked=false when not curated', () => {
    render(<CuratedToggle curated={false} onClick={() => {}} />);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false');
  });

  it('calls onClick on click', () => {
    const spy = vi.fn();
    render(<CuratedToggle curated={false} onClick={spy} />);
    fireEvent.click(screen.getByRole('switch'));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('honors disabled', () => {
    const spy = vi.fn();
    render(<CuratedToggle curated onClick={spy} disabled />);
    const btn = screen.getByRole('switch');
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(spy).not.toHaveBeenCalled();
  });
});
