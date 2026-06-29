import React from "react";
import { Link } from "react-router-dom";
import Logo from "@/components/Logo";
import { Star } from "lucide-react";

export default function AuthLayout({ children, side = "left", tagline }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      <div className={`relative hidden lg:flex ${side === "left" ? "order-first" : "order-last"} bg-primary text-white overflow-hidden`}>
        <div className="absolute inset-0 opacity-30" style={{
          backgroundImage: "radial-gradient(circle at 20% 20%, rgba(212,175,55,0.35), transparent 40%), radial-gradient(circle at 80% 80%, rgba(212,175,55,0.25), transparent 45%)"
        }} />
        <div className="relative z-10 p-12 xl:p-16 flex flex-col justify-between w-full">
          <Link to="/" className="inline-block">
            <Logo textClassName="text-white" />
          </Link>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">{tagline || "Welcome to BrandKrt"}</p>
            <h2 className="mt-5 text-4xl xl:text-5xl font-light tracking-tight leading-tight">
              The premium marketplace for brands and creators.
            </h2>
            <p className="mt-5 text-white/70 max-w-md leading-relaxed">
              Discover verified creators, run campaigns end-to-end and pay securely — all from one workspace.
            </p>
            <figure className="mt-10 rounded-2xl border border-white/10 bg-white/5 backdrop-blur p-6 max-w-md">
              <div className="flex gap-1 text-secondary">{Array.from({ length: 5 }).map((_, k) => <Star key={k} className="h-4 w-4 fill-current" />)}</div>
              <blockquote className="mt-3 text-sm text-white/90 leading-relaxed">"BrandKrt feels like Stripe for influencer marketing — quietly powerful, premium, and built for serious operators."</blockquote>
              <figcaption className="mt-3 text-xs text-white/60">— Director of Growth, Lumen Co.</figcaption>
            </figure>
          </div>
          <p className="text-xs text-white/40">© {new Date().getFullYear()} BrandKrt — brandkrt.com</p>
        </div>
      </div>
      <div className="flex flex-col">
        <div className="flex items-center justify-between p-6 lg:hidden">
          <Link to="/"><Logo /></Link>
          <Link to="/" className="text-sm text-muted-foreground">← Home</Link>
        </div>
        <div className="flex-1 flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-md">{children}</div>
        </div>
      </div>
    </div>
  );
}
