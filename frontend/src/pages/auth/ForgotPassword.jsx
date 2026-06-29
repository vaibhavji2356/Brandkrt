import React, { useState } from "react";
import { Link } from "react-router-dom";
import AuthLayout from "./AuthLayout";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export default function ForgotPassword() {
  const { forgotPassword, formatApiError } = useAuth();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await forgotPassword(email);
      setSent(true);
      toast.success("If that email exists, we've sent reset instructions.");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout tagline="Reset password">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-display font-light tracking-tight text-primary dark:text-white">Forgot password</h1>
        <p className="text-sm text-muted-foreground">We'll email you a secure reset link.</p>
      </div>
      {sent ? (
        <div className="mt-8 rounded-2xl border border-border bg-card p-6 text-sm text-foreground/80" data-testid="forgot-sent">
          <p>Check your inbox at <span className="font-semibold">{email}</span>. The link is valid for 1 hour.</p>
          <Link to="/login" className="mt-4 inline-block text-secondary font-semibold hover:underline">← Back to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-8 space-y-5" data-testid="forgot-form">
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Email</label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="forgot-email" className="mt-2" placeholder="you@brandkrt.com" />
          </div>
          <button type="submit" disabled={submitting} data-testid="forgot-submit" className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold disabled:opacity-60">
            {submitting ? "Sending..." : "Send reset link"}
          </button>
          <p className="text-center text-sm text-muted-foreground">
            Remembered? <Link to="/login" className="font-semibold text-primary dark:text-white hover:text-secondary">Back to sign in</Link>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
