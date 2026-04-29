'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { Loader2, X } from 'lucide-react';
import {
  type GenreNode,
  type GenreOut,
  createGenre,
  updateGenre,
} from '@/lib/admin/genres';
import { cn } from '@/lib/utils';

export type GenreModalMode = 'create' | 'edit';

interface GenreModalProps {
  mode: GenreModalMode;
  genre?: GenreNode | null;
  parentOptions: GenreNode[];
  onClose: () => void;
  onSaved: (saved: GenreOut) => void;
}

const DEFAULT_COLOR = '#8B4EE8';

export function GenreModal({
  mode,
  genre,
  parentOptions,
  onClose,
  onSaved,
}: GenreModalProps) {
  const [name, setName] = useState(genre?.name ?? '');
  const [slug, setSlug] = useState(genre?.slug ?? '');
  const [parentId, setParentId] = useState<number | null>(
    genre?.parent_id ?? null,
  );
  const [colorHex, setColorHex] = useState(genre?.color_hex ?? DEFAULT_COLOR);
  const [sortOrder, setSortOrder] = useState<number>(
    typeof genre?.sort_order === 'number' ? genre.sort_order : 100,
  );
  const [description, setDescription] = useState(genre?.description ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !saving) onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, saving]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;

    setSaving(true);
    setError(null);

    const payload = {
      slug,
      name,
      parent_id: parentId,
      color_hex: colorHex,
      sort_order: sortOrder,
      description: description ? description : null,
    };

    try {
      const saved =
        mode === 'create'
          ? await createGenre(payload)
          : await updateGenre(genre!.id, payload);
      onSaved(saved);
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code === 'slug_conflict') {
        setError(`El slug "${slug}" ya está en uso por otro género.`);
      } else if (code === 'not_found') {
        setError('Género no encontrado (puede haber sido borrado).');
      } else if (code === 'invalid_payload') {
        setError('Algún campo no es válido (revisa slug, color, sort).');
      } else {
        setError(`Error: ${code}`);
      }
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-0/80 p-4 backdrop-blur"
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
    >
      <div className="border-fg-3/40 bg-bg-2 max-h-[90vh] w-full max-w-md overflow-y-auto rounded-lg border shadow-sticker-lg">
        <div className="border-fg-3/40 flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-display text-fg-0 text-lg font-semibold">
            {mode === 'create' ? 'Create genre' : `Edit ${genre?.name ?? ''}`}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close"
            className="text-fg-2 hover:text-fg-0 disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-4">
          <Field label="Name" htmlFor="g-name">
            <input
              id="g-name"
              type="text"
              required
              minLength={1}
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={saving}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
            />
          </Field>

          <Field label="Slug" htmlFor="g-slug">
            <input
              id="g-slug"
              type="text"
              required
              pattern="^[a-z0-9][a-z0-9-]*$"
              minLength={2}
              maxLength={60}
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={saving}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 font-mono text-sm focus:outline-none disabled:opacity-50"
            />
          </Field>

          <Field label="Parent" htmlFor="g-parent">
            <select
              id="g-parent"
              value={parentId === null ? '' : String(parentId)}
              onChange={(e) =>
                setParentId(e.target.value ? Number(e.target.value) : null)
              }
              disabled={saving}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
            >
              <option value="">— No parent (root) —</option>
              {parentOptions
                .filter((p) => p.id !== genre?.id)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Color" htmlFor="g-color">
              <input
                id="g-color"
                type="color"
                value={colorHex}
                onChange={(e) => setColorHex(e.target.value)}
                disabled={saving}
                className="border-fg-3 bg-bg-1 h-10 w-full cursor-pointer rounded-md border disabled:opacity-50"
              />
            </Field>
            <Field label="Sort order" htmlFor="g-sort">
              <input
                id="g-sort"
                type="number"
                min={0}
                max={10000}
                value={sortOrder}
                onChange={(e) => setSortOrder(Number(e.target.value))}
                disabled={saving}
                className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
              />
            </Field>
          </div>

          <Field label="Description" htmlFor="g-desc" hint="(opcional)">
            <textarea
              id="g-desc"
              maxLength={500}
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={saving}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
            />
          </Field>

          {error ? (
            <div
              role="alert"
              className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm"
            >
              {error}
            </div>
          ) : null}

          <div className="border-fg-3/40 flex items-center justify-end gap-2 border-t pt-3">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className={cn(
                'bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex items-center gap-2 rounded-md px-3 py-1.5 font-display text-sm font-medium transition-all',
                'disabled:cursor-not-allowed disabled:opacity-50',
              )}
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : null}
              {saving
                ? 'Saving…'
                : mode === 'create'
                  ? 'Create'
                  : 'Save'}
            </button>
          </div>
        </form>
      </div>
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
        {hint ? (
          <span className="text-fg-3 ml-1 normal-case">{hint}</span>
        ) : null}
      </label>
      {children}
    </div>
  );
}
