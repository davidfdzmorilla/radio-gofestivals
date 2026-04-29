'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2, Save } from 'lucide-react';
import {
  type StationDetail,
  getStationDetail,
  updateStation,
} from '@/lib/admin/stations';
import {
  type FlatGenre,
  flattenGenres,
  listAllGenres,
} from '@/lib/admin/genres';
import { GenreSelector } from '@/components/admin/GenreSelector';

type EditableStatus = 'active' | 'broken' | 'inactive';

interface FormState {
  curated: boolean;
  status: EditableStatus;
  name: string;
  slug: string;
  genre_ids: number[];
  notes: string;
}

const EDITABLE_STATUSES: EditableStatus[] = ['active', 'broken', 'inactive'];

function coerceStatus(raw: string): EditableStatus {
  return EDITABLE_STATUSES.includes(raw as EditableStatus)
    ? (raw as EditableStatus)
    : 'active';
}

export default function StationEditPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const stationId = params.id;

  const [station, setStation] = useState<StationDetail | null>(null);
  const [genres, setGenres] = useState<FlatGenre[]>([]);
  const [form, setForm] = useState<FormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!stationId) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    Promise.all([getStationDetail(stationId), listAllGenres()])
      .then(([detail, tree]) => {
        if (cancelled) return;
        setStation(detail);
        setGenres(flattenGenres(tree));
        setForm({
          curated: detail.curated,
          status: coerceStatus(detail.status),
          name: detail.name,
          slug: detail.slug,
          genre_ids: detail.genres.map((g) => g.genre_id),
          notes: '',
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof Error && err.message === 'not_found') {
          setLoadError('not_found');
        } else {
          setLoadError(
            err instanceof Error ? err.message : 'unknown_error',
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [stationId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form || saving) return;

    setSaving(true);
    setSubmitError(null);

    try {
      await updateStation(stationId, {
        curated: form.curated,
        status: form.status,
        name: form.name,
        slug: form.slug,
        genre_ids: form.genre_ids,
        notes: form.notes ? form.notes : undefined,
      });
      router.push(`/admin/stations/${stationId}?saved=1`);
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code === 'slug_conflict') {
        setSubmitError(
          `El slug "${form.slug}" ya está en uso por otra station.`,
        );
      } else if (code === 'not_found') {
        setSubmitError('Station no encontrada.');
      } else if (code === 'invalid_payload') {
        setSubmitError(
          'Algún campo no es válido (revisa slug, géneros, status).',
        );
      } else {
        setSubmitError(`Error al guardar: ${code}`);
      }
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="text-fg-2 flex items-center justify-center gap-2 py-12 font-mono text-xs uppercase tracking-widest">
        <Loader2 className="animate-spin" size={16} />
        Loading…
      </div>
    );
  }

  if (loadError === 'not_found') {
    return (
      <div className="space-y-4">
        <BackLink onClick={() => router.push('/admin/stations')} />
        <p className="text-warm font-mono text-sm">Station not found.</p>
      </div>
    );
  }

  if (loadError || !station || !form) {
    return (
      <div className="space-y-4">
        <BackLink onClick={() => router.push('/admin/stations')} />
        <p className="text-warm font-mono text-sm">
          Error: {loadError ?? 'unknown_error'}
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <BackLink
        onClick={() => router.push(`/admin/stations/${stationId}`)}
        label="Back to station"
      />

      <div>
        <h1 className="font-display text-fg-0 text-2xl font-bold">
          Edit station
        </h1>
        <p className="text-fg-2 mt-1 font-mono text-xs uppercase tracking-widest">
          {station.slug}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <fieldset className="space-y-2">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={form.curated}
              onChange={(e) =>
                setForm({ ...form, curated: e.target.checked })
              }
              disabled={saving}
              className="accent-magenta h-4 w-4"
            />
            <span className="text-fg-0 text-sm font-medium">Curated</span>
            <span className="text-fg-2 text-xs">(destacada en home)</span>
          </label>
        </fieldset>

        <Field label="Status" htmlFor="status">
          <select
            id="status"
            value={form.status}
            onChange={(e) =>
              setForm({ ...form, status: coerceStatus(e.target.value) })
            }
            disabled={saving}
            className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
          >
            <option value="active">Active</option>
            <option value="broken">Broken</option>
            <option value="inactive">Inactive</option>
          </select>
          <p className="text-fg-2 mt-1 text-xs">
            Pending y duplicate son estados del sistema, no editables.
          </p>
        </Field>

        <Field label="Name" htmlFor="name">
          <input
            id="name"
            type="text"
            required
            minLength={1}
            maxLength={200}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            disabled={saving}
            className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
          />
        </Field>

        <Field label="Slug" htmlFor="slug">
          <input
            id="slug"
            type="text"
            required
            pattern="^[a-z0-9][a-z0-9-]*$"
            minLength={2}
            maxLength={100}
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            disabled={saving}
            className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 font-mono text-sm focus:outline-none disabled:opacity-50"
          />
          <p className="text-fg-2 mt-1 text-xs">
            Solo lowercase, números y guiones. Debe ser único.
          </p>
        </Field>

        <Field label="Géneros">
          <GenreSelector
            genres={genres}
            selectedIds={form.genre_ids}
            onChange={(ids) => setForm({ ...form, genre_ids: ids })}
            disabled={saving}
          />
        </Field>

        <Field
          label="Notes"
          htmlFor="notes"
          hint="(para audit log)"
        >
          <input
            id="notes"
            type="text"
            maxLength={500}
            placeholder="Razón del cambio (opcional)"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            disabled={saving}
            className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
          />
        </Field>

        {submitError ? (
          <div
            role="alert"
            className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm"
          >
            {submitError}
          </div>
        ) : null}

        <div className="border-fg-3/40 flex items-center gap-3 border-t pt-4">
          <button
            type="submit"
            disabled={saving}
            className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex items-center gap-2 rounded-md px-4 py-2 font-display text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Save size={16} />
            )}
            {saving ? 'Guardando…' : 'Save changes'}
          </button>
          <button
            type="button"
            onClick={() => router.push(`/admin/stations/${stationId}`)}
            disabled={saving}
            className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 rounded-md border px-4 py-2 font-mono text-xs uppercase tracking-widest transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={htmlFor}
        className="text-fg-2 block font-mono text-[10px] uppercase tracking-widest"
      >
        {label}
        {hint ? <span className="text-fg-3 ml-1 normal-case">{hint}</span> : null}
      </label>
      {children}
    </div>
  );
}

function BackLink({
  onClick,
  label = 'Back',
}: {
  onClick: () => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-fg-2 hover:text-fg-0 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest"
    >
      <ArrowLeft size={14} />
      {label}
    </button>
  );
}
