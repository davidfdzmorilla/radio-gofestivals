import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { storeToken } from '@/lib/admin/api';
import {
  createGenre,
  deleteGenre,
  updateGenre,
} from '@/lib/admin/genres';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function lastCall() {
  const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  return fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1]!;
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('createGenre', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('POSTs /admin/genres with JSON body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 9, slug: 'x', name: 'X' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const result = await createGenre({
      slug: 'x',
      name: 'X',
      parent_id: null,
      color_hex: '#fff',
      sort_order: 50,
      description: null,
    });
    expect(result.id).toBe(9);
    const [url, init] = lastCall();
    expect(String(url)).toBe(`${API_BASE}/api/v1/admin/genres`);
    expect((init as RequestInit).method).toBe('POST');
  });

  it('maps 409 to slug_conflict', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 409 }),
    );
    await expect(
      createGenre({ slug: 'taken', name: 'X' }),
    ).rejects.toThrow('slug_conflict');
  });

  it('maps 400 to invalid_payload', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 400 }),
    );
    await expect(createGenre({ slug: 'bad', name: '' })).rejects.toThrow(
      'invalid_payload',
    );
  });
});

describe('updateGenre', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('PUTs /admin/genres/{id}', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 9, slug: 'x', name: 'X' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await updateGenre(9, { name: 'Renamed' });
    const [url, init] = lastCall();
    expect(String(url)).toBe(`${API_BASE}/api/v1/admin/genres/9`);
    expect((init as RequestInit).method).toBe('PUT');
  });

  it('maps 409 to slug_conflict', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 409 }),
    );
    await expect(updateGenre(9, { slug: 'taken' })).rejects.toThrow(
      'slug_conflict',
    );
  });

  it('maps 404 to not_found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 404 }),
    );
    await expect(updateGenre(99, { name: 'x' })).rejects.toThrow(
      'not_found',
    );
  });
});

describe('deleteGenre', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('DELETEs /admin/genres/{id}', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    await deleteGenre(9);
    const [url, init] = lastCall();
    expect(String(url)).toBe(`${API_BASE}/api/v1/admin/genres/9`);
    expect((init as RequestInit).method).toBe('DELETE');
  });

  it('maps 409 to genre_in_use', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 409 }),
    );
    await expect(deleteGenre(1)).rejects.toThrow('genre_in_use');
  });

  it('maps 404 to not_found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 404 }),
    );
    await expect(deleteGenre(999)).rejects.toThrow('not_found');
  });
});
