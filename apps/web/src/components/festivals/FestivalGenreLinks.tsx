import { Badge } from '@/components/ui/badge';
import { Link } from '@/i18n/navigation';
import { readableOnDark } from '@/lib/color';
import type { Genre } from '@/lib/types';

interface Props {
  title: string;
  genres: Genre[];
}

/** Géneros de la radio a los que pertenece el festival; cada uno enlaza a su hub. */
export function FestivalGenreLinks({ title, genres }: Props) {
  if (genres.length === 0) return null;
  return (
    <section className="space-y-3" aria-labelledby="festival-genres-title">
      <h2 id="festival-genres-title" className="font-display text-xl font-semibold text-fg-0">
        {title}
      </h2>
      <ul className="flex flex-wrap gap-2">
        {genres.map((g) => (
          <li key={g.slug}>
            <Link href={`/genres/${g.slug}`} className="inline-flex min-h-8 items-center">
              <Badge
                className="border-fg-3 bg-bg-3 px-3 py-1 transition-colors hover:border-fg-2"
                style={{ color: readableOnDark(g.color_hex) }}
              >
                {g.name}
              </Badge>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
