import { z } from 'zod';

export interface Genre {
  id: number;
  slug: string;
  name: string;
  color_hex: string;
  parent_id: number | null;
  station_count: number;
  children: Genre[];
}

export const GenreSchema: z.ZodType<Genre, unknown> = z.lazy(() =>
  z
    .object({
      id: z.number(),
      slug: z.string(),
      name: z.string(),
      color_hex: z.string(),
      parent_id: z.number().nullable(),
      station_count: z.number(),
      children: z.array(GenreSchema).optional(),
    })
    .transform(
      (g): Genre => ({
        id: g.id,
        slug: g.slug,
        name: g.name,
        color_hex: g.color_hex,
        parent_id: g.parent_id,
        station_count: g.station_count,
        children: g.children ?? [],
      }),
    ),
);

export const StationStreamRefSchema = z.object({
  id: z.string(),
  url: z.string(),
  codec: z.string().nullable(),
  bitrate: z.number().nullable(),
  format: z.string().nullable(),
  is_primary: z.boolean(),
  status: z.string().default('active'),
  cors_ok: z.boolean().nullable().optional(),
});
export type StationStreamRef = z.infer<typeof StationStreamRefSchema>;

export const StationSummarySchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  country_code: z.string().nullable(),
  city: z.string().nullable(),
  curated: z.boolean(),
  quality_score: z.number(),
  votes_local: z.number().default(0),
  genres: z.array(z.string()),
  primary_stream: StationStreamRefSchema.nullable().optional(),
  // Hash del logo procesado (ADR 011); null = sin logo propio.
  logo_hash: z.string().nullable().optional(),
  is_favorite: z.boolean().nullable().optional(),
  user_voted: z.boolean().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});
export type StationSummary = z.infer<typeof StationSummarySchema>;

export const StationSuggestionSchema = z.object({
  slug: z.string(),
  name: z.string(),
  country_code: z.string().nullable(),
  genres: z.array(z.string()).default([]),
});
export type StationSuggestion = z.infer<typeof StationSuggestionSchema>;

export const CountryFacetSchema = z.object({
  code: z.string(),
  station_count: z.number(),
});
export type CountryFacet = z.infer<typeof CountryFacetSchema>;

export const GenreFacetSchema = z.object({
  slug: z.string(),
  name: z.string(),
  color_hex: z.string(),
  station_count: z.number(),
});
export type GenreFacet = z.infer<typeof GenreFacetSchema>;

export const StationsPageSchema = z.object({
  items: z.array(StationSummarySchema),
  total: z.number(),
  page: z.number(),
  size: z.number(),
  pages: z.number(),
});
export type StationsPage = z.infer<typeof StationsPageSchema>;

export const StationGenreRefSchema = z.object({
  slug: z.string(),
  name: z.string(),
  color_hex: z.string(),
});

export const NowPlayingEntrySchema = z.object({
  title: z.string().nullable(),
  artist: z.string().nullable(),
  captured_at: z.string(),
});
export type NowPlayingEntry = z.infer<typeof NowPlayingEntrySchema>;

export const StationDetailSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  homepage_url: z.string().nullable(),
  country_code: z.string().nullable(),
  city: z.string().nullable(),
  language: z.string().nullable(),
  curated: z.boolean(),
  quality_score: z.number(),
  status: z.string(),
  votes_local: z.number().default(0),
  logo_hash: z.string().nullable().optional(),
  genres: z.array(StationGenreRefSchema),
  streams: z.array(StationStreamRefSchema).default([]),
  now_playing: z.array(NowPlayingEntrySchema),
  is_favorite: z.boolean().nullable().optional(),
  user_voted: z.boolean().nullable().optional(),
});
export type StationDetail = z.infer<typeof StationDetailSchema>;

export interface NowPlayingState {
  title: string | null;
  artist: string | null;
  at: string;
}

// Festivales de gofestivals (proyecto hermano, ADR 009). La API usa snake_case
// y mezcla nombres; aquí se normaliza al forma que usa la web.
export const FestivalSchema = z
  .object({
    id: z.union([z.number(), z.string()]).transform(String),
    name: z.string().min(1),
    start_date: z.string(),
    end_date: z.string().nullish(),
    location: z.string().nullish(),
    location_en: z.string().nullish(),
    country_code: z.string().nullish(),
    website: z.string().nullish(),
    imageUrl: z.string().nullish(),
    description: z.string().nullish(),
    description_en: z.string().nullish(),
    Genres: z.array(z.object({ name: z.string() })).nullish(),
  })
  .transform((f) => ({
    id: f.id,
    name: f.name,
    startDate: f.start_date,
    endDate: f.end_date ?? null,
    location: f.location ?? null,
    locationEn: f.location_en ?? null,
    countryCode: f.country_code ? f.country_code.toUpperCase() : null,
    website: f.website ?? null,
    imageUrl: f.imageUrl ?? null,
    description: f.description ?? null,
    descriptionEn: f.description_en ?? null,
    genres: (f.Genres ?? []).map((g) => g.name),
  }));
export type Festival = z.infer<typeof FestivalSchema>;
