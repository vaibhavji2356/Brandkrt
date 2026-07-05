"""Pluggable payment provider abstraction.

PAYMENT_PROVIDER=stub     default, no external payment call
PAYMENT_PROVIDER=stripe   requires STRIPE_SECRET_KEY
PAYMENT_PROVIDER=razorpay requires RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional

import requests

logger = logging.getLogger("brandkrt.payments")


class PaymentResult(dict):
    pass


class PaymentProvider:
    name = "base"

    def create_escrow(self, *, amount: float, deal_id: str, currency: str = "INR") -> PaymentResult:
        raise NotImplementedError

    def release(self, *, transaction_id: str) -> PaymentResult:
        raise NotImplementedError

    def verify(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        raise NotImplementedError

    def create_payout(
        self,
        *,
        amount: float,
        method: str,
        details: dict,
        contact: dict,
        reference_id: str,
    ) -> PaymentResult:
        raise NotImplementedError


class StubProvider(PaymentProvider):
    name = "stub"

    def create_escrow(self, *, amount: float, deal_id: str, currency: str = "INR") -> PaymentResult:
        return PaymentResult(
            transaction_id=secrets.token_hex(8).upper(),
            client_secret=None,
            provider=self.name,
            status="escrowed",
            currency=currency,
        )

    def release(self, *, transaction_id: str) -> PaymentResult:
        return PaymentResult(transaction_id=transaction_id, status="released", provider=self.name)

    def verify(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        return True

    def create_payout(
        self,
        *,
        amount: float,
        method: str,
        details: dict,
        contact: dict,
        reference_id: str,
    ) -> PaymentResult:
        return PaymentResult(
            payout_id=secrets.token_hex(8).upper(),
            status="processed",
            provider=self.name,
            amount=amount,
            method=method,
            reference_id=reference_id,
        )


class StripeProvider(PaymentProvider):
    name = "stripe"

    def __init__(self) -> None:
        key = os.environ.get("STRIPE_SECRET_KEY")
        if not key:
            raise RuntimeError("STRIPE_SECRET_KEY env var is required for the Stripe provider")
        try:
            import stripe  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"stripe SDK not installed: {e}")
        stripe.api_key = key
        self._stripe = stripe

    def create_escrow(self, *, amount: float, deal_id: str, currency: str = "INR") -> PaymentResult:
        units = int(round(float(amount) * 100))
        intent = self._stripe.PaymentIntent.create(
            amount=units,
            currency=currency.lower(),
            capture_method="manual",
            metadata={"deal_id": deal_id, "platform": "brandkrt"},
        )
        return PaymentResult(
            transaction_id=intent.id,
            client_secret=intent.client_secret,
            provider=self.name,
            status="escrowed",
            currency=currency,
        )

    def release(self, *, transaction_id: str) -> PaymentResult:
        captured = self._stripe.PaymentIntent.capture(transaction_id)
        return PaymentResult(
            transaction_id=transaction_id,
            status="released" if captured.status == "succeeded" else captured.status,
            provider=self.name,
        )

    def verify(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        return True


class RazorpayProvider(PaymentProvider):
    name = "razorpay"

    def __init__(self) -> None:
        self.key_id = _env("RAZORPAY_KEY_ID")
        self.key_secret = _env("RAZORPAY_KEY_SECRET")
        self.x_account_number = _env("RAZORPAYX_ACCOUNT_NUMBER")
        if not self.key_id or not self.key_secret:
            raise RuntimeError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET env vars are required")

    def create_escrow(self, *, amount: float, deal_id: str, currency: str = "INR") -> PaymentResult:
        units = int(round(float(amount) * 100))
        if units <= 0:
            raise RuntimeError("Razorpay amount must be greater than zero")
        receipt = f"bkrt_{deal_id[:12]}_{secrets.token_hex(4)}"[:40]
        response = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(self.key_id, self.key_secret),
            json={
                "amount": units,
                "currency": currency.upper(),
                "receipt": receipt,
                "payment_capture": 1,
                "notes": {"deal_id": deal_id, "platform": "brandkrt"},
            },
            timeout=20,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Razorpay order creation failed: {response.text[:300]}")
        order = response.json()
        return PaymentResult(
            transaction_id=order["id"],
            provider=self.name,
            status="pending",
            currency=order.get("currency", currency.upper()),
            amount_subunits=order.get("amount", units),
            receipt=order.get("receipt", receipt),
            key_id=self.key_id,
        )

    def release(self, *, transaction_id: str) -> PaymentResult:
        return PaymentResult(transaction_id=transaction_id, status="released", provider=self.name)

    def verify(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        payload = f"{order_id}|{payment_id}".encode("utf-8")
        digest = hmac.new(self.key_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature or "")

    def create_payout(
        self,
        *,
        amount: float,
        method: str,
        details: dict,
        contact: dict,
        reference_id: str,
    ) -> PaymentResult:
        if not self.x_account_number:
            raise RuntimeError("RAZORPAYX_ACCOUNT_NUMBER env var is required for creator payouts")
        units = int(round(float(amount) * 100))
        if units <= 0:
            raise RuntimeError("RazorpayX payout amount must be greater than zero")

        contact_response = requests.post(
            "https://api.razorpay.com/v1/contacts",
            auth=(self.key_id, self.key_secret),
            json={
                "name": contact.get("name") or "BrandKrt Creator",
                "email": contact.get("email"),
                "contact": contact.get("phone"),
                "type": "vendor",
                "reference_id": (contact.get("reference_id") or reference_id)[:40],
                "notes": {"platform": "brandkrt"},
            },
            timeout=20,
        )
        if contact_response.status_code >= 400:
            raise RuntimeError(f"RazorpayX contact creation failed: {contact_response.text[:300]}")
        contact_id = contact_response.json()["id"]

        method = (method or "").lower()
        if method == "upi":
            upi = (details.get("upi") or details.get("vpa") or "").strip()
            if not upi:
                raise RuntimeError("Creator UPI ID is required for UPI payout")
            fund_payload = {
                "contact_id": contact_id,
                "account_type": "vpa",
                "vpa": {"address": upi},
            }
            payout_mode = "UPI"
        else:
            account_name = (details.get("account_name") or details.get("account_holder_name") or contact.get("name") or "").strip()
            account_number = (details.get("account_number") or "").strip()
            ifsc = (details.get("ifsc") or details.get("ifsc_code") or "").strip().upper()
            if not account_name or not account_number or not ifsc:
                raise RuntimeError("Creator account holder name, account number and IFSC are required for bank payout")
            fund_payload = {
                "contact_id": contact_id,
                "account_type": "bank_account",
                "bank_account": {
                    "name": account_name,
                    "ifsc": ifsc,
                    "account_number": account_number,
                },
            }
            payout_mode = (_env("RAZORPAYX_BANK_PAYOUT_MODE") or "IMPS").upper()

        fund_response = requests.post(
            "https://api.razorpay.com/v1/fund_accounts",
            auth=(self.key_id, self.key_secret),
            json=fund_payload,
            timeout=20,
        )
        if fund_response.status_code >= 400:
            raise RuntimeError(f"RazorpayX fund account creation failed: {fund_response.text[:300]}")
        fund_account_id = fund_response.json()["id"]

        idem = f"bkrt_wd_{reference_id}_{secrets.token_hex(4)}"[:64]
        payout_response = requests.post(
            "https://api.razorpay.com/v1/payouts",
            auth=(self.key_id, self.key_secret),
            headers={"X-Payout-Idempotency": idem},
            json={
                "account_number": self.x_account_number,
                "fund_account_id": fund_account_id,
                "amount": units,
                "currency": "INR",
                "mode": payout_mode,
                "purpose": "payout",
                "queue_if_low_balance": True,
                "reference_id": reference_id[:40],
                "narration": "BrandKrt creator payout",
                "notes": {"platform": "brandkrt", "withdrawal_id": reference_id},
            },
            timeout=30,
        )
        if payout_response.status_code >= 400:
            raise RuntimeError(f"RazorpayX payout failed: {payout_response.text[:300]}")
        payout = payout_response.json()
        return PaymentResult(
            payout_id=payout.get("id"),
            status=payout.get("status", "processing"),
            provider=self.name,
            amount=amount,
            method=method,
            reference_id=reference_id,
            fund_account_id=fund_account_id,
            contact_id=contact_id,
            mode=payout_mode,
        )


_PROVIDER: Optional[PaymentProvider] = None


def _env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value or None


def get_provider() -> PaymentProvider:
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    name = (_env("PAYMENT_PROVIDER") or "stub").lower()
    try:
        if name == "stripe":
            _PROVIDER = StripeProvider()
        elif name == "razorpay":
            _PROVIDER = RazorpayProvider()
        else:
            _PROVIDER = StubProvider()
    except Exception as e:
        if name in {"stripe", "razorpay"}:
            raise
        logger.warning("Payment provider '%s' init failed (%s) - falling back to stub", name, e)
        _PROVIDER = StubProvider()
    logger.info("payments: provider=%s", _PROVIDER.name)
    return _PROVIDER
