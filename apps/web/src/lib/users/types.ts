import { z } from 'zod';

export const UserSchema = z.object({
  id: z.string(),
  email: z.string(),
  username: z.string().nullable(),
  display_name: z.string().nullable(),
  bio: z.string().nullable(),
  avatar_url: z.string().nullable(),
  is_public: z.boolean(),
  created_at: z.string(),
});
export type User = z.infer<typeof UserSchema>;

export const AuthResponseSchema = z.object({
  user: UserSchema,
  access_token: z.string(),
  token_type: z.string().default('bearer'),
  expires_at: z.string(),
});
export type AuthResponse = z.infer<typeof AuthResponseSchema>;

export const FavoriteStreamRefSchema = z.object({
  id: z.string(),
  url: z.string(),
  codec: z.string().nullable(),
  bitrate: z.number().nullable(),
  format: z.string().nullable(),
});

export const FavoriteOutSchema = z.object({
  station_id: z.string(),
  slug: z.string(),
  name: z.string(),
  country_code: z.string().nullable(),
  city: z.string().nullable(),
  curated: z.boolean(),
  quality_score: z.number(),
  status: z.string(),
  primary_stream: FavoriteStreamRefSchema.nullable(),
  created_at: z.string(),
});
export type FavoriteOut = z.infer<typeof FavoriteOutSchema>;

export const FavoritesListResponseSchema = z.object({
  items: z.array(FavoriteOutSchema),
  total: z.number(),
});
export type FavoritesListResponse = z.infer<
  typeof FavoritesListResponseSchema
>;

export const MigrateFavoritesResponseSchema = z.object({
  added: z.number(),
  already_existed: z.number(),
  invalid: z.number(),
});
export type MigrateFavoritesResponse = z.infer<
  typeof MigrateFavoritesResponseSchema
>;

export const LikeResponseSchema = z.object({
  user_voted: z.boolean(),
  votes_local: z.number(),
});
export type LikeResponse = z.infer<typeof LikeResponseSchema>;
