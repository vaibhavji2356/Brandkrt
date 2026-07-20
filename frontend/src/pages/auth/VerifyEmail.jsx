import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AuthLayout from "./AuthLayout";
import { useAuth } from "@/context/AuthContext";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

export default function VerifyEmail() {
  const { verifyEmail, formatApiError } = useAuth();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState({ status: "loading", message: "" });

  useEffect(() => {
    let alive = true;
    if (!token) { setState({ status: "error", message: "Missing verification token." }); return; }
    (async () => {
      try {
        const data = await verifyEmail(token);
        if (alive) setState({ status: "success", message: data.message || "Email verified." });
      } catch (err) {
        if (alive) setState({ status: "error", message: formatApiError(err) });
      }
    })();
    return () => { alive = false; };
  }, [token, verifyEmail, formatApiError]);

  return (
    <AuthLayout tagline="Email verification">
      <div className="text-center" data-testid="verify-email-page">
        {state.status === "loading" && (
          <div className="flex flex-col items-center gap-4 py-12">
            <Loader2 className="h-8 w-8 animate-spin text-secondary" />
            <p className="text-muted-foreground">Verifying your email...</p>
          </div>
        )}
        {state.status === "success" && (
          <div className="flex flex-col items-center gap-4 py-12">
            <CheckCircle2 className="h-12 w-12 text-success" />
            <h1 className="text-2xl font-display tracking-tight text-primary dark:text-white">Email verified</h1>
            <p className="text-muted-foreground text-sm">{state.message}</p>
            <Link to="/dashboard" className="mt-2 rounded-full bg-primary text-primary-foreground px-6 py-3 text-sm font-semibold">Open dashboard</Link>
          </div>
        )}
        {state.status === "error" && (
          <div className="flex flex-col items-center gap-4 py-12">
            <XCircle className="h-12 w-12 text-destructive" />
            <h1 className="text-2xl font-display tracking-tight text-primary dark:text-white">Verification failed</h1>
            <p className="text-muted-foreground text-sm">{state.message}</p>
            <Link to="/login" className="mt-2 text-secondary font-semibold hover:underline">Back to sign in</Link>
          </div>
        )}
      </div>
    </AuthLayout>
  );
}
