import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StationCover } from '@/components/stations/StationCover';

const base = {
  slug: 'radio-q',
  name: 'Radio Q',
  color: '#8B4EE8',
  size: 'sm' as const,
  className: 'h-14 w-14 rounded-lg',
  textClassName: 'text-xl',
};

describe('StationCover', () => {
  it('shows the real logo from our own API when the station has one', () => {
    const { container } = render(<StationCover {...base} logoHash="abc123def456" />);
    const img = container.querySelector('img');
    expect(img).not.toBeNull();
    const src = new URL(img!.getAttribute('src')!);
    expect(src.pathname).toBe('/api/v1/stations/radio-q/logo');
    expect(src.searchParams.get('size')).toBe('sm');
    expect(src.searchParams.get('v')).toBe('abc123def456');
  });

  it('requests the large rendition for large covers', () => {
    const { container } = render(<StationCover {...base} size="lg" logoHash="abc123def456" />);
    expect(new URL(container.querySelector('img')!.getAttribute('src')!).searchParams.get('size')).toBe('lg');
  });

  it('puts the logo on a light tile and keeps it decorative, lazy and uncropped', () => {
    const { container } = render(<StationCover {...base} logoHash="abc123def456" />);
    const img = container.querySelector('img')!;
    expect(img).toHaveAttribute('alt', '');
    expect(img).toHaveAttribute('loading', 'lazy');
    expect(img.className).toContain('object-contain');
    expect(img.className).toContain('bg-fg-0');
  });

  it.each([null, undefined, ''])('falls back to the initials when there is no logo (%s)', (logoHash) => {
    const { container } = render(<StationCover {...base} logoHash={logoHash} />);
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('RQ')).toBeInTheDocument();
  });

  it('uses the genre color with a readable ink for the fallback', () => {
    const { container } = render(<StationCover {...base} logoHash={null} color="#FDE047" />);
    const box = container.firstElementChild as HTMLElement;
    expect(box.style.backgroundColor).toBe('rgb(253, 224, 71)');
    expect(box.style.color).toBe('rgb(12, 11, 9)'); // tinta oscura sobre amarillo
  });

  it('falls back to the initials when the image fails to load', () => {
    const { container } = render(<StationCover {...base} logoHash="abc123def456" />);
    fireEvent.error(container.querySelector('img')!);
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('RQ')).toBeInTheDocument();
  });

  it('keeps the box dimensions in both states (no layout shift)', () => {
    const { container, rerender } = render(<StationCover {...base} logoHash="abc123def456" />);
    expect((container.firstElementChild as HTMLElement).className).toContain('h-14 w-14');
    rerender(<StationCover {...base} logoHash={null} />);
    expect((container.firstElementChild as HTMLElement).className).toContain('h-14 w-14');
  });

  it('lets the caller hide the box on small screens (the player does)', () => {
    const { container } = render(<StationCover {...base} className="hidden h-12 w-12 sm:flex" logoHash={null} />);
    const cls = (container.firstElementChild as HTMLElement).className;
    expect(cls).toContain('hidden');
    expect(cls).not.toMatch(/(^|\s)flex(\s|$)/); // twMerge: el `flex` base no pisa al `hidden`
  });
});
