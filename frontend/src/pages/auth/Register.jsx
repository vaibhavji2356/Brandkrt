import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "./AuthLayout";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { Eye, EyeOff, Sparkles, Briefcase } from "lucide-react";

const ROLES = [
  { id: "influencer", title: "I'm a Creator", desc: "Earn from premium brand campaigns.", icon: Sparkles },
  { id: "brand", title: "I'm a Brand", desc: "Run end-to-end creator campaigns.", icon: Briefcase },
];

export default function Register() {
  const { register, formatApiError } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialRole = ["influencer", "brand"].includes(params.get("role")) ? params.get("role") : "influencer";

  const [role, setRole] = useState(initialRole);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accept, setAccept] = useState(false);
  const [show, setShow] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!accept) { setError("Please accept the terms and privacy policy."); return; }
    setSubmitting(true);
    try {
      const u = await register({ name, email, password, role, accept_terms: true });
      toast.success("Account created — check your inbox to verify your email.");
      const dest =
        u.role === "admin"
          ? "/admin"
          : u.role === "influencer"
          ? "/influencer"
          : "/profile";
      navigate(dest, { replace: true });
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout side="right" tagline="Create your account">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-display font-light tracking-tight text-primary dark:text-white">Join BrandKrt</h1>
        <p className="text-sm text-muted-foreground">Choose your role and get started in under a minute.</p>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3" data-testid="register-role-select">
        {ROLES.map((r) => {
          const active = role === r.id;
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => setRole(r.id)}
              data-testid={`register-role-${r.id}`}
              className={`relative rounded-2xl border p-4 text-left transition-all ${active ? "border-secondary bg-accent shadow-gold-glow" : "border-border bg-card hover:border-secondary/50"}`}
            >
              <r.icon className={`h-5 w-5 ${active ? "text-secondary" : "text-muted-foreground"}`} />
              <div className="mt-3 text-sm font-semibold text-primary dark:text-white">{r.title}</div>
              <div className="mt-1 text-xs text-muted-foreground leading-snug">{r.desc}</div>
            </button>
          );
        })}
      </div>

      <form onSubmit={submit} className="mt-6 space-y-4" data-testid="register-form">
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Full name</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} data-testid="register-name" className="mt-2" placeholder="Ava Sharma" />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Email</label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" data-testid="register-email" className="mt-2" placeholder="you@brandkrt.com" />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Password</label>
          <div className="relative mt-2">
            <Input type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" data-testid="register-password" placeholder="At least 8 characters" />
            <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-label="Toggle password">
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <label className="flex items-start gap-3 text-sm text-foreground/80">
          <Checkbox checked={accept} onCheckedChange={(v) => setAccept(!!v)} data-testid="register-accept" className="mt-0.5" />
          <span>
            I agree to the <Link to="/terms" className="text-secondary hover:underline">Terms</Link> and <Link to="/privacy" className="text-secondary hover:underline">Privacy Policy</Link>.
          </span>
        </label>

        {error && <p className="text-sm text-destructive" data-testid="register-error">{error}</p>}

        <button type="submit" disabled={submitting} data-testid="register-submit" className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold transition-colors disabled:opacity-60">
          {submitting ? "Creating account..." : "Create account"}
        </button>

        <p className="text-center text-sm text-muted-foreground pt-2">
          Already on BrandKrt? <Link to="/login" className="font-semibold text-primary dark:text-white hover:text-secondary" data-testid="register-to-login">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
