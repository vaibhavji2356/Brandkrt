import React from "react";
import SiteLayout from "@/components/SiteLayout";
import { Link } from "react-router-dom";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@/components/ui/accordion";
import { Mail, BookOpen, Shield, FileText, RefreshCw, Users } from "lucide-react";

const TOPICS = [
  { icon: BookOpen, title: "Getting Started", desc: "Set up your account and run your first campaign.", to: "/#how-it-works" },
  { icon: Users, title: "For Creators", desc: "Build a profile, attract brands, and get paid securely.", to: "/register?role=influencer" },
  { icon: Shield, title: "Verification", desc: "How KYC, social-handle verification and trust badges work.", to: "/contact" },
  { icon: RefreshCw, title: "Refunds & Disputes", desc: "Our refund policy and how disputes are resolved.", to: "/refund" },
  { icon: FileText, title: "Legal", desc: "Terms, Privacy and Community Guidelines.", to: "/terms" },
  { icon: Mail, title: "Talk to a human", desc: "Reach support@brandkrt.com — we reply within 24 hours.", to: "/contact" },
];

const FAQS = [
  { q: "How do I become a verified creator?", a: "Sign up as a creator, complete your profile, submit ID and social-handle verification. Our team reviews within 48 hours." },
  { q: "How do brands pay creators?", a: "Brands fund the deal into BrandKrt escrow. Once deliverables are approved, the funds are released minus a flat 8% platform fee." },
  { q: "Can I cancel a campaign?", a: "Yes, until the offer is accepted. After acceptance, cancellations follow the dispute flow described in our Refund Policy." },
  { q: "Do you support international payouts?", a: "Yes — 40+ countries with local payout methods. Multi-currency support is available on Growth and Enterprise plans." },
];

export default function HelpCenter() {
  return (
    <SiteLayout>
      <section className="section-y" data-testid="help-center-page">
        <div className="container-luxe max-w-5xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Help Center</p>
          <h1 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">
            Answers, guides and support — all in one place.
          </h1>
          <p className="mt-5 text-lg text-muted-foreground max-w-2xl">Search popular topics or browse by category. Can't find what you need? <Link to="/contact" className="text-secondary font-semibold hover:underline">Email our team</Link>.</p>

          <div className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {TOPICS.map((t, i) => (
              <Link key={t.title} to={t.to} className="rounded-2xl border border-border bg-card p-6 hover:-translate-y-1 hover:shadow-luxe-sm transition-all" data-testid={`help-topic-${i}`}>
                <div className="h-10 w-10 rounded-xl bg-accent text-secondary flex items-center justify-center"><t.icon className="h-5 w-5" /></div>
                <h3 className="mt-5 text-base font-medium text-primary dark:text-white">{t.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{t.desc}</p>
              </Link>
            ))}
          </div>

          <div className="mt-20">
            <h2 className="text-2xl font-display font-light text-primary dark:text-white">Frequently asked</h2>
            <Accordion type="single" collapsible className="mt-6 space-y-3">
              {FAQS.map((f, i) => (
                <AccordionItem key={i} value={`h-${i}`} className="rounded-2xl border border-border bg-card px-6" data-testid={`help-faq-${i}`}>
                  <AccordionTrigger className="text-left text-base font-medium text-primary dark:text-white">{f.q}</AccordionTrigger>
                  <AccordionContent className="text-sm text-muted-foreground leading-relaxed">{f.a}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </div>
      </section>
    </SiteLayout>
  );
}
