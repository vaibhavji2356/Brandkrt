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
      <div className="absolute inset-0 -z-10 grid-bg opacity-30" />
      <div className="absolute inset-x-0 top-0 -z-10 h-px bg-secondary/40" />
      <div className="absolute inset-x-0 bottom-0 -z-10 h-px bg-border/80" />
      <div className="container-luxe pt-24 md:pt-32 pb-20 md:pb-28">
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
          className="max-w-4xl"
        >
          <span className="inline-flex items-center gap-2 rounded-full border border-secondary/30 bg-accent px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-secondary" data-testid="hero-badge">
            <Sparkles className="h-3.5 w-3.5" /> Affordable influencer marketing for every business
          </span>
          <h1 className="mt-8 text-5xl sm:text-6xl lg:text-7xl font-light tracking-tighter text-primary dark:text-white leading-[1.02]" data-testid="hero-headline">
            Where local businesses<br />
            meet the <span className="gold-text font-semibold">right</span> creators.
          </h1>
          <p className="mt-7 text-lg md:text-xl text-muted-foreground max-w-2xl leading-relaxed" data-testid="hero-subtitle">
            BrandKrt connects small &amp; medium businesses - restaurants, cafes, salons, gyms, clothing stores, coaching institutes, D2C and home brands - with verified nano &amp; micro creators on Instagram, YouTube and Facebook. Verified collaborations, secure escrow payments and one simple dashboard to run every campaign.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3">
            <Link
              to="/register?role=influencer"
              data-testid="hero-cta-influencer"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-7 py-3.5 text-sm font-semibold transition-colors"
            >
              I&apos;m a Creator - Earn from Brands <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/register?role=brand"
              data-testid="hero-cta-brand"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90 px-7 py-3.5 text-sm font-semibold transition-colors"
            >
              Promote my Business <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="mt-12 flex flex-wrap items-center gap-x-8 gap-y-4 text-sm text-muted-foreground">
            {["Verified creators", "Escrow-secured payments", "Affordable for any budget"].map((t) => (
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
            { v: "2,400+", l: "Local & D2C Brands" },
            { v: "Rs 0", l: "To Get Started" },
            { v: "4.9 star", l: "Average Rating" },
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
  { icon: ShieldCheck, title: "Verified Collaborations", desc: "Every creator and business is identity-checked and handle-verified before they can collaborate. No fake followers, no ghost brands." },
  { icon: CreditCard, title: "Secure Escrow Payments", desc: "Brands fund the campaign upfront, money stays safely in escrow, and creators get paid the moment deliverables go live." },
  { icon: Sparkles, title: "Built for Small Budgets", desc: "Designed for cafes, salons, gyms, clothing stores and home businesses. Start with a single nano-creator campaign for as little as Rs 999." },
  { icon: Users, title: "Nano & Micro Creator Network", desc: "Discover authentic creators across Instagram, YouTube and Facebook - sorted by niche, city and audience quality, not vanity followers." },
  { icon: FileSignature, title: "Simple Contracts & Briefs", desc: "Auto-generated agreements with clear deliverables, deadlines and revision rules - so nothing slips through the cracks." },
  { icon: BarChart3, title: "Easy Campaign Management", desc: "One dashboard to brief, chat, approve content, track posts and review ROI. No spreadsheets, no DMs, no chasing." },
];

function Features() {
  return (
    <section id="features" className="section-y">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary" data-testid="features-overline">Features</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white" data-testid="features-heading">
            Everything a local business needs<br /> to run creator campaigns.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground">From your first nano-creator post to a multi-city micro-influencer rollout - BrandKrt makes the whole journey affordable, verified and effortless.</p>
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
  { n: "01", t: "Sign Up Free", d: "Create your free account as a business or as a creator in under a minute." },
  { n: "02", t: "Get Verified", d: "Quick KYC + social handle check so every collaboration on BrandKrt is genuine and safe." },
  { n: "03", t: "Find Your Match", d: "Brands shortlist nano & micro creators by city, niche and price. Creators browse open campaigns." },
  { n: "04", t: "Run the Campaign", d: "Send the brief, agree on deliverables, ship the product or share details, approve the content - all inside BrandKrt." },
  { n: "05", t: "Get Paid Safely", d: "Money sits in escrow and is released to the creator the moment the post goes live and is approved." },
];

function HowItWorks() {
  return (
    <section id="how-it-works" className="section-y bg-accent dark:bg-card">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">How It Works</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            From sign up to live post in five simple steps.
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
    { t: "Affordable for any business", d: "Restaurants, cafes, salons, gyms, coaching institutes, clothing stores, D2C and home businesses - start campaigns from as little as Rs 999. No monthly minimums." },
    { t: "Verified creators only", d: "Every nano, micro, Instagram, YouTube and Facebook creator on BrandKrt clears ID + social handle verification. Real people, real audiences." },
    { t: "Secure escrow payments", d: "Brands pay safely upfront. Creators are guaranteed payment the moment their content goes live and is approved. No more chasing." },
    { t: "Easy campaign management", d: "Brief, chat, approve and track every collab in one dashboard. Built for owners who don't have a marketing team." },
  ];
  return (
    <section className="section-y">
      <div className="container-luxe grid gap-16 lg:grid-cols-2 items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Why BrandKrt</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Influencer marketing - finally built for small businesses and everyday creators.
          </h2>
          <p className="mt-6 text-lg text-muted-foreground">We replaced expensive agencies, random DMs and risky payments with one premium, verified marketplace that any local shop, cafe, salon or D2C brand can use - and any nano or micro creator can earn from.</p>
          <div className="mt-8">
            <Link to="/register" data-testid="why-cta" className="inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-3 text-sm font-semibold">
              Create your free account <ArrowRight className="h-4 w-4" />
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
  { name: "Priya Sharma", role: "Owner, Bloom Cafe - Pune", img: "https://images.pexels.com/photos/27086922/pexels-photo-27086922.jpeg", q: "We ran our first BrandKrt campaign with five nano creators in Pune. Footfall doubled the next weekend - for less than what one ad agency was quoting us." },
  { name: "Rohit Verma", role: "Founder, FitNation Gym - Jaipur", img: "https://images.pexels.com/photos/29086752/pexels-photo-29086752.jpeg", q: "BrandKrt got us 18 verified micro creators for our new branch launch. Escrow gave us total peace of mind on payments." },
  { name: "Aanya Mehta", role: "Instagram Creator - 22K followers", img: "https://images.pexels.com/photos/27086922/pexels-photo-27086922.jpeg", q: "I'm a nano creator and I'm finally getting paid on time, every time. BrandKrt is the only platform where small brands actually find me." },
];

function Testimonials() {
  return (
    <section className="section-y bg-primary text-white">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Loved by businesses &amp; creators</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight">
            Trusted by local shops, D2C brands and everyday creators.
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
              <blockquote className="mt-5 text-base leading-relaxed text-white/90">"{t.q}"</blockquote>
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
  { name: "Starter", price: "Free", per: "forever", features: ["For solo founders, home businesses &amp; new creators", "Up to 2 active campaigns", "Verified creator search", "Escrow-secured payments", "Email support"], cta: "Start free", testId: "pricing-starter", highlight: false },
  { name: "Growth", price: "Rs 1,499", per: "/ month", features: ["For cafes, salons, gyms, clothing stores &amp; D2C brands", "Unlimited campaigns", "Priority creator matchmaking", "Multi-city &amp; multi-platform reach", "Campaign analytics &amp; ROI tracking", "Priority support"], cta: "Start 14-day free trial", testId: "pricing-growth", highlight: true },
  { name: "Business+", price: "Custom", per: "billed annually", features: ["For coaching institutes, retail chains &amp; growing D2C brands", "Dedicated account manager", "Custom contracts &amp; campaign briefs", "Bulk creator onboarding", "Quarterly performance reviews", "24/7 white-glove support"], cta: "Talk to us", testId: "pricing-enterprise", highlight: false },
];

function Pricing() {
  return (
    <section id="pricing" className="section-y">
      <div className="container-luxe">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Pricing</p>
          <h2 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Affordable plans for every kind of business.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground">Flat 10% platform fee on campaign payouts - no agency markups, no hidden charges. Creators always sign up free.</p>
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
                    <Check className="h-4 w-4 mt-0.5 text-secondary shrink-0" /> <span dangerouslySetInnerHTML={{ __html: f }} />
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
  { q: "Who is BrandKrt for?", a: "Any business that wants reach without the agency cost - restaurants, cafes, salons, gyms, coaching institutes, clothing stores, local shops, D2C brands and home businesses - and any creator: nano, micro, Instagram, YouTube or Facebook." },
  { q: "How affordable is influencer marketing on BrandKrt?", a: "You can run your first verified nano-creator campaign for as little as Rs 999. There are no signup fees and no monthly minimums on the free plan - only a 10% platform fee on successful campaigns." },
  { q: "How do you verify creators and businesses?", a: "Every creator clears ID verification plus social handle ownership check. Every business is identity-verified before they can run a campaign. Verified profiles get a trust badge." },
  { q: "How are payments handled?", a: "Brands fund the campaign upfront. The amount sits safely in escrow and is released to the creator only after the deliverables (post, reel, video) are live and approved. Creators are never ghosted on payment." },
  { q: "What platforms do you support?", a: "Right now Instagram, YouTube and Facebook - including Reels, Shorts, posts, stories and long-form videos. You can match with nano creators (1K-10K), micro creators (10K-100K) and established content creators all in one place." },
  { q: "Can I run a campaign for my local shop or home business?", a: "Absolutely - that's exactly who BrandKrt is built for. Filter creators by your city and niche, send a brief, and your store can be featured by real local creators within days." },
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
      toast.success(data.message || "Thanks - we'll be in touch.");
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
            Tell us about your business or your creator journey.
          </h2>
          <p className="mt-6 text-lg text-muted-foreground">Whether you&apos;re a cafe owner planning your first campaign, a salon launching a new service, a D2C brand scaling up, or a creator who wants to start earning - we&apos;re here. We typically reply within 24 hours.</p>
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
