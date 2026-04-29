import { adminFetch } from './api';

export type JobStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'failed'
  | 'timeout';

export interface ParamsSchema {
  title?: string;
  description?: string;
  properties?: Record<string, unknown>;
  required?: string[];
  [key: string]: unknown;
}

export interface CommandCatalogEntry {
  command: string;
  label: string;
  description: string;
  timeout: number;
  params_schema: ParamsSchema;
}

export interface AdminJob {
  id: number;
  command: string;
  params_json: Record<string, unknown> | null;
  status: JobStatus;
  result_json: Record<string, unknown> | null;
  stderr_tail: string | null;
  started_at: string | null;
  finished_at: string | null;
  admin_id: string;
  admin_email: string | null;
  created_at: string;
}

export interface JobsPage {
  items: AdminJob[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export async function getCatalog(): Promise<CommandCatalogEntry[]> {
  const response = await adminFetch('/operations/catalog');
  if (!response.ok) {
    throw new Error(`catalog_failed_${response.status}`);
  }
  return (await response.json()) as CommandCatalogEntry[];
}

export async function runCommand(
  command: string,
  params?: Record<string, unknown> | null,
): Promise<AdminJob> {
  const response = await adminFetch('/operations/run', {
    method: 'POST',
    body: JSON.stringify({ command, params: params ?? null }),
  });
  if (!response.ok) {
    if (response.status === 400) throw new Error('command_not_allowed');
    if (response.status === 422) {
      const detail = (await response.json().catch(() => ({}))) as unknown;
      throw new Error(`invalid_params:${JSON.stringify(detail)}`);
    }
    throw new Error(`run_failed_${response.status}`);
  }
  return (await response.json()) as AdminJob;
}

export interface ListJobsParams {
  page?: number;
  size?: number;
  status?: JobStatus | '';
}

export async function listJobs(
  params: ListJobsParams = {},
): Promise<JobsPage> {
  const search = new URLSearchParams();
  if (params.page !== undefined) search.set('page', String(params.page));
  if (params.size !== undefined) search.set('size', String(params.size));
  if (params.status) search.set('status', params.status);
  const qs = search.toString();
  const path = qs ? `/operations/jobs?${qs}` : '/operations/jobs';
  const response = await adminFetch(path);
  if (!response.ok) {
    throw new Error(`list_jobs_failed_${response.status}`);
  }
  return (await response.json()) as JobsPage;
}

export async function getJob(id: number): Promise<AdminJob> {
  const response = await adminFetch(`/operations/jobs/${id}`);
  if (!response.ok) {
    if (response.status === 404) throw new Error('not_found');
    throw new Error(`get_job_failed_${response.status}`);
  }
  return (await response.json()) as AdminJob;
}
