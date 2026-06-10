import { ImageResponse } from 'next/og';
import { getStation } from '@/lib/api';
import { initials } from '@/lib/utils';

export const revalidate = 3600;
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
export const alt = 'radio.gofestivals';

export default async function OpengraphImage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { slug } = await params;
  const station = await getStation(slug, revalidate).catch(() => null);
  const name = station?.name ?? 'radio.gofestivals';
  const color = station?.genres[0]?.color_hex ?? '#8b4ee8';
  const meta = station
    ? [
        station.genres[0]?.name,
        [station.city, station.country_code].filter(Boolean).join(', '),
      ]
        .filter(Boolean)
        .join(' · ')
    : '';

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 64,
          padding: '0 88px',
          backgroundColor: '#14130f',
          backgroundImage:
            'linear-gradient(135deg, #14130f 55%, #2a1640 100%)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 280,
            height: 280,
            borderRadius: 32,
            backgroundColor: color,
            color: '#0c0b09',
            fontSize: 120,
            fontWeight: 700,
            transform: 'rotate(-2deg)',
            boxShadow: '0 8px 0 0 #8b4ee8',
            flexShrink: 0,
          }}
        >
          {initials(name)}
        </div>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
            minWidth: 0,
          }}
        >
          <div
            style={{
              color: '#fafaf9',
              fontSize: name.length > 28 ? 56 : 72,
              fontWeight: 700,
              lineHeight: 1.05,
            }}
          >
            {name}
          </div>
          {meta ? (
            <div
              style={{
                color: '#8a877f',
                fontSize: 32,
                textTransform: 'uppercase',
                letterSpacing: 4,
              }}
            >
              {meta}
            </div>
          ) : null}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              marginTop: 22,
              color: '#1cc1f9',
              fontSize: 28,
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                borderRadius: 999,
                backgroundColor: '#e62de9',
              }}
            />
            radio.gofestivals.eu
          </div>
        </div>
      </div>
    ),
    size,
  );
}
