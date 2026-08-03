import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight, BadgeCheck, BarChart3, Building2, CreditCard, FileSignature,
  Instagram, Mail, MessageCircle, Play, Search, Send, ShieldCheck,
  Megaphone, PlayCircle, SearchX, Sparkles, Star, UserRound, Youtube,
} from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";

const rise = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55 } },
};

const EXPLAINER_SCENES = [
  {
    icon: UserRound,
    label: "Creator ki problem",
    time: "0–5 sec",
    title: "Talent hai, par sahi brand aur payment ka bharosa nahi.",
    detail: "Random DMs, unclear brief aur delayed payment creator ka time waste karte hain.",
    chips: ["Unclear brief", "Late payment", "Random DMs"],
    tone: "bg-violet-500/15 text-violet-300",
  },
  {
    icon: SearchX,
    label: "Brand ki problem",
    time: "5–10 sec",
    title: "Campaign ke liye genuine local creator kaise mile?",
    detail: "Fake profiles, unclear pricing aur scattered conversations se selection mushkil hota hai.",
    chips: ["Fake profiles", "No pricing", "Slow search"],
    tone: "bg-rose-500/15 text-rose-300",
  },
  {
    icon: BadgeCheck,
    label: "BrandKrt solution",
    time: "10–15 sec",
    title: "Match se payment tak—sab ek jagah.",
    detail: "Verified match · clear brief · protected payment",
    chips: ["Verified", "Clear brief", "Safe payment"],
    tone: "bg-emerald-500/15 text-emerald-300",
  },
];

const EXPLAINER_SCENE_MS = 5000;

