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
            <Sparkles className="h-3.5 w-3.5" /> The premium creator marketplace
          </span>
          <h1 className="mt-8 text-5xl sm:text-6xl lg:text-7xl font-light tracking-tighter text-primary dark:text-white leading-[1.02]" data-testid="hero-headline">
            Where ambitious brands<br />
            meet <span className="gold-text font-semibold">extraordinary</span> creators.
          </h1>
          <p className="mt-7 text-lg md:text-xl text-muted-foreground max-w-2xl leading-relaxed" data-testid="hero-subtitle">
            BrandKrt is the end-to-end marketplace handling verification, contracts, payments and analytics — so every collaboration ships on time, on brand, and on budget.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3">
            <Link
              to="/register?role=influencer"
              data-testid="hero-cta-influencer"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-7 py-3.5 text-sm font-semibold transition-colors"
            >
              Join as Influencer <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/register?role=brand"
              data-testid="hero-cta-brand"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-7 py-3.5 text-sm font-semibold transition-colors"
            >
              Register a Brand <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="mt-12 flex flex-wrap items-center gap-x-8 gap-y-4 text-sm text-muted-foreground">
            {["KYC-verified creators", "Escrow-secured payments", "Real-time analytics"].map((t) => (
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
            { v: "12K+", l: "Verified Creators" },
            { v: "850+", l: "Active Brands" },
            { v: "$24M", l: "Paid to Creators" },
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
            Everything you need to run<br /> creator campaigns end-to-end.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground">A platform engineered to remove friction at every step — discover, contract, deliver, measure, pay.</p>
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
  { n: "01", t: "Create Account", d: "Sign up in under 60 seconds as a brand or creator." },
  { n: "02", t: "Verification", d: "Pass KYC and connect your social handles for trust badges." },
  { n: "03", t: "Connect", d: "Discover and shortlist via deep filters, audience insights, and AI matchmaking." },
  { n: "04", t: "Campaign", d: "Brief, contract, deliver and revise — all inside BrandKrt." },
  { n: "05", t: "Payment", d: "Escrow releases funds the moment deliverables go live." },
];

function HowItWorks() {
  return (
    <section id="how-it-works" className="section-y bg-accent dark:bg-card">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Process</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            From discovery to payout in five steps.
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
    { t: "Built for both sides", d: "Tools designed equally for brand marketers and creator businesses — not retrofitted from a vendor portal." },
    { t: "Premium curation", d: "We turn down 7 out of 10 applicants. The roster you see has been earned." },
    { t: "Transparent economics", d: "Flat 8% platform fee. No hidden spreads, no surprise FX, no upsells." },
    { t: "Global, multi-currency", d: "Pay creators across 40+ countries in their local currency with one click." },
  ];
  return (
    <section className="section-y">
      <div className="container-luxe grid gap-16 lg:grid-cols-2 items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Why BrandKrt</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            A platform built for partnerships that actually perform.
          </h2>
          <p className="mt-6 text-lg text-muted-foreground">We replaced the spreadsheets, DMs and invoice chasing with a single, premium workflow trusted by leading brands and elite creators.</p>
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
  { name: "Aanya Mehta", role: "Lifestyle Creator — 480K followers", img: "https://images.pexels.com/photos/27086922/pexels-photo-27086922.jpeg", q: "BrandKrt is the only platform where I actually get paid on time. The contracts are clean and the brands are serious." },
  { name: "Rohan Verma", role: "Marketing Director, Lumen Co.", img: "https://images.pexels.com/photos/29086752/pexels-photo-29086752.jpeg", q: "We replaced three agencies and an entire shared inbox with BrandKrt. ROI tracking alone paid for the platform in week one." },
  { name: "Sara Iqbal", role: "Beauty Creator — 1.2M followers", img: "https://images.pexels.com/photos/27086922/pexels-photo-27086922.jpeg", q: "From brief to payout in a single tab. Every other tool feels archaic after this." },
];

function Testimonials() {
  return (
    <section className="section-y bg-primary text-white">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Loved by both sides</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight">
            Trusted by brands and creators who lead culture.
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
  { name: "Starter", price: "Free", per: "forever", features: ["Up to 3 active campaigns", "Verified creator search", "Standard contracts", "Email support"], cta: "Start free", testId: "pricing-starter", highlight: false },
  { name: "Growth", price: "$199", per: "/ month", features: ["Unlimited campaigns", "Priority creator matchmaking", "Escrow + multi-currency payouts", "Advanced analytics", "Dedicated success manager"], cta: "Start 14-day trial", testId: "pricing-growth", highlight: true },
  { name: "Enterprise", price: "Custom", per: "billed annually", features: ["SSO + custom workflows", "API & integrations", "Bespoke contracts", "24/7 white-glove support", "SLA & uptime guarantees"], cta: "Talk to sales", testId: "pricing-enterprise", highlight: false },
];

function Pricing() {
  return (
    <section id="pricing" className="section-y">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Pricing</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Honest pricing. No hidden spreads.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground">Flat 8% platform fee on transactions. Choose the plan that fits how you run partnerships.</p>
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
  { q: "How does BrandKrt verify creators?", a: "Every creator passes a multi-step verification: government-ID KYC, social handle ownership check, and audience-quality scoring. Top accounts also receive a manual editorial review." },
  { q: "How are payments handled?", a: "Funds are held in escrow and released milestone-by-milestone once deliverables are approved. We support 40+ currencies and most popular local payout methods." },
  { q: "What does the platform fee cover?", a: "Verification, contracts, escrow, analytics and dispute resolution. Flat 8% — no spreads, no upsells." },
  { q: "Can I cancel anytime?", a: "Yes. Growth plans are month-to-month and can be cancelled from your billing settings at any time." },
  { q: "Do you support agencies?", a: "Absolutely. Agencies can manage multiple brand workspaces, invite team members, and bill clients directly through BrandKrt." },
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
          <p className="mt-6 text-muted-foreground">Can't find what you need? <Link to="/contact" className="text-secondary underline-offset-4 hover:underline">Talk to our team.</Link></p>
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
            Tell us about your next campaign.
          </h2>
          <p className="mt-6 text-lg text-muted-foreground">For brands launching campaigns, creators with questions, or partnership enquiries — we typically reply within 24 hours.</p>
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
