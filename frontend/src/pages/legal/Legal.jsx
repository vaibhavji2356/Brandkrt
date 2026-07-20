import React from "react";
import SiteLayout from "@/components/SiteLayout";

function LegalShell({ title, lastUpdated, children }) {
  return (
    <SiteLayout>
      <section className="section-y">
        <div className="container-luxe max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Legal</p>
          <h1 className="mt-4 text-4xl sm:text-5xl font-light tracking-tight text-primary dark:text-white">{title}</h1>
          <p className="mt-2 text-sm text-muted-foreground">Last updated: {lastUpdated}</p>
          <div className="mt-10 space-y-6 text-foreground/80 leading-relaxed text-sm">{children}</div>
        </div>
      </section>
    </SiteLayout>
  );
}

export function Privacy() {
  return (
    <LegalShell title="Privacy Policy" lastUpdated="February 2026">
      <p>BrandKrt ("we", "us") respects your privacy. This policy describes how we collect, use and share information when you use brandkrt.com and the BrandKrt platform.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Information we collect</h3>
      <p>Account details (name, email, role), KYC documents for verification, payment metadata, and platform usage data needed to deliver the service.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">How we use information</h3>
      <p>To deliver campaigns, verify identity, process payments, prevent fraud, and improve the platform. We do not sell personal data.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Your rights</h3>
      <p>You may access, correct, export or delete your data at any time from Settings or by contacting support@brandkrt.com.</p>
    </LegalShell>
  );
}

export function Terms() {
  return (
    <LegalShell title="Terms of Service" lastUpdated="February 2026">
      <p>By creating a BrandKrt account you agree to these terms. BrandKrt provides a marketplace; campaign contracts are formed between brands and creators, with BrandKrt acting as escrow and platform.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Account</h3>
      <p>You must be 18+ and provide accurate information. You're responsible for keeping credentials secure.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Fees</h3>
      <p>BrandKrt charges a flat 10% platform fee on processed transactions plus applicable taxes. Subscription plans are billed monthly or annually.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Prohibited use</h3>
      <p>No misrepresentation, no automated engagement, no off-platform circumvention of payments. Violations may result in suspension.</p>
    </LegalShell>
  );
}

export function Refund() {
  return (
    <LegalShell title="Refund Policy" lastUpdated="February 2026">
      <p>BrandKrt holds campaign funds in escrow until deliverables are approved. Refunds and dispute resolution follow the timeline below.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Campaign funds</h3>
      <p>If a creator fails to deliver agreed milestones, the brand may dispute within 14 days of deadline. Approved disputes result in refund minus processing fees.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Subscriptions</h3>
      <p>Monthly subscriptions are non-refundable but can be cancelled anytime. Annual plans are refundable pro-rata in the first 30 days.</p>
      <h3 className="text-lg font-medium text-primary dark:text-white">Contact</h3>
      <p>For any refund queries reach out to support@brandkrt.com — our team responds within 24 hours.</p>
    </LegalShell>
  );
}
