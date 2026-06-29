import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ShieldCheck, FileSignature, CreditCard, BarChart3, Users, Sparkles,
  ArrowRight, Check, Star, Mail, Send, ChevronRight,
} from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";

/* ---------- Hero ---------- */
function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 -z-10 grid-bg opacity-40" />
      <div className="absolute -z-10 top-20 -right-20 h-80 w-80 rounded-full bg-secondary/10 blur-3xl animate-float-slow" />
      <div className="absolute -z-10 -bottom-20 -left-20 h-80 w-80 rounded-full bg-primary/10 blur-3xl animate-float-slow" />
      <div className="container-luxe pt-24 md:pt-32 pb-20 md:pb-28">
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
          className="max-w-4xl"
        >
          <span className="inline-flex items-center gap-2 rounded-full border border-secondary/30 bg-accent px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-secondary" data-testid="hero-badge">
            <Sparkles className="h-3.5 w-3.5" /> Built for SMBs &amp; nano creators
          </span>
          <h1 className="mt-8 text-5xl sm:text-6xl lg:text-7xl font-light tracking-tighter text-primary dark:text-white leading-[1.02]" data-testid="hero-headline">
            Where small businesses{" "}
            <br className="hidden sm:block" />
            meet <span className="gold-text font-semibold">nano &amp; micro</span> creators.
          </h1>
          <p className="mt-7 text-lg md:text-xl text-muted-foreground max-w-2xl leading-relaxed" data-testid="hero-subtitle">
            BrandKrt is the affordable creator marketplace built for small and medium businesses and nano/micro influencers — verification, contracts, escrow and reporting, with no minimum budgets and no agency middlemen.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3">
            <Link
              to="/register?role=influencer"
              data-testid="hero-cta-influencer"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-7 py-3.5 text-sm font-semibold transition-colors"
            >
              Join as Creator <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/register?role=brand"
              data-testid="hero-cta-brand"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-7 py-3.5 text-sm font-semibold transition-colors"
            >
              Sign up as Business <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="mt-12 flex flex-wrap items-center gap-x-8 gap-y-4 text-sm text-muted-foreground">
            {["KYC-verified nano creators", "Escrow from ₹500", "Made for local SMBs"].map((t) => (
              <div key={t} className="flex items-center gap-2"><Check className="h-4 w-4 text-secondary" /> {t}</div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-6"
          data-testid="hero-stats"
        >
          {[
            { v: "8K+", l: "Nano & Micro Creators" },
            { v: "1.2K+", l: "Small Businesses" },
            { v: "₹4.6Cr", l: "Paid to Creators" },
            { v: "4.9★", l: "Average Rating" },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl border border-border bg-card p-6">
              <div className="text-3xl md:text-4xl font-display font-light text-primary dark:text-white">{s.v}</div>
              <div className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">{s.l}</div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ---------- Features ---------- */
const FEATURES = [
  { icon: ShieldCheck, title: "Verified Identities", desc: "Every brand and creator passes KYC and platform-handle verification before listing." },
  { icon: FileSignature, title: "Smart Contracts", desc: "Auto-generated, e-signed agreements with clear deliverables and revisions baked in." },
  { icon: CreditCard, title: "Escrow Payments", desc: "Funds held securely and released milestone-by-milestone. No more chasing invoices." },
  { icon: BarChart3, title: "Live Analytics", desc: "Track impressions, engagement and ROI in real time across every campaign." },
  { icon: Users, title: "Curated Discovery", desc: "Search creators by niche, geography, audience quality — not just follower counts." },
  { icon: Sparkles, title: "White-glove Support", desc: "Dedicated account managers for growth-stage brands and top-tier creators." },
];

function Features() {
  return (
    <section id="features" className="section-y">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary" data-testid="features-overline">Features</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white" data-testid="features-heading">
            Everything an SMB needs<br /> to run creator campaigns.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground">Designed for small businesses with small budgets and big ambition — discover, brief, ship, measure, pay. No agency. No spreadsheets.</p>
        </div>
        <div className="mt-16 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.05 }}
              className="group rounded-2xl border border-border bg-card p-8 hover:-translate-y-1 hover:shadow-luxe transition-all"
              data-testid={`feature-card-${i}`}
            >
              <div className="h-12 w-12 rounded-xl bg-accent flex items-center justify-center text-secondary group-hover:bg-secondary group-hover:text-secondary-foreground transition-colors">
                <f.icon className="h-5 w-5" />
              </div>
              <h3 className="mt-6 text-xl font-medium text-primary dark:text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- How it works ---------- */
const STEPS = [
  { n: "01", t: "Sign up free", d: "Small businesses or nano creators — get started in 60 seconds." },
  { n: "02", t: "Get verified", d: "Quick KYC + social check builds trust on both sides." },
  { n: "03", t: "Match locally", d: "Discover creators by city, niche and budget — or get matched automatically." },
  { n: "04", t: "Run the collab", d: "Brief, ship product, approve content — all in one place." },
  { n: "05", t: "Pay on delivery", d: "Escrow releases the moment the post goes live. Done." },
];

function HowItWorks() {
  return (
    <section id="how-it-works" className="section-y bg-accent dark:bg-card">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Process</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            From shop to social post in five steps.
          </h2>
        </div>
        <div className="mt-16 grid gap-8 lg:grid-cols-5">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.n}
              initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.07 }}
              className="relative rounded-2xl border border-border bg-background p-6"
              data-testid={`step-card-${i}`}
            >
              <div className="text-secondary text-sm font-semibold tracking-[0.3em]">{s.n}</div>
              <h3 className="mt-4 text-lg font-medium text-primary dark:text-white">{s.t}</h3>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{s.d}</p>
              {i < STEPS.length - 1 && (
                <ChevronRight className="hidden lg:block absolute -right-5 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary/50" />
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- Benefits / Why Choose ---------- */
function WhyChoose() {
  const items = [
    { t: "Built for small budgets", d: "Run a real campaign for ₹500 — no minimum spend, no annual contracts, no agency retainer." },
    { t: "Nano & micro creators win", d: "Authentic local creators with 1K–100K followers — the audience that actually converts for SMBs." },
    { t: "Transparent 8% fee", d: "Flat platform fee. No hidden agency commissions, no FX spreads, no upsells." },
    { t: "Local-first matching", d: "Find creators in your city or pin code who genuinely care about your category." },
  ];
  return (
    <section className="section-y">
      <div className="container-luxe grid gap-16 lg:grid-cols-2 items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Why BrandKrt</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            The marketplace SMBs and nano creators can actually afford.
          </h2>
          <p className="mt-6 text-lg text-muted-foreground">We replaced agency markups, copy-paste DMs and missed payments with one simple workspace — priced for businesses that count every rupee.</p>
          <div className="mt-8">
            <Link to="/register" data-testid="why-cta" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold">
              Create your account <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 gap-5">
          {items.map((it, i) => (
            <motion.div
              key={it.t}
              initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.06 }}
              className="rounded-2xl border border-border bg-card p-6"
              data-testid={`why-card-${i}`}
            >
              <div className="h-9 w-9 rounded-full bg-secondary text-secondary-foreground flex items-center justify-center font-semibold">{i + 1}</div>
              <h3 className="mt-4 text-lg font-medium text-primary dark:text-white">{it.t}</h3>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{it.d}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- Testimonials ---------- */
const TESTIMONIALS = [
  { name: "Priya Kulkarni", role: "Nano Creator — 9.4K followers", img: "https://images.pexels.com/photos/27086922/pexels-photo-27086922.jpeg", q: "I never imagined getting paid for collabs at 9K followers. BrandKrt makes it normal — and I always get paid on time." },
  { name: "Rohit Shah", role: "Founder, Café Mocha Pune", img: "https://images.pexels.com/photos/29086752/pexels-photo-29086752.jpeg", q: "We ran four nano-creator campaigns for under ₹20K total. Footfall doubled on weekends. No agency could have given us this ROI." },
  { name: "Anjali Rao", role: "Micro Creator — 42K followers", img: "https://images.pexels.com/photos/27086922/pexels-photo-27086922.jpeg", q: "Clean contracts, fast escrow, real local brands. Finally a platform that treats small creators like real partners." },
];

function Testimonials() {
  return (
    <section className="section-y bg-primary text-white">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Loved by both sides</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight">
            Trusted by local businesses and the creators who serve them.
          </h2>
        </div>
        <div className="mt-16 grid gap-6 md:grid-cols-3">
          {TESTIMONIALS.map((t, i) => (
            <motion.figure
              key={t.name}
              initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.07 }}
              className="rounded-2xl border border-white/10 bg-white/5 p-7"
              data-testid={`testimonial-${i}`}
            >
              <div className="flex gap-1 text-secondary">
                {Array.from({ length: 5 }).map((_, k) => <Star key={k} className="h-4 w-4 fill-current" />)}
              </div>
              <blockquote className="mt-5 text-base leading-relaxed text-white/90">“{t.q}”</blockquote>
              <figcaption className="mt-6 flex items-center gap-3">
                <img src={t.img} alt={t.name} className="h-10 w-10 rounded-full object-cover" />
                <div>
                  <div className="text-sm font-semibold">{t.name}</div>
                  <div className="text-xs text-white/60">{t.role}</div>
                </div>
              </figcaption>
            </motion.figure>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- Pricing ---------- */
const PLANS = [
  { name: "Starter", price: "Free", per: "forever", features: ["Up to 3 active campaigns", "Local creator search", "1-click contract templates", "Email support"], cta: "Start free", testId: "pricing-starter", highlight: false },
  { name: "SMB", price: "₹999", per: "/ month", features: ["Unlimited campaigns", "Priority creator matching", "Escrow + UPI / bank payouts", "Performance reporting", "Chat support"], cta: "Start 14-day trial", testId: "pricing-growth", highlight: true },
  { name: "Pro / Agency", price: "Custom", per: "billed annually", features: ["Multi-brand workspaces", "Bulk campaign tools", "Custom contracts", "Dedicated success manager", "API access"], cta: "Talk to us", testId: "pricing-enterprise", highlight: false },
];

function Pricing() {
  return (
    <section id="pricing" className="section-y">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Pricing</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Affordable for SMBs. Fair for creators.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground">Flat 8% platform fee on payouts. Pick a plan that fits your stage — no annual lock-in, no hidden charges.</p>
        </div>
        <div className="mt-16 grid gap-6 lg:grid-cols-3">
          {PLANS.map((p) => (
            <div
              key={p.name}
              data-testid={p.testId}
              className={`relative rounded-2xl p-8 transition-all hover:-translate-y-1 ${p.highlight ? "bg-card border-2 border-secondary shadow-gold-glow" : "bg-card border border-border hover:shadow-luxe"}`}
            >
              {p.highlight && (
                <span className="absolute -top-3 left-8 inline-flex items-center gap-1 rounded-full bg-secondary text-secondary-foreground px-3 py-1 text-xs font-semibold">
                  Most Popular
                </span>
              )}
              <h3 className="text-xl font-medium text-primary dark:text-white">{p.name}</h3>
              <div className="mt-5 flex items-baseline gap-2">
                <span className="text-4xl font-display font-light text-primary dark:text-white">{p.price}</span>
                <span className="text-sm text-muted-foreground">{p.per}</span>
              </div>
              <ul className="mt-7 space-y-3">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-foreground/80">
                    <Check className="h-4 w-4 mt-0.5 text-secondary shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={`mt-8 inline-flex w-full items-center justify-center rounded-full px-5 py-3 text-sm font-semibold transition-colors ${
                  p.highlight ? "bg-primary text-primary-foreground hover:bg-primary/90" : "border border-border hover:bg-accent"
                }`}
                data-testid={`${p.testId}-cta`}
              >
                {p.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- FAQ ---------- */
const FAQS = [
  { q: "Can I run a campaign with a small budget?", a: "Yes — that's exactly who BrandKrt is built for. You can escrow as little as ₹500 and pair with nano creators (1K–10K followers) at affordable rates. No minimum spends, no annual contracts." },
  { q: "Why nano and micro creators?", a: "Smaller creators have higher trust and 3–5× the engagement of celebrity influencers — and they're far more affordable for local businesses. Perfect for cafés, salons, D2C launches, kirana shops, and emerging brands." },
  { q: "How do payments work for creators?", a: "Brands escrow the agreed amount upfront. Once your deliverable goes live and is approved, funds are released to your UPI or bank account. You can withdraw any time from the Earnings page." },
  { q: "What's the platform fee?", a: "A flat 8% on the deal amount — covers verification, contracts, escrow and dispute support. There are no hidden charges, no FX spreads, and no agency commissions." },
  { q: "Can I cancel anytime?", a: "Absolutely. Paid plans are month-to-month and can be cancelled from your settings at any time. The free Starter plan never expires." },
];

function FAQ() {
  return (
    <section id="faq" className="section-y bg-accent dark:bg-card">
      <div className="container-luxe grid gap-12 lg:grid-cols-2">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">FAQ</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Questions, answered.
          </h2>
          <p className="mt-6 text-muted-foreground">Can&apos;t find what you need? <Link to="/contact" className="text-secondary underline-offset-4 hover:underline">Talk to our team.</Link></p>
        </div>
        <Accordion type="single" collapsible className="space-y-3">
          {FAQS.map((f, i) => (
            <AccordionItem key={f.q} value={`item-${i}`} className="rounded-2xl border border-border bg-background px-6" data-testid={`faq-item-${i}`}>
              <AccordionTrigger className="text-left text-base font-medium text-primary dark:text-white">{f.q}</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

/* ---------- Contact ---------- */
function ContactSection() {
  const [form, setForm] = useState({ name: "", email: "", subject: "", message: "" });
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { data } = await api.post("/contact", form);
      toast.success(data.message || "Thanks — we'll be in touch.");
      setForm({ name: "", email: "", subject: "", message: "" });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section id="contact" className="section-y">
      <div className="container-luxe grid gap-12 lg:grid-cols-2">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Contact</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Tell us about your business.
          </h2>
          <p className="mt-6 text-lg text-muted-foreground">For small businesses planning their first creator campaign, nano creators with questions, or anything in between — we usually reply within a day.</p>
          <div className="mt-8 space-y-3 text-sm text-muted-foreground">
            <a href="mailto:support@brandkrt.com" className="flex items-center gap-3 hover:text-secondary"><Mail className="h-4 w-4" /> support@brandkrt.com</a>
            <a href="mailto:vaibhav@brandkrt.com" className="flex items-center gap-3 hover:text-secondary"><Mail className="h-4 w-4" /> vaibhav@brandkrt.com</a>
          </div>
        </div>
        <form onSubmit={submit} className="rounded-2xl border border-border bg-card p-8 space-y-5" data-testid="contact-form">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Name</label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="contact-name" className="mt-2" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Email</label>
              <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required data-testid="contact-email" className="mt-2" />
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Subject</label>
            <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required data-testid="contact-subject" className="mt-2" />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Message</label>
            <Textarea rows={5} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} required data-testid="contact-message" className="mt-2" />
          </div>
          <button
            type="submit"
            disabled={submitting}
            data-testid="contact-submit"
            className="inline-flex items-center justify-center gap-2 w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold disabled:opacity-60"
          >
            {submitting ? "Sending..." : (<>Send Message <Send className="h-4 w-4" /></>)}
          </button>
        </form>
      </div>
    </section>
  );
}

/* ---------- Landing ---------- */
export default function Landing() {
  // hash scroll
  useEffect(() => {
    if (window.location.hash) {
      const el = document.getElementById(window.location.hash.slice(1));
      if (el) setTimeout(() => el.scrollIntoView({ behavior: "smooth" }), 100);
    }
  }, []);
  return (
    <div data-testid="landing-page">
      <Hero />
      <Features />
      <HowItWorks />
      <WhyChoose />
      <Testimonials />
      <Pricing />
      <FAQ />
      <ContactSection />
    </div>
  );
}
