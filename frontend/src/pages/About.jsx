import React from "react";
import SiteLayout from "@/components/SiteLayout";
import { Link } from "react-router-dom";

export default function About() {
  return (
    <SiteLayout>
      <section className="section-y" data-testid="about-page">
        <div className="container-luxe max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Our story</p>
          <h1 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Built by operators tired of spreadsheets, DMs and missed invoices.
          </h1>
          <div className="mt-8 prose prose-neutral dark:prose-invert max-w-none text-foreground/80 leading-relaxed space-y-5">
            <p>BrandKrt was started in 2026 with a single belief: the influencer economy deserves the same operational rigor as any modern marketplace. Stripe rebuilt payments. Linear rebuilt project tracking. We're doing the same for creator partnerships.</p>
            <p>Today, BrandKrt is the trusted infrastructure layer for hundreds of brands and thousands of verified creators across 40+ countries. Every transaction passes through KYC, escrow and real-time analytics — so both sides can focus on the creative work, not the chase.</p>
            <p>Our team is small, opinionated and obsessed with quality. If that sounds like your kind of place — <Link to="/contact" className="text-secondary font-semibold hover:underline">say hello</Link>.</p>
          </div>
        </div>
      </section>
    </SiteLayout>
  );
}
