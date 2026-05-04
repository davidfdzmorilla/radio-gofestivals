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

export const GenreSchema: z.ZodType<Genre, z.ZodTypeDef, unknown> = z.lazy(() =>
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
  is_favorite: z.boolean().nullable().optional(),
  user_voted: z.boolean().nullable().optional(),
});
export type StationSummary = z.infer<typeof StationSummarySchema>;

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
