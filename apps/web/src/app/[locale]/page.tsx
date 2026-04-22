import { getTranslations, setRequestLocale } from 'next-intl/server';
import { getGenresTree, listStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { GenreTree } from '@/components/genres/GenreTree';
import type { Genre } from '@/lib/types';

export const revalidate = 300;

function indexBySlug(genres: Genre[]): Record<string, Genre> {
  const out: Record<string, Genre> = {};
  const walk = (g: Genre) => {
    out[g.slug] = g;
    g.children.forEach(walk);
  };
  genres.forEach(walk);
  return out;
}

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const tHome = await getTranslations('home');
  const tGenres = await getTranslations('genres');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');

  const [genres, stationsPage] = await Promise.all([
    getGenresTree(),
    listStations({ curated: true, size: 12, revalidate: 300 }),
  ]);

  const genresBySlug = indexBySlug(genres);

  return (
    <div className="space-y-12">
      <section className="space-y-3">
        <h1 className="font-display text-5xl font-bold tracking-tight text-white">
          {tHome('title')}
        </h1>
        <p className="text-lg text-white/70">{tHome('tagline')}</p>
      </section>

      <section className="space-y-4">
        <h2 className="font-display text-2xl font-semibold text-white">
          {tGenres('title')}
        </h2>
        <GenreTree
          genres={genres}
          countLabel={(count) => tGenres('stationCount', { count })}
        />
      </section>

      <section className="space-y-4">
        <h2 className="font-display text-2xl font-semibold text-white">
          {tHome('featured')}
        </h2>
        <StationGrid
          stations={stationsPage.items}
          genresBySlug={genresBySlug}
          labels={{
            curated: tCommon('curated'),
            location: ({ city, country }) =>
              tStation('location', { city, country }),
            empty: tHome('featuredEmpty'),
          }}
        />
      </section>
    </div>
  );
}
