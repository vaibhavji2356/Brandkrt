import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import AuthLayout from "./AuthLayout";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { Eye, EyeOff } from "lucide-react";
import { getGoogleClientId, isGoogleConfigured, renderGoogleSignInButton, setGoogleClientId } from "@/lib/googleAuth";
import api from "@/lib/api";
import { waitForBackendReady } from "@/lib/backendStatus";

export default function Login() {
  const { login, googleSignIn, formatApiError } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [show, setShow] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [error, setError] = useState("");
  const [googleEnabled, setGoogleEnabled] = useState(isGoogleConfigured());
  const [googleConfigState, setGoogleConfigState] = useState("checking");
  const googleBtnRef = useRef(null);

  // Wait for Render readiness before deciding whether Google is configured. A
  // network failure during a cold start must not be shown as a config error.
  useEffect(() => {
    let alive = true;
    waitForBackendReady({
      onState: ({ state }) => {
        if (alive && (state === "checking" || state === "waking")) setGoogleConfigState("waking");
      },
    }).then(() => api.get("/auth/google/config")).then((r) => {
      if (!alive) return;
      const clientId = r.data?.client_id || "";
      setGoogleClientId(clientId);
      const enabled = !!r.data?.enabled && !!clientId;
      setGoogleEnabled(enabled);
      setGoogleConfigState(enabled ? "enabled" : "disabled");
    }).catch(() => {
      if (alive) setGoogleConfigState("unavailable");
    });
    return () => { alive = false; };
  }, []);

  const completeGoogleSignIn = async (credential) => {
    setGoogleBusy(true);
    try {
      const u = await googleSignIn(credential);
      toast.success(`Welcome ${u.name?.split(" ")[0] || ""}!`);
      const dest = u.role === "admin" ? "/admin" : u.role === "brand" ? "/brand" : "/influencer";
      navigate(dest, { replace: true });
    } catch (err) {
      toast.error(formatApiError ? formatApiError(err) : (err?.message || "Google sign-in failed"));
    } finally {
      setGoogleBusy(false);
    }
  };

  useEffect(() => {
    if (!googleEnabled || !googleBtnRef.current) return;
    let cancelled = false;
    const render = () => {
      if (cancelled || !googleBtnRef.current) return;
      renderGoogleSignInButton(googleBtnRef.current, {
        clientId: getGoogleClientId(),
        width: googleBtnRef.current.offsetWidth || 360,
        onCredential: completeGoogleSignIn,
      }).catch((err) => {
        if (!cancelled) toast.error(formatApiError ? formatApiError(err) : (err?.message || "Google sign-in failed"));
      });
    };
    render();
    window.addEventListener("resize", render);
    return () => {
      cancelled = true;
      window.removeEventListener("resize", render);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleEnabled]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const u = await login(email, password, remember);
      toast.success("Welcome back!");
      const dest = u.role === "admin" ? "/admin" : u.role === "brand" ? "/brand" : "/influencer";
      navigate(dest, { replace: true });
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout tagline="Sign in">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-display font-light tracking-tight text-primary dark:text-white">Welcome back</h1>
        <p className="text-sm text-muted-foreground">Sign in to your BrandKrt account.</p>
      </div>

      <form onSubmit={submit} className="mt-8 space-y-5" data-testid="login-form">
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Email</label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" data-testid="login-email" className="mt-2" placeholder="you@brandkrt.com" />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Password</label>
          <div className="relative mt-2">
            <Input type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" data-testid="login-password" placeholder="••••••••" />
            <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-label="Toggle password">
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-foreground/80">
            <Checkbox checked={remember} onCheckedChange={(v) => setRemember(!!v)} data-testid="login-remember" />
            Remember me
          </label>
          <Link to="/forgot-password" className="text-sm text-secondary hover:underline" data-testid="login-forgot-link">Forgot password?</Link>
        </div>

        {error && <p className="text-sm text-destructive" data-testid="login-error">{error}</p>}

        <button type="submit" disabled={submitting} data-testid="login-submit" className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold transition-colors disabled:opacity-60">
          {submitting ? "Signing in..." : "Sign in"}
        </button>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-border" /></div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-background px-3 text-muted-foreground">or</span>
          </div>
        </div>

        {!googleEnabled && googleConfigState !== "waking" && googleConfigState !== "checking" && (
        <button
          type="button"
          onClick={() => toast.error(
            googleConfigState === "disabled"
              ? "Google sign-in is not configured on this server yet."
              : "Google sign-in is temporarily unavailable. Please try again shortly."
          )}
          disabled={googleBusy}
          data-testid="login-google"
          aria-label="Continue with Google"
          className="w-full flex items-center justify-center gap-3 rounded-full border border-border bg-background hover:bg-accent px-6 py-3 text-sm font-medium transition-colors disabled:opacity-60"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09A6.99 6.99 0 0 1 5.47 12c0-.73.13-1.44.36-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.78.43 3.47 1.18 4.97l3.66-2.88z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/></svg>
          {googleBusy ? "Signing in…" : "Continue with Google"}
        </button>
        )}
        <div
          ref={googleBtnRef}
          data-testid="login-google"
          className={`flex min-h-[44px] w-full justify-center overflow-hidden rounded-full ${googleBusy ? "pointer-events-none opacity-60" : ""} ${googleEnabled ? "" : "hidden"}`}
        />

        <p className="text-center text-sm text-muted-foreground pt-2">
          New to BrandKrt? <Link to="/register" className="font-semibold text-primary dark:text-white hover:text-secondary" data-testid="login-to-register">Create an account</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
