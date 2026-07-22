import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "@/lib/api";
import { resetBackendReadiness, waitForBackendReady } from "@/lib/backendStatus";

const AuthContext = createContext(null);
const TOKEN_KEY = "brandkrt_access_token";

function clearLegacyAccessToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

function isAuthDenied(error) {
  const status = error?.response?.status;
  return status === 401 || status === 403;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);     // user object | null
  const [loading, setLoading] = useState(true);
  const [backendState, setBackendState] = useState("checking");

  const refresh = useCallback(async () => {
    try {
      await waitForBackendReady({ onState: ({ state }) => setBackendState(state) });
    } catch (_) {
      setBackendState("unavailable");
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.user);
    } catch (e) {
      try {
        const { data } = await api.post("/auth/refresh");
        setUser(data.user);
      } catch (refreshErr) {
        if (isAuthDenied(e) || isAuthDenied(refreshErr)) {
          clearLegacyAccessToken();
        }
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    clearLegacyAccessToken();
    refresh();
  }, [refresh]);

  const login = async (email, password, remember_me = false) => {
    try {
      await waitForBackendReady({ onState: ({ state }) => setBackendState(state) });
      const { data } = await api.post("/auth/login", { email, password, remember_me });
      setUser(data.user);
      return data.user;
    } catch (error) {
      if (!error?.response || [408, 425, 429, 500, 502, 503, 504].includes(error.response.status)) {
        resetBackendReadiness();
        setBackendState("unavailable");
      }
      throw error;
    }
  };

  const googleSignIn = async (credential) => {
    await waitForBackendReady({ onState: ({ state }) => setBackendState(state) });
    const { data } = await api.post("/auth/google", { credential });
    setUser(data.user);
    return data.user;
  };

  const register = async (payload) => {
    await waitForBackendReady({ onState: ({ state }) => setBackendState(state) });
    const { data } = await api.post("/auth/register", payload);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) {}
    clearLegacyAccessToken();
    setUser(null);
  };

  const forgotPassword = async (email) => {
    await waitForBackendReady({ onState: ({ state }) => setBackendState(state) });
    const { data } = await api.post("/auth/forgot-password", { email });
    return data;
  };

  const resetPassword = async (token, new_password) => {
    await waitForBackendReady({ onState: ({ state }) => setBackendState(state) });
    const { data } = await api.post("/auth/reset-password", { token, new_password });
    return data;
  };

  const verifyEmail = async (token) => {
    await waitForBackendReady({ onState: ({ state }) => setBackendState(state) });
    const { data } = await api.post("/auth/verify-email", { token });
    await refresh();
    return data;
  };

  return (
    <AuthContext.Provider value={{
      user, loading, backendState, refresh, login, register, logout, googleSignIn,
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
