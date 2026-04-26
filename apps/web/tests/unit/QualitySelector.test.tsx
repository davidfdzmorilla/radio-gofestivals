import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { QualitySelector } from '@/components/player/QualitySelector';
import type { StationStreamRef } from '@/lib/types';

const messages = { player: { quality: 'Quality' } };

function renderWith(streams: StationStreamRef[], activeId: string, onSelect = vi.fn()) {
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QualitySelector streams={streams} activeStreamId={activeId} onSelect={onSelect} />
    </NextIntlClientProvider>,
  );
  return onSelect;
}

const mk = (id: string, bitrate: number | null, codec = 'mp3'): StationStreamRef => ({
  id,
  url: `https://x/${id}`,
  codec,
  bitrate,
  format: codec,
  is_primary: false,
});

describe('QualitySelector', () => {
  it('renders one pill per stream when there are multiple', () => {
    renderWith([mk('a', 320), mk('b', 128, 'aac+')], 'a');
    expect(screen.getByRole('button', { name: '320 mp3' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '128 aac+' })).toBeInTheDocument();
  });

  it('renders nothing when only one stream', () => {
    const { container } = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <QualitySelector
          streams={[mk('a', 128)]}
          activeStreamId="a"
          onSelect={() => {}}
        />
      </NextIntlClientProvider>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('marks the active pill with aria-pressed=true', () => {
    renderWith([mk('a', 320), mk('b', 128)], 'b');
    expect(screen.getByRole('button', { name: '320 mp3' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    expect(screen.getByRole('button', { name: '128 mp3' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('calls onSelect with the clicked stream', () => {
    const onSelect = renderWith([mk('a', 320), mk('b', 128)], 'a');
    fireEvent.click(screen.getByRole('button', { name: '128 mp3' }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0]![0].id).toBe('b');
  });

  it('formats missing bitrate as "—"', () => {
    renderWith([mk('a', null, 'opus'), mk('b', 128)], 'b');
    expect(screen.getByRole('button', { name: '— opus' })).toBeInTheDocument();
  });
});