function HindiExplainer() {
  const [scene, setScene] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setScene((current) => (current + 1) % EXPLAINER_SCENES.length), EXPLAINER_SCENE_MS);
    return () => window.clearInterval(timer);
  }, [scene]);
  const current = EXPLAINER_SCENES[scene];
  return (
    <div className="relative overflow-hidden rounded-[2rem] border border-white/15 bg-[#102a55] p-5 shadow-2xl" aria-label="BrandKrt Hindi visual explainer">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-[#f0c94b]"><PlayCircle className="h-4 w-4" /> Hindi visual story</div>
        <div className="flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-[9px] text-white/65"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />15 sec · Auto playing</div>
      </div>
      <div className="relative mt-5 min-h-[255px] overflow-hidden rounded-2xl border border-white/10 bg-[#071a3d] p-6">
        <div className="absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_1px_1px,white_1px,transparent_0)] [background-size:22px_22px]" />
        <motion.div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-[#e0b52f]/15 blur-3xl" animate={{ x: [0, -35, 0], y: [0, 30, 0], scale: [1, 1.2, 1] }} transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }} />
        <AnimatePresence mode="wait">
          <motion.div key={scene} initial={{ opacity: 0, x: 28 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -28 }} transition={{ duration: 0.45 }} className="relative flex min-h-[205px] flex-col justify-between">
            <motion.div className={`grid h-14 w-14 place-items-center rounded-2xl ${current.tone}`} animate={{ y: [0, -5, 0], rotate: [0, 2, 0] }} transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}><current.icon className="h-7 w-7" /></motion.div>
            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#f0c94b]">{current.label}</p>
                <span className="shrink-0 text-[10px] font-semibold text-white/45">{current.time}</span>
              </div>
              <h3 className="mt-2 max-w-md text-2xl font-medium leading-tight text-white">{current.title}</h3>
              <p className="mt-3 text-sm text-white/55">{current.detail}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {current.chips.map((chip, index) => (
                  <motion.span key={chip} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + index * 0.12 }} className="rounded-full border border-white/10 bg-white/[0.07] px-2.5 py-1 text-[9px] font-semibold text-white/70">{chip}</motion.span>
                ))}
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {EXPLAINER_SCENES.map((item, index) => (
          <button key={item.label} type="button" onClick={() => setScene(index)} aria-label={`Show ${item.label}`} className="group py-1">
            <span className="block h-1 overflow-hidden rounded-full bg-white/15">
              {index === scene && (
                <motion.span key={`${scene}-progress`} className="block h-full origin-left rounded-full bg-[#f0c94b]" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: EXPLAINER_SCENE_MS / 1000, ease: "linear" }} />
              )}
            </span>
            <span className={`mt-2 block truncate text-[9px] ${index === scene ? "text-white" : "text-white/40"}`}>{index + 1}. {item.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function HeroVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[560px]" aria-label="Creator campaign matching preview">
      <div className="absolute inset-8 rounded-[2rem] bg-[#e0b52f]/20 blur-3xl" />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7, delay: 0.2 }}
        className="relative"
      >
        <HindiExplainer />
      </motion.div>
    </div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden bg-[#071a3d] py-20 text-white dark:bg-[#050b18] md:py-28">
      <div className="absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_1px_1px,white_1px,transparent_0)] [background-size:32px_32px]" />
      <div className="container-luxe relative grid items-center gap-16 lg:grid-cols-[0.95fr_1.05fr]">
        <motion.div initial="hidden" animate="show" variants={rise}>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs text-white/80">
            <Sparkles className="h-3.5 w-3.5 text-[#f0c94b]" /> Brands meet creators
          </div>
          <h1 className="mt-7 max-w-2xl text-5xl font-light leading-[0.98] tracking-tighter sm:text-6xl lg:text-7xl" data-testid="hero-headline">
            Local reach.<br /><span className="gold-text font-semibold">Real creators.</span>
          </h1>
          <p className="mt-6 max-w-lg text-lg text-white/65" data-testid="hero-subtitle">
            Discover, collaborate and pay—without scattered DMs.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link to="/register?role=brand" data-testid="hero-cta-brand" className="inline-flex items-center justify-center gap-2 rounded-full bg-[#e0b52f] px-7 py-3.5 text-sm font-bold text-[#071a3d] shadow-[0_10px_35px_rgba(224,181,47,0.22)] transition-all hover:scale-[1.03] hover:bg-[#f0c94b] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
              Find creators <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/register?role=influencer" data-testid="hero-cta-influencer" className="inline-flex items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-7 py-3.5 text-sm font-semibold text-white hover:bg-white/15">
              Join as creator <Play className="h-4 w-4" />
            </Link>
          </div>
          <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur-sm" aria-label="BrandKrt campaign flow">
            <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-2 text-center">
              {[
                { icon: Building2, label: "Business" },
                { icon: UserRound, label: "Right creator" },
                { icon: Megaphone, label: "Campaign live" },
              ].map((item, index) => (
                <React.Fragment key={item.label}>
                  <motion.div whileHover={{ y: -3 }} className="flex min-w-0 flex-col items-center gap-2 rounded-xl bg-white/[0.06] px-2 py-3">
                    <item.icon className="h-5 w-5 text-[#f0c94b]" />
                    <span className="text-[10px] font-semibold text-white/80 sm:text-xs">{item.label}</span>
                  </motion.div>
                  {index < 2 && <motion.div animate={{ x: [0, 4, 0] }} transition={{ duration: 1.5, repeat: Infinity, delay: index * 0.3 }}><ArrowRight className="h-4 w-4 text-[#f0c94b]" /></motion.div>}
                </React.Fragment>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-center gap-5 text-[10px] text-white/50">
              <span className="flex items-center gap-1.5"><BadgeCheck className="h-3.5 w-3.5 text-[#f0c94b]" /> Verified</span>
              <span className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-[#f0c94b]" /> Protected</span>
            </div>
          </div>
        </motion.div>
        <HeroVisual />
      </div>
    </section>
  );
}

const JOURNEY = [
  { icon: Search, label: "Discover", detail: "Niche + city" },
  { icon: MessageCircle, label: "Discuss", detail: "One clear brief" },
  { icon: FileSignature, label: "Agree", detail: "Terms together" },
  { icon: CreditCard, label: "Protect", detail: "Escrow flow" },
  { icon: BarChart3, label: "Track", detail: "One dashboard" },
];

function VisualJourney() {
  return (
    <section id="how-it-works" className="section-y scroll-mt-24 overflow-hidden">
      <div className="container-luxe">
        <div className="text-center">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#c69718] dark:text-[#f0c94b]">How it works</p>
          <h2 className="mt-4 text-4xl font-light tracking-tight text-primary dark:text-white sm:text-5xl">One smooth campaign flow.</h2>
        </div>
        <div className="relative mt-16 grid gap-4 md:grid-cols-5">
          <div className="absolute left-[10%] right-[10%] top-12 hidden h-px bg-gradient-to-r from-transparent via-secondary to-transparent md:block" />
          {JOURNEY.map((item, i) => (
            <motion.div key={item.label} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} className="relative text-center">
              <motion.div whileHover={{ scale: 1.08, rotate: 2 }} className="relative z-10 mx-auto grid h-24 w-24 place-items-center rounded-[2rem] border border-border bg-card shadow-lg">
                <item.icon className="h-8 w-8 text-[#c69718] dark:text-[#f0c94b]" />
              </motion.div>
              <h3 className="mt-5 text-base font-semibold text-primary dark:text-white">{item.label}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{item.detail}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BentoBenefits() {
  return (
    <section id="features" className="section-y scroll-mt-24 bg-accent dark:bg-[#08152d]">
      <div className="container-luxe">
        <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#c69718] dark:text-[#f0c94b]">Built for clarity</p><h2 className="mt-4 text-4xl font-light tracking-tight text-primary dark:text-white sm:text-5xl">See the work. Skip the noise.</h2></div>
          <p className="max-w-sm text-sm text-muted-foreground">Everything important stays visible—from match to payout.</p>
        </div>
        <div className="mt-14 grid gap-5 md:grid-cols-6 md:grid-rows-2">
          <motion.div whileHover={{ y: -5 }} className="relative overflow-hidden rounded-[2rem] bg-[#071a3d] p-8 text-white dark:bg-[#0d2246] md:col-span-3 md:row-span-2">
            <div className="absolute -right-12 -top-12 h-52 w-52 rounded-full bg-[#e0b52f]/20 blur-2xl" />
            <BadgeCheck className="h-9 w-9 text-[#f0c94b]" />
            <h3 className="mt-12 text-3xl font-light">Creator discovery,<br />made visual.</h3>
            <div className="mt-8 space-y-3">
              {["Food · Pune", "Beauty · Jaipur", "Fitness · Delhi"].map((row, i) => <motion.div key={row} initial={{ x: 20, opacity: 0 }} whileInView={{ x: 0, opacity: 1 }} transition={{ delay: i * 0.12 }} viewport={{ once: true }} className="flex items-center justify-between rounded-xl bg-white/10 px-4 py-3 text-xs"><span>{row}</span><ArrowRight className="h-3.5 w-3.5 text-[#f0c94b]" /></motion.div>)}
            </div>
          </motion.div>
          <motion.div whileHover={{ y: -5 }} className="rounded-[2rem] border border-border bg-card p-7 md:col-span-3">
            <div className="flex items-center justify-between"><ShieldCheck className="h-8 w-8 text-emerald-600" /><span className="rounded-full bg-emerald-50 px-3 py-1 text-[10px] font-bold text-emerald-700">PROTECTED</span></div>
            <h3 className="mt-8 text-2xl font-medium">Clear payment stages</h3>
            <div className="mt-5 flex items-center gap-2">{["Funded", "Approved", "Released"].map((x, i) => <React.Fragment key={x}><span className="rounded-full bg-accent px-3 py-2 text-[10px]">{x}</span>{i < 2 && <div className="h-px flex-1 bg-[#e0b52f]/50" />}</React.Fragment>)}</div>
          </motion.div>
          <motion.div whileHover={{ y: -5 }} className="rounded-[2rem] border border-border bg-card p-7 md:col-span-2">
            <MessageCircle className="h-7 w-7 text-[#c69718] dark:text-[#f0c94b]" /><h3 className="mt-7 text-xl font-medium">Chat in context</h3><p className="mt-2 text-xs text-muted-foreground">Briefs and updates stay together.</p>
          </motion.div>
          <motion.div whileHover={{ y: -5 }} className="rounded-[2rem] border border-border bg-card p-7 md:col-span-1">
            <div className="flex gap-2"><Instagram className="h-6 w-6 text-pink-500" /><Youtube className="h-6 w-6 text-red-500" /></div><p className="mt-8 text-sm font-semibold">Multi-platform</p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

const REVIEWS = [
  { name: "Priya Sharma", text: "Campaign manage karna simple laga." },
  { name: "Rohit Verma", text: "Creator search clear aur easy hai." },
  { name: "Aditi Mehta", text: "Brief aur payment ek jagah milte hain." },
];

function Reviews() {
  return (
    <section className="section-y bg-[#071a3d] text-white dark:bg-[#050b18]">
      <div className="container-luxe">
        <div className="flex items-end justify-between gap-6"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#f0c94b]">People</p><h2 className="mt-4 text-4xl font-light sm:text-5xl">Simple words. Indian voices.</h2></div><UserRound className="hidden h-16 w-16 text-white/10 sm:block" /></div>
        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {REVIEWS.map((review, i) => (
            <motion.figure key={review.name} initial={{ opacity: 0, scale: 0.96 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} className="rounded-[2rem] border border-white/10 bg-white/5 p-7">
              <div className="flex gap-1 text-[#f0c94b]">{Array.from({ length: 5 }).map((_, x) => <Star key={x} className="h-3.5 w-3.5 fill-current" />)}</div>
              <blockquote className="mt-8 text-xl font-light leading-snug">“{review.text}”</blockquote>
              <figcaption className="mt-8 flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-full bg-[#e0b52f] font-bold text-[#071a3d]">{review.name[0]}</div><span className="text-sm font-semibold">{review.name}</span></figcaption>
            </motion.figure>
          ))}
        </div>
      </div>
    </section>
  );
}

const FAQS = [
  { q: "Brand ke liye kya milega?", a: "Creator discovery, briefs, collaboration tracking and payment workflow." },
  { q: "Creator ke liye kya milega?", a: "Relevant opportunities, clear deliverables and a structured payout flow." },
  { q: "Kaunse platforms supported hain?", a: "Instagram, YouTube and other campaign formats shown inside the platform." },
];

function QuickAnswers() {
  return (
    <section id="faq" className="section-y scroll-mt-24">
      <div className="container-luxe grid gap-12 lg:grid-cols-[0.75fr_1.25fr]">
        <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#c69718] dark:text-[#f0c94b]">Quick answers</p><h2 className="mt-4 text-4xl font-light tracking-tight text-primary dark:text-white">No long manual.</h2><p className="mt-4 text-sm text-muted-foreground">Bas jo zaroori hai.</p></div>
        <Accordion type="single" collapsible className="space-y-3">{FAQS.map((item, i) => <AccordionItem key={item.q} value={`faq-${i}`} className="rounded-2xl border border-border bg-card px-6"><AccordionTrigger className="text-left">{item.q}</AccordionTrigger><AccordionContent className="text-sm text-muted-foreground">{item.a}</AccordionContent></AccordionItem>)}</Accordion>
      </div>
    </section>
  );
}

function ContactSection() {
  const [form, setForm] = useState({ name: "", email: "", subject: "", message: "" });
  const [submitting, setSubmitting] = useState(false);
  const submit = async (event) => {
    event.preventDefault(); setSubmitting(true);
    try { const { data } = await api.post("/contact", form); toast.success(data.message || "Message sent."); setForm({ name: "", email: "", subject: "", message: "" }); }
    catch (error) { toast.error(formatApiError(error)); }
    finally { setSubmitting(false); }
  };
  return (
    <section id="contact" className="section-y scroll-mt-24 bg-accent dark:bg-[#08152d]">
      <div className="container-luxe overflow-hidden rounded-[2.5rem] bg-[#071a3d] text-white dark:bg-[#050b18]">
        <div className="grid lg:grid-cols-[0.8fr_1.2fr]">
          <div className="relative p-8 md:p-12"><div className="absolute -left-20 -top-20 h-64 w-64 rounded-full bg-[#e0b52f]/20 blur-3xl" /><Mail className="relative h-9 w-9 text-[#f0c94b]" /><h2 className="relative mt-12 text-4xl font-light">Let’s build your<br />next collaboration.</h2><a href="mailto:support@brandkrt.com" className="relative mt-8 inline-flex items-center gap-2 text-sm text-white/65 hover:text-[#f0c94b]">support@brandkrt.com <ArrowRight className="h-4 w-4" /></a></div>
          <form onSubmit={submit} className="space-y-4 bg-white p-8 text-foreground dark:bg-background md:p-12" data-testid="contact-form">
            <div className="grid gap-4 sm:grid-cols-2"><Input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /><Input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></div>
            <Input placeholder="What do you need?" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required />
            <Textarea rows={4} placeholder="Tell us briefly…" value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} required />
            <button type="submit" disabled={submitting} className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-[#e0b52f] px-6 py-3 text-sm font-semibold text-[#071a3d] disabled:opacity-60">{submitting ? "Sending…" : <>Send <Send className="h-4 w-4" /></>}</button>
          </form>
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  useEffect(() => {
    if (window.location.hash) {
      const element = document.getElementById(window.location.hash.slice(1));
      if (element) setTimeout(() => element.scrollIntoView({ behavior: "smooth" }), 100);
    }
  }, []);
  return <div data-testid="landing-page"><Hero /><VisualJourney /><BentoBenefits /><Reviews /><QuickAnswers /><ContactSection /></div>;
}
