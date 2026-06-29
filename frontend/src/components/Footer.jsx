import React from "react";
import { Link } from "react-router-dom";
import { Instagram, Twitter, Linkedin, Youtube, Mail } from "lucide-react";
import { BRAND } from "@/lib/brand";
import Logo from "./Logo";

const groups = [
  {
    title: "Product",
    links: [
      { to: "/#features", label: "Features" },
      { to: "/#how-it-works", label: "How it Works" },
      { to: "/#pricing", label: "Pricing" },
      { to: "/#faq", label: "FAQ" },
    ],
  },
  {
    title: "Company",
    links: [
      { to: "/about", label: "About" },
      { to: "/contact", label: "Contact" },
      { to: "/login", label: "Login" },
      { to: "/register", label: "Register" },
    ],
  },
  {
    title: "Legal",
    links: [
      { to: "/privacy", label: "Privacy Policy" },
      { to: "/terms", label: "Terms" },
      { to: "/refund", label: "Refund Policy" },
    ],
  },
];

export default function Footer() {
  return (
    <footer data-testid="site-footer" className="bg-primary text-white">
      <div className="container-luxe py-20">
        <div className="grid gap-12 lg:grid-cols-5">
          <div className="lg:col-span-2 space-y-6">
            <Logo textClassName="text-white" />
            <p className="text-sm text-white/70 max-w-sm leading-relaxed">
              {BRAND.name} is the premium influencer marketing marketplace built for serious brands and creators. Verification, contracts, payments and analytics — handled.
            </p>
            <div className="flex items-center gap-3 text-white/80">
              <Mail className="h-4 w-4" />
              <a href={`mailto:${BRAND.contactEmail}`} data-testid="footer-email" className="text-sm hover:text-secondary">
                {BRAND.contactEmail}
              </a>
            </div>
            <div className="flex items-center gap-3">
              <a href="https://instagram.com" aria-label="Instagram" data-testid="social-instagram" className="h-9 w-9 rounded-full border border-white/20 flex items-center justify-center hover:border-secondary hover:text-secondary transition-colors">
                <Instagram className="h-4 w-4" />
              </a>
              <a href="https://twitter.com" aria-label="Twitter" data-testid="social-twitter" className="h-9 w-9 rounded-full border border-white/20 flex items-center justify-center hover:border-secondary hover:text-secondary transition-colors">
                <Twitter className="h-4 w-4" />
              </a>
              <a href="https://linkedin.com" aria-label="LinkedIn" data-testid="social-linkedin" className="h-9 w-9 rounded-full border border-white/20 flex items-center justify-center hover:border-secondary hover:text-secondary transition-colors">
                <Linkedin className="h-4 w-4" />
              </a>
              <a href="https://youtube.com" aria-label="YouTube" data-testid="social-youtube" className="h-9 w-9 rounded-full border border-white/20 flex items-center justify-center hover:border-secondary hover:text-secondary transition-colors">
                <Youtube className="h-4 w-4" />
              </a>
            </div>
          </div>

          {groups.map((g) => (
            <div key={g.title}>
              <h4 className="text-xs uppercase tracking-[0.2em] text-secondary mb-5">{g.title}</h4>
              <ul className="space-y-3">
                {g.links.map((l) => (
                  <li key={l.to}>
                    <Link to={l.to} className="text-sm text-white/70 hover:text-white transition-colors" data-testid={`footer-link-${l.label.toLowerCase().replace(/\s+/g, '-')}`}>
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-16 pt-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-xs text-white/50" data-testid="footer-copyright">© {new Date().getFullYear()} {BRAND.name}. All rights reserved. {BRAND.domain}</p>
          <p className="text-xs text-white/50">Crafted with intention — for brands that lead and creators that move culture.</p>
        </div>
      </div>
    </footer>
  );
}
