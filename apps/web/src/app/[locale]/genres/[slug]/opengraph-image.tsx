import { ImageResponse } from 'next/og';
import { getTranslations } from 'next-intl/server';
import { getGenresTree } from '@/lib/api';
import type { Genre } from '@/lib/types';

export const revalidate = 3600;
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
export const alt = 'radio.gofestivals';

function findGenre(genres: Genre[], slug: string): Genre | null {
  for (const g of genres) {
    if (g.slug === slug) return g;
    const child = findGenre(g.children, slug);
    if (child) return child;
  }
  return null;
}

export default async function OpengraphImage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const tGenres = await getTranslations({ locale, namespace: 'genres' });
  const genre = await getGenresTree(revalidate)
    .then((tree) => findGenre(tree, slug))
    .catch(() => null);
  const name = genre?.name ?? 'radio.gofestivals';
  const color = genre?.color_hex ?? '#8b4ee8';

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: 24,
          padding: '0 96px',
          backgroundColor: '#14130f',
          backgroundImage:
            'linear-gradient(135deg, #14130f 55%, #2a1640 100%)',
        }}
      >
        <div
          style={{
            width: 120,
            height: 16,
            borderRadius: 999,
            backgroundColor: color,
          }}
        />
        <div
          style={{
            color: '#fafaf9',
            fontSize: 96,
            fontWeight: 700,
            lineHeight: 1.05,
          }}
        >
          {name}
        </div>
        {genre ? (
          <div
            style={{
              color: '#8a877f',
              fontSize: 34,
              textTransform: 'uppercase',
              letterSpacing: 4,
            }}
          >
            {tGenres('stationCount', { count: genre.station_count })}
          </div>
        ) : null}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            marginTop: 28,
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
    ),
    size,
  );
}
