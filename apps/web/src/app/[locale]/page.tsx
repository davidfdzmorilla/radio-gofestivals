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
    <div className="space-y-16">
      {/* Hero */}
      <section className="space-y-5">
        <span className="inline-flex -rotate-1 items-center gap-2 rounded-full border border-magenta/40 bg-magenta-soft px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-fg-0 shadow-sticker-magenta">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-magenta" />
          {tCommon('curated')} · 2026
        </span>
        <h1 className="font-display text-[clamp(2.75rem,7vw,5rem)] font-semibold leading-[1.02] tracking-tight text-fg-0">
          {tHome('title')}
        </h1>
        <p className="max-w-xl font-display text-xl font-medium text-fg-1">
          {tHome('tagline')}
        </p>
      </section>

      {/* Géneros */}
      <section className="space-y-5">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-3xl font-semibold text-fg-0">
            {tGenres('title')}
          </h2>
          <span className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
            {genres.filter((g) => g.parent_id === null).length} / 9
          </span>
        </div>
        <GenreTree
          genres={genres}
          countLabel={(count) => tGenres('stationCount', { count })}
        />
      </section>

      {/* Destacadas */}
      <section className="space-y-5">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-3xl font-semibold text-fg-0">
            <span className="mr-2 inline-block rotate-1 rounded-lg bg-wave px-2 py-0.5 text-bg-0 shadow-sticker-sm">
              {tHome('featured')}
            </span>
          </h2>
          <span className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
            {stationsPage.total} total
          </span>
        </div>
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
