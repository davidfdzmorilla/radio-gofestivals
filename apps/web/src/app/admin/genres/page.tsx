'use client';

import { useEffect, useState } from 'react';
import { Loader2, Pencil, Plus } from 'lucide-react';
import {
  type GenreNode,
  deleteGenre,
  listAllGenres,
} from '@/lib/admin/genres';
import { DeleteButton } from '@/components/admin/DeleteButton';
import { GenreModal, type GenreModalMode } from '@/components/admin/GenreModal';

interface GenreRow extends GenreNode {
  depth: number;
}

function flattenGenresWithDepth(tree: GenreNode[]): GenreRow[] {
  const out: GenreRow[] = [];
  const visit = (nodes: GenreNode[], depth: number) => {
    const sorted = [...nodes].sort((a, b) => {
      const so = (a as { sort_order?: number }).sort_order ?? 100;
      const sb = (b as { sort_order?: number }).sort_order ?? 100;
      if (so !== sb) return so - sb;
      return a.name.localeCompare(b.name);
    });
    for (const node of sorted) {
      out.push({ ...node, depth });
      if (node.children && node.children.length > 0) {
        visit(node.children, depth + 1);
      }
    }
  };
  visit(tree, 0);
  return out;
}

export default function GenresPage() {
  const [genres, setGenres] = useState<GenreNode[]>([]);
  const [flat, setFlat] = useState<GenreRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [modalMode, setModalMode] = useState<GenreModalMode | null>(null);
  const [modalGenre, setModalGenre] = useState<GenreNode | null>(null);

  async function refresh() {
    setLoading(true);
    setLoadError(null);
    try {
      const tree = await listAllGenres();
      setGenres(tree);
      setFlat(flattenGenresWithDepth(tree));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'unknown_error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function showActionError(message: string) {
    setActionError(message);
    window.setTimeout(() => setActionError(null), 5000);
  }

  function handleCreate() {
    setModalGenre(null);
    setModalMode('create');
  }

  function handleEdit(g: GenreRow) {
    setModalGenre(g);
    setModalMode('edit');
  }

  async function handleDelete(g: GenreRow) {
    try {
      await deleteGenre(g.id);
      await refresh();
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code === 'genre_in_use') {
        showActionError(
          `No se puede borrar "${g.name}": tiene stations asociadas.`,
        );
      } else if (code === 'not_found') {
        showActionError(`"${g.name}" no encontrado.`);
        await refresh();
      } else {
        showActionError(`Error al borrar: ${code}`);
      }
    }
  }

  function closeModal() {
    setModalMode(null);
    setModalGenre(null);
  }

  async function handleModalSaved() {
    closeModal();
    await refresh();
  }

  const maxDepth = flat.reduce((m, r) => Math.max(m, r.depth), 0);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="font-display text-fg-0 text-2xl font-bold">Genres</h2>
          {!loading ? (
            <p className="text-fg-2 mt-1 font-mono text-xs uppercase tracking-widest">
              {flat.length} géneros · {maxDepth + 1}{' '}
              {maxDepth + 1 === 1 ? 'nivel' : 'niveles'}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={handleCreate}
          className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex items-center gap-2 rounded-md px-3 py-2 font-display text-sm font-medium transition-all"
        >
          <Plus size={16} />
          New genre
        </button>
      </div>

      {actionError ? (
        <div
          role="alert"
          className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm"
        >
          {actionError}
        </div>
      ) : null}

      <div className="border-fg-3/40 bg-bg-2/40 overflow-hidden rounded-lg border">
        {loading ? (
          <div className="text-fg-2 flex items-center justify-center gap-2 py-10 font-mono text-xs uppercase tracking-widest">
            <Loader2 className="animate-spin" size={16} />
            Loading…
          </div>
        ) : loadError ? (
          <p className="text-warm py-10 text-center text-sm">
            Error: {loadError}
          </p>
        ) : flat.length === 0 ? (
          <p className="text-fg-2 py-10 text-center text-sm">
            No genres. Click “New genre” to create one.
          </p>
        ) : (
          <ul className="divide-fg-3/30 divide-y">
            {flat.map((g) => (
              <li
                key={g.id}
                className="hover:bg-bg-3/40 flex items-center gap-3 px-4 py-2 transition-colors"
                style={{ paddingLeft: `${1 + g.depth * 1.5}rem` }}
              >
                <span
                  aria-hidden
                  className="border-fg-3/60 inline-block h-3 w-3 shrink-0 rounded-full border"
                  style={{ backgroundColor: g.color_hex }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="text-fg-0 font-medium">{g.name}</span>
                    <span className="text-fg-2 font-mono text-xs">
                      {g.slug}
                    </span>
                  </div>
                  {g.description ? (
                    <p className="text-fg-2 truncate text-xs">
                      {g.description}
                    </p>
                  ) : null}
                </div>
                <span className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
                  sort {(g as { sort_order?: number }).sort_order ?? 100}
                </span>
                <span className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
                  {g.station_count} stations
                </span>
                <button
                  type="button"
                  onClick={() => handleEdit(g)}
                  className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 inline-flex items-center gap-1 rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors"
                >
                  <Pencil size={12} />
                  Edit
                </button>
                <DeleteButton onDelete={() => handleDelete(g)} />
              </li>
            ))}
          </ul>
        )}
      </div>

      {modalMode ? (
        <GenreModal
          mode={modalMode}
          genre={modalGenre}
          parentOptions={genres}
          onClose={closeModal}
          onSaved={handleModalSaved}
        />
      ) : null}
    </div>
  );
}
