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
