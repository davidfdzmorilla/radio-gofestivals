import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getGenresTree } from '@/lib/api';

export const revalidate = 300;

export default async function GenresIndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations('genres');

  let genres: Awaited<ReturnType<typeof getGenresTree>> = [];
  try {
    genres = await getGenresTree();
  } catch {
    genres = [];
  }
  const roots = genres.filter((g) => g.parent_id === null);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-fg-0 text-3xl font-semibold">
        {t('title')}
      </h1>
      <ul className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
        {roots.map((genre) => (
          <li key={genre.slug}>
            <Link
              href={`/genres/${genre.slug}`}
              className="border-fg-3/40 bg-bg-2/40 hover:bg-bg-3/40 hover:border-magenta block rounded-lg border p-4 transition-colors"
            >
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: genre.color_hex }}
              />
              <span className="text-fg-0 ml-2 font-medium">{genre.name}</span>
              <p className="text-fg-2 mt-1 font-mono text-[10px] uppercase tracking-widest">
                {t('stationCount', { count: genre.station_count })}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
