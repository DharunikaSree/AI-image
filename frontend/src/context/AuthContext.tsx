import React, { createContext, useContext, useEffect, useState } from "react";
import { api, apiErrorMessage } from "../services/api";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("current_user");
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    try {
      const res = await api.post("/auth/login", { email, password });
      localStorage.setItem("access_token", res.data.access_token);
      localStorage.setItem("current_user", JSON.stringify(res.data.user));
      setUser(res.data.user);
    } catch (e) {
      throw new Error(apiErrorMessage(e, "Incorrect email or password."));
    }
  }

  async function register(name: string, email: string, password: string) {
    try {
      const res = await api.post("/auth/register", { name, email, password });
      localStorage.setItem("access_token", res.data.access_token);
      localStorage.setItem("current_user", JSON.stringify(res.data.user));
      setUser(res.data.user);
    } catch (e) {
      throw new Error(apiErrorMessage(e, "Could not create your account."));
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
