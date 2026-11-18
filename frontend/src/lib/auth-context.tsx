"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "./api";
import { useUserEvents } from "./use-user-events";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function loadUser() {
      const stored = localStorage.getItem("pulsesearch_token");
      if (!stored) {
        setLoading(false);
        return;
      }
      try {
        setUser(await api.me());
      } catch {
        setToken(null);
      } finally {
        setLoading(false);
      }
    }
    void loadUser();
  }, []);

  useUserEvents(user?.id ?? null);

  async function login(email: string, password: string) {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    const me = await api.me();
    setUser(me);
    router.push("/dashboard");
  }

  async function register(email: string, password: string, fullName?: string) {
    const { access_token } = await api.register(email, password, fullName);
    setToken(access_token);
    const me = await api.me();
    setUser(me);
    router.push("/dashboard");
  }

  function logout() {
    setToken(null);
    setUser(null);
    router.push("/login");
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
