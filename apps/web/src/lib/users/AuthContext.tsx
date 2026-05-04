'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from './api';
import { getMe } from './auth';
import {
  BackendFavorites,
  type FavoritesProvider,
  LocalStorageFavorites,
} from './favorites';
import type { User } from './types';

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  favoriteIds: Set<string>;
  /** Save the JWT, fetch the user, refresh favorites, migrate anonymous list. */
  login: (token: string, user: User) => Promise<{ migrated: number }>;
  /** Drop JWT and reset to anonymous mode. */
  logout: () => void;
  /** Re-fetch favorites from the active provider and update the in-memory set. */
  refreshFavorites: () => Promise<void>;
  /** Optimistically toggle the local set without hitting the network. */
  setFavoriteFlag: (stationId: string, value: boolean) => void;
  /** Active provider (Backend if logged, LocalStorage otherwise). */
  favoritesProvider: FavoritesProvider;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());

  // Two stable provider instances; we pick one based on `user`.
  const localProvider = useMemo(() => new LocalStorageFavorites(), []);
  const backendProvider = useMemo(() => new BackendFavorites(), []);
  const provider: FavoritesProvider = user ? backendProvider : localProvider;

  // Initial bootstrap: hydrate user + favorites depending on token presence.
  useEffect(() => {
    let cancelled = false;
    const token = getStoredToken();
    if (!token) {
      if (!cancelled) {
        setFavoriteIds(new Set(localProvider.ids()));
        setIsLoading(false);
      }
      return () => {
        cancelled = true;
      };
    }

    (async () => {
      try {
        const me = await getMe();
        if (cancelled) return;
        setUser(me);
        await backendProvider.hydrate();
        if (!cancelled) {
          setFavoriteIds(new Set(backendProvider.ids()));
        }
      } catch {
        clearStoredToken();
        if (!cancelled) {
          setFavoriteIds(new Set(localProvider.ids()));
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [localProvider, backendProvider]);

  const refreshFavorites = useCallback(async () => {
    const active = user ? backendProvider : localProvider;
    if (active === backendProvider) {
      await backendProvider.hydrate();
    }
    setFavoriteIds(new Set(active.ids()));
  }, [user, backendProvider, localProvider]);

  const login = useCallback(
    async (token: string, loggedUser: User) => {
      setStoredToken(token);
      setUser(loggedUser);

      // Migrate any local favorites the user collected as anonymous.
      const localIds = localProvider.ids();
      let migrated = 0;
      if (localIds.length > 0) {
        try {
          const result = await backendProvider.migrate(localIds);
          migrated = result.added;
        } catch {
          // Non-fatal: keep the local cache as-is so the user can retry.
        }
        LocalStorageFavorites.clear();
      }

      await backendProvider.hydrate();
      setFavoriteIds(new Set(backendProvider.ids()));
      return { migrated };
    },
    [localProvider, backendProvider],
  );

  const logout = useCallback(() => {
    clearStoredToken();
    setUser(null);
    // After logout we're anonymous; the local cache may be empty.
    setFavoriteIds(new Set(localProvider.ids()));
  }, [localProvider]);

  const setFavoriteFlag = useCallback(
    (stationId: string, value: boolean) => {
      setFavoriteIds((prev) => {
        const next = new Set(prev);
        if (value) next.add(stationId);
        else next.delete(stationId);
        return next;
      });
    },
    [],
  );

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: user !== null,
    favoriteIds,
    login,
    logout,
    refreshFavorites,
    setFavoriteFlag,
    favoritesProvider: provider,
  };

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used within <AuthProvider>');
  }
  return ctx;
}
