import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

/**
 * Smart /dashboard redirect — routes the user to the dashboard
 * that matches their role. Keeps backwards compatibility for older
 * links pointing to /dashboard.
 */
export default function DashboardRedirect() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login?from=/dashboard" replace />;
  if (user.role === "admin") return <Navigate to="/admin" replace />;
  if (user.role === "influencer") return <Navigate to="/influencer" replace />;
  if (user.role === "brand") return <Navigate to="/brand" replace />;
  return <Navigate to="/" replace />;
}
