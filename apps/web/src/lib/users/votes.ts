import { LikeResponseSchema, type LikeResponse } from './types';
import { userFetch } from './api';

export async function likeStation(
  stationId: string,
): Promise<LikeResponse> {
  const response = await userFetch(
    `/api/v1/stations/${stationId}/like`,
    { method: 'POST' },
  );
  if (!response.ok) {
    if (response.status === 401) throw new Error('unauthenticated');
    if (response.status === 404) throw new Error('station_not_found');
    if (response.status === 429) throw new Error('rate_limit_exceeded');
    throw new Error(`like_failed_${response.status}`);
  }
  return LikeResponseSchema.parse(await response.json());
}

export async function unlikeStation(
  stationId: string,
): Promise<LikeResponse> {
  const response = await userFetch(
    `/api/v1/stations/${stationId}/like`,
    { method: 'DELETE' },
  );
  if (!response.ok) {
    if (response.status === 401) throw new Error('unauthenticated');
    throw new Error(`unlike_failed_${response.status}`);
  }
  return LikeResponseSchema.parse(await response.json());
}
