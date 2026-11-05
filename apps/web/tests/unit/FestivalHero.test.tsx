import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FestivalHero } from '@/components/festivals/FestivalHero';
import type { Festival } from '@/lib/festivals';

// next/image necesita el optimizador; aquí basta un <img> que deje disparar onError.
vi.mock('next/image', () => ({
  default: ({ src, alt, onError }: { src: string; alt: string; onError?: () => void }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} onError={onError} />
  ),
}));

const IMG = 'https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/festivals/x/y.webp';

function festival(over: Partial<Festival> = {}): Festival {
  return {
    id: '17',
    name: 'Rave on Snow Festival',
    startDate: '2026-12-10T00:00:00.000Z',
    endDate: '2026-12-13T00:00:00.000Z',
    location: 'Saalbach, Salzburg, Austria',
    locationEn: null,
    countryCode: 'AT',
    website: 'https://raveonsnow.com',
    imageUrl: IMG,
    description: 'Festival alpino.',
    descriptionEn: null,
    genres: ['Techno'],
    ...over,
  };
}

const base = {
  locale: 'es',
  color: '#8B4EE8',
  phase: 'upcoming' as const,
  phaseLabel: 'Empieza dentro de 4 semanas',
  countryName: 'Austria',
  labels: { viewOnGofestivals: 'Ver en gofestivals', officialSite: 'Web oficial' },
};

describe('FestivalHero', () => {
  it('shows the festival, its phase, and links to its gofestivals page', () => {
    render(<FestivalHero festival={festival()} {...base} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Rave on Snow Festival' })).toBeInTheDocument();
    expect(screen.getByText('Empieza dentro de 4 semanas')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver en gofestivals' })).toHaveAttribute(
      'href',
      'https://gofestivals.es/es/festival/17/rave-on-snow-festival',
    );
  });

  it('marks the official website nofollow and drops non-http(s) URLs (XSS)', () => {
    const { rerender } = render(<FestivalHero festival={festival()} {...base} />);
    const link = screen.getByRole('link', { name: 'Web oficial' });
    expect(link).toHaveAttribute('href', 'https://raveonsnow.com/');
    expect(link.getAttribute('rel')).toContain('nofollow');

    rerender(<FestivalHero festival={festival({ website: 'javascript:alert(1)' })} {...base} />);
    expect(screen.queryByRole('link', { name: 'Web oficial' })).toBeNull();
    rerender(<FestivalHero festival={festival({ website: null })} {...base} />);
    expect(screen.queryByRole('link', { name: 'Web oficial' })).toBeNull();
  });

  it('renders the image when it is valid and falls back to initials when it fails to load', () => {
    render(<FestivalHero festival={festival()} {...base} />);
    const img = screen.getByRole('img', { name: 'Rave on Snow Festival' });
    expect(img.tagName).toBe('IMG');
    fireEvent.error(img);
    const fallback = screen.getByRole('img', { name: 'Rave on Snow Festival' });
    expect(fallback.tagName).toBe('DIV');
    expect(fallback).toHaveTextContent('RO');
  });

  it('uses the fallback straight away for a missing or untrusted image host', () => {
    for (const imageUrl of [null, 'https://evil.example/festivals/x.webp']) {
      const { unmount } = render(<FestivalHero festival={festival({ imageUrl })} {...base} />);
      expect(screen.getByRole('img', { name: 'Rave on Snow Festival' }).tagName).toBe('DIV');
      unmount();
    }
  });

  it('adds the country only when the place does not already mention it', () => {
    const { rerender } = render(<FestivalHero festival={festival()} {...base} />);
    expect(screen.getByText('Saalbach, Salzburg, Austria')).toBeInTheDocument();
    rerender(<FestivalHero festival={festival({ location: 'Saalbach, Salzburg' })} {...base} />);
    expect(screen.getByText('Saalbach, Salzburg · Austria')).toBeInTheDocument();
  });

  it('clamps a very long description', () => {
    render(<FestivalHero festival={festival({ description: 'a'.repeat(900) })} {...base} />);
    const text = screen.getByText(/^a+…$/);
    expect(text.textContent!.length).toBeLessThanOrEqual(401);
  });
});
