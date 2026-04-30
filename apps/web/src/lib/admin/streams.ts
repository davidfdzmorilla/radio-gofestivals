import { adminFetch } from './api';

export interface PromotePrimaryResponse {
  promoted_stream_id: string;
  demoted_stream_id: string | null;
  station_id: string;
}

export interface BulkStatusChangeResponse {
  affected: number;
  skipped: number;
  station_ids_affected: string[];
}

export async function promoteStreamToPrimary(
  streamId: string,
): Promise<PromotePrimaryResponse> {
  const response = await adminFetch(
    `/streams/${streamId}/promote-primary`,
    { method: 'PATCH' },
  );
  if (!response.ok) {
    if (response.status === 404) throw new Error('stream_not_found');
    if (response.status === 400) {
      const detail = (await response.json().catch(() => ({}))) as {
        detail?: string;
      };
      if (detail.detail === 'already_primary') {
        throw new Error('already_primary');
      }
    }
    throw new Error(`promote_failed_${response.status}`);
  }
  return (await response.json()) as PromotePrimaryResponse;
}

export async function bulkStatusChange(
  stationIds: string[],
  newStatus: 'inactive',
  reason?: string,
): Promise<BulkStatusChangeResponse> {
  const response = await adminFetch('/stations/bulk-status-change', {
    method: 'POST',
    body: JSON.stringify({
      station_ids: stationIds,
      new_status: newStatus,
      reason: reason ?? null,
    }),
  });
  if (!response.ok) {
    if (response.status === 422) {
      const detail = (await response.json().catch(() => ({}))) as unknown;
      throw new Error(`validation_failed:${JSON.stringify(detail)}`);
    }
    throw new Error(`bulk_failed_${response.status}`);
  }
  return (await response.json()) as BulkStatusChangeResponse;
}
