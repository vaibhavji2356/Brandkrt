import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";

const AuthContext = createContext(null);
const TOKEN_KEY = "brandkrt_access_token";

function saveAccessToken(token) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);     // user object | null
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.user);
    } catch (e) {
      try {
        const { data } = await api.post("/auth/refresh");
        saveAccessToken(data.access_token);
        setUser(data.user);
      } catch (refreshErr) {
        saveAccessToken(null);
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = async (email, password, remember_me = false) => {
    const { data } = await api.post("/auth/login", { email, password, remember_me });
    saveAccessToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const googleSignIn = async (credential) => {
    const { data } = await api.post("/auth/google", { credential });
    saveAccessToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    saveAccessToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) {}
    saveAccessToken(null);
    setUser(null);
  };

  const forgotPassword = async (email) => {
    const { data } = await api.post("/auth/forgot-password", { email });
    return data;
  };

  const resetPassword = async (token, new_password) => {
    const { data } = await api.post("/auth/reset-password", { token, new_password });
    return data;
  };

  const verifyEmail = async (token) => {
    const { data } = await api.post("/auth/verify-email", { token });
    await refresh();
    return data;
  };

  return (
    <AuthContext.Provider value={{
      user, loading, refresh, login, register, logout, googleSignIn,
      forgotPassword, resetPassword, verifyEmail, formatApiError,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
