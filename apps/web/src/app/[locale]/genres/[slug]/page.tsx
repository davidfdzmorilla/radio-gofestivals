import { notFound } from 'next/navigation';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { getGenresTree, listStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { SidebarFilters } from '@/components/layout/SidebarFilters';
import type { Genre } from '@/lib/types';

export const revalidate = 300;

export async function generateStaticParams() {
  try {
    const genres = await getGenresTree();
    return genres
      .filter((g) => g.parent_id === null)
      .map((g) => ({ slug: g.slug }));
  } catch {
    // API no disponible en build → renderizado on-demand
    return [];
  }
}

function indexBySlug(genres: Genre[]): Record<string, Genre> {
  const out: Record<string, Genre> = {};
  const walk = (g: Genre) => {
    out[g.slug] = g;
    g.children.forEach(walk);
  };
  genres.forEach(walk);
  return out;
}

export default async function GenrePage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale, slug } = await params;
  const sp = await searchParams;
  setRequestLocale(locale);

  const genres = await getGenresTree();
  const genresBySlug = indexBySlug(genres);
  const genre = genresBySlug[slug];
  if (!genre) notFound();

  const country = typeof sp.country === 'string' ? sp.country : undefined;
  const curatedParam = typeof sp.curated === 'string' ? sp.curated : undefined;
  const page = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;

  const tGenres = await getTranslations('genres');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');
  const tHome = await getTranslations('home');

  const stationsPage = await listStations({
    genre: genre.slug,
    country,
    curated: curatedParam === 'true' ? true : undefined,
    page: Number.isFinite(page) && page > 0 ? page : 1,
    size: 20,
    revalidate: 300,
  });

  const countries = ['ES', 'FR', 'DE', 'IT', 'UK', 'US', 'NL', 'BE'];

  return (
    <div className="space-y-6">
      <header
        className="rounded-xl border border-white/10 p-6"
        style={{
          background: `linear-gradient(135deg, ${genre.color_hex}40, transparent)`,
        }}
      >
        <p className="text-xs uppercase tracking-wider text-white/60">
          {tGenres('title')}
        </p>
        <h1 className="mt-1 font-display text-4xl font-bold text-white">
          {tGenres('exploreTitle', { name: genre.name })}
        </h1>
        <p className="mt-2 text-sm text-white/60">
          {tGenres('stationCount', { count: stationsPage.total })}
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[220px_1fr]">
        <SidebarFilters
          current={{ country, curated: curatedParam === 'true' }}
          countries={countries}
        />
        <StationGrid
          stations={stationsPage.items}
          genresBySlug={genresBySlug}
          labels={{
            curated: tCommon('curated'),
            location: ({ city, country: c }) =>
              tStation('location', { city, country: c }),
            empty: tHome('featuredEmpty'),
          }}
        />
      </div>
    </div>
  );
}
