import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "./AuthLayout";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export default function ResetPassword() {
  const { resetPassword, formatApiError } = useAuth();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (!token) { setError("Missing reset token."); return; }
    setSubmitting(true);
    try {
      await resetPassword(token, password);
      toast.success("Password updated. You can now sign in.");
      navigate("/login", { replace: true });
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout tagline="Set new password">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-display font-light tracking-tight text-primary dark:text-white">Choose a new password</h1>
        <p className="text-sm text-muted-foreground">Make it at least 8 characters and easy to remember.</p>
      </div>
      <form onSubmit={submit} className="mt-8 space-y-5" data-testid="reset-form">
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">New password</label>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} data-testid="reset-password" className="mt-2" />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Confirm password</label>
          <Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} data-testid="reset-confirm" className="mt-2" />
        </div>
        {error && <p className="text-sm text-destructive" data-testid="reset-error">{error}</p>}
        <button type="submit" disabled={submitting} data-testid="reset-submit" className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold disabled:opacity-60">
          {submitting ? "Updating..." : "Update password"}
        </button>
        <p className="text-center text-sm text-muted-foreground">
          <Link to="/login" className="font-semibold text-primary dark:text-white hover:text-secondary">Back to sign in</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
