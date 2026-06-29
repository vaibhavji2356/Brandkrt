import React from "react";
import SiteLayout from "@/components/SiteLayout";
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <SiteLayout>
      <section className="section-y" data-testid="not-found-page">
        <div className="container-luxe text-center">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">404</p>
          <h1 className="mt-4 text-5xl sm:text-6xl font-light tracking-tight text-primary dark:text-white">Page not found</h1>
          <p className="mt-4 text-muted-foreground">The page you're looking for has moved or doesn't exist.</p>
          <Link to="/" className="mt-8 inline-flex rounded-full bg-primary text-primary-foreground px-6 py-3 text-sm font-semibold hover:bg-primary/90">Back to home</Link>
        </div>
      </section>
    </SiteLayout>
  );
}
