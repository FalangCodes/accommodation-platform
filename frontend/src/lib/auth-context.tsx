"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { authApi } from "./api";
import { SESSION_ENDED_EVENT } from "./session";
import { useQueryClient } from "@tanstack/react-query";

export interface User {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  clearSession: () => void;
  isStudent: boolean;
  isLandlord: boolean;
  isModerator: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const clear = () => {
      setUser(null);
      queryClient.clear();
    };
    const onStorage = (event: StorageEvent) => {
      if ((event.key === "access_token" || event.key === null) && !localStorage.getItem("access_token")) clear();
    };
    window.addEventListener(SESSION_ENDED_EVENT, clear);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SESSION_ENDED_EVENT, clear);
      window.removeEventListener("storage", onStorage);
    };
  }, [queryClient]);

  const userId = user?.id;
  useEffect(() => {
    if (!userId) return;
    const check = () => {
      if (document.visibilityState === "visible" && localStorage.getItem("access_token")) {
        void authApi.me().catch(() => {});
      }
    };
    const timer = window.setInterval(check, 60_000);
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", check);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", check);
      document.removeEventListener("visibilitychange", check);
    };
  }, [userId]);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const request = token ? authApi.me() : Promise.resolve(null);
    request
        .then((res) => {
          if (res && localStorage.getItem("access_token")) setUser(res.data);
        })
        .catch(() => {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        })
        .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    localStorage.setItem("access_token", res.data.access_token);
    localStorage.setItem("refresh_token", res.data.refresh_token);
    const me = await authApi.me();
    if (localStorage.getItem("access_token")) setUser(me.data);
    return me.data as User;
  };

  const clearSession = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
    queryClient.clear();
  };

  const logout = () => {
    clearSession();
    window.location.href = "/";
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      logout,
      clearSession,
      isStudent: user?.role === "student",
      isLandlord: user?.role === "landlord",
      isModerator: user?.role === "moderator" || user?.role === "admin",
      isAdmin: user?.role === "admin",
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
