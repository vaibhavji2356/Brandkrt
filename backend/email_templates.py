"""BrandKrt email templates - reusable HTML for transactional emails.

EmailService composes a template with brand-styled HTML and plain text fallback.
Pluggable provider with SMTP for production and console fallback in development.
"""
from __future__ import annotations

BASE_STYLES = """
  body{margin:0;background:#F8FAFC;font-family:'Manrope',Helvetica,Arial,sans-serif;color:#1F2937}
  .wrap{max-width:560px;margin:0 auto;padding:32px 16px}
  .card{background:#fff;border:1px solid #E5E7EB;border-radius:16px;padding:32px}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:24px}
  .brand b{color:#0A1F44;font-weight:600;font-size:18px;letter-spacing:-.01em}
  .brand .gold{color:#D4AF37}
  h1{font-family:Outfit,Helvetica,Arial,sans-serif;font-weight:300;color:#0A1F44;font-size:24px;margin:0 0 12px}
  p{line-height:1.6;color:#374151;margin:0 0 12px}
  .btn{display:inline-block;background:#0A1F44;color:#fff!important;text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:600;margin-top:16px}
  .muted{color:#6B7280;font-size:12px;margin-top:24px}
  .hr{height:1px;background:#E5E7EB;margin:24px 0}
"""


def _shell(title: str, body_html: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>{BASE_STYLES}</style></head><body><div class="wrap"><div class="card">
<div class="brand"><b>Brand<span class="gold">krt</span></b></div>
{body_html}
<div class="hr"></div>
<p class="muted">BrandKrt · Connecting Brands With Creators · brandkrt.com<br/>
You're receiving this because you have an account at BrandKrt. Reach support@brandkrt.com anytime.</p>
</div></div></body></html>"""


def welcome(name: str) -> dict:
    html = _shell("Welcome to BrandKrt",
        f"<h1>Welcome, {name}.</h1><p>You're now part of BrandKrt — the premium marketplace where ambitious brands meet extraordinary creators.</p><p>Complete your profile to unlock campaigns, verification badges and faster payouts.</p><a class='btn' href='https://brandkrt.com/profile'>Complete profile</a>")
    text = f"Welcome to BrandKrt, {name}. Complete your profile: https://brandkrt.com/profile"
    return {"subject": "Welcome to BrandKrt", "html": html, "text": text}


def verify_email(link: str) -> dict:
    html = _shell("Verify your email",
        f"<h1>Verify your email</h1><p>Confirm your email to activate your BrandKrt account. This link expires in 24 hours.</p><a class='btn' href='{link}'>Verify email</a><p class='muted'>Or paste this link into your browser: {link}</p>")
    return {"subject": "Verify your BrandKrt email", "html": html, "text": f"Verify your email: {link}"}


def reset_password(link: str) -> dict:
    html = _shell("Reset your password",
        f"<h1>Reset your password</h1><p>We received a request to reset your BrandKrt password. This link expires in 1 hour.</p><a class='btn' href='{link}'>Reset password</a><p class='muted'>If you didn't request this, you can safely ignore this email.</p>")
    return {"subject": "Reset your BrandKrt password", "html": html, "text": f"Reset link: {link}"}


def verification_approved(name: str) -> dict:
    html = _shell("Verification approved",
        f"<h1>You're verified, {name}.</h1><p>Your BrandKrt verification has been approved. You can now access premium campaigns and receive a verified badge on your profile.</p><a class='btn' href='https://brandkrt.com/profile'>Go to profile</a>")
    return {"subject": "Your BrandKrt verification is approved", "html": html, "text": "Your verification is approved."}


def verification_rejected(reason: str) -> dict:
    html = _shell("Verification needs attention",
        f"<h1>Verification update</h1><p>We weren't able to verify your account. Reason: <em>{reason or 'Please review and resubmit.'}</em></p><p>You can submit updated documents from your profile.</p><a class='btn' href='https://brandkrt.com/profile'>Resubmit</a>")
    return {"subject": "Action required: BrandKrt verification", "html": html, "text": f"Verification rejected: {reason}"}


def campaign_invitation(brand: str, title: str, link: str) -> dict:
    html = _shell("Campaign invitation",
        f"<h1>New campaign offer</h1><p><b>{brand}</b> invited you to collaborate on <b>{title}</b>.</p><a class='btn' href='{link}'>Review offer</a>")
    return {"subject": f"New campaign offer from {brand}", "html": html, "text": f"Review offer: {link}"}


def campaign_accepted(brand: str, link: str) -> dict:
    html = _shell("Offer accepted",
        f"<h1>Offer accepted</h1><p>Your offer with <b>{brand}</b> has been accepted. Track deliverables and milestones inside BrandKrt.</p><a class='btn' href='{link}'>Open deal</a>")
    return {"subject": "Your BrandKrt offer was accepted", "html": html, "text": f"Open deal: {link}"}


def campaign_completed(link: str) -> dict:
    html = _shell("Campaign completed",
        f"<h1>Campaign completed</h1><p>The deliverables have been approved. Final analytics and invoice are now available.</p><a class='btn' href='{link}'>View campaign</a>")
    return {"subject": "Your BrandKrt campaign is complete", "html": html, "text": f"View campaign: {link}"}


def payment_released(amount: float, txid: str) -> dict:
    html = _shell("Payment released",
        f"<h1>You've been paid</h1><p>${amount:,.2f} has been released to your account. Transaction id: <code>{txid}</code></p><a class='btn' href='https://brandkrt.com/profile'>View earnings</a>")
    return {"subject": "Payment released to your BrandKrt account", "html": html, "text": f"Paid ${amount} (tx {txid})."}


def deadline_reminder(title: str, when: str, link: str) -> dict:
    html = _shell("Deadline reminder",
        f"<h1>Reminder: {title}</h1><p>Your deliverable is due on <b>{when}</b>. Stay on track to keep funds released on time.</p><a class='btn' href='{link}'>Open deal</a>")
    return {"subject": f"Reminder: {title} due soon", "html": html, "text": f"Reminder due {when}: {link}"}
