import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { LoginResponse, User, UserMenu, UserPermissions } from "@/types";
import { AuthAPI } from "@/api/client";

interface AuthState {
  token: string | null;
  user: User | null;
  permissions: UserPermissions | null;
  menu: UserMenu | null;
  isLoading: boolean;
  error: string | null;

  login: (email: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  hasCapability: (cap: string) => boolean;
}

const persistKey = "latam.auth";

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      permissions: null,
      menu: null,
      isLoading: false,
      error: null,

      login: async (email: string) => {
        set({ isLoading: true, error: null });
        try {
          const data: LoginResponse = await AuthAPI.login(email);
          localStorage.setItem("latam.token", data.token);
          set({
            token: data.token,
            user: data.user,
            permissions: data.permissions,
            menu: data.menu,
            isLoading: false,
            error: null,
          });
        } catch (err: unknown) {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            "Falha no login.";
          set({ isLoading: false, error: msg });
          throw err;
        }
      },

      logout: () => {
        localStorage.removeItem("latam.token");
        set({ token: null, user: null, permissions: null, menu: null, error: null });
      },

      refresh: async () => {
        if (!get().token) return;
        try {
          const data = await AuthAPI.me();
          set({
            user: data.user,
            permissions: data.permissions,
            menu: data.menu,
          });
        } catch {
          get().logout();
        }
      },

      hasCapability: (cap: string) =>
        !!get().permissions?.capabilities?.includes(cap),
    }),
    {
      name: persistKey,
      partialize: (s) => ({
        token: s.token,
        user: s.user,
        permissions: s.permissions,
        menu: s.menu,
      }),
    },
  ),
);
