import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user, loading, backendState } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
          {(backendState === "checking" || backendState === "waking") && (
            <p className="mt-3 text-sm text-muted-foreground">Waking server...</p>
          )}
        </div>
      </div>
    );
  }
  if (!user) {
    return <Navigate to={`/login?from=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return children;
}
