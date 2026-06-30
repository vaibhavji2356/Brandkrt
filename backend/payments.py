"""Part 5 — Pluggable payment provider abstraction.

Existing endpoints (`/api/payments/escrow`, `/api/payments/{id}/release`) keep
working with the original DB-stub behaviour. The provider abstraction lets us
drop a real Stripe implementation later (controlled via PAYMENT_PROVIDER env
var) without touching any of the routes or the frontend.

PAYMENT_PROVIDER=stub  (default — current behaviour, no external call)
PAYMENT_PROVIDER=stripe (requires STRIPE_SECRET_KEY; charge-intent creation)

The live Stripe code path is intentionally minimal — it surfaces real
PaymentIntents but mirror-writes to the existing `payments` collection so the
rest of the platform (release, list, notifications, completion reports) keeps
working unchanged.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("brandkrt.payments")


class PaymentResult(dict):
    pass


class PaymentProvider:
    name = "base"

    def create_escrow(self, *, amount: float, deal_id: str, currency: str = "INR") -> PaymentResult:
        raise NotImplementedError

    def release(self, *, transaction_id: str) -> PaymentResult:
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
        # Stripe expects amount in the smallest currency unit
        units = int(round(float(amount) * 100))
        intent = self._stripe.PaymentIntent.create(
            amount=units,
            currency=currency.lower(),
            capture_method="manual",  # treat as escrow — capture (release) later
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


_PROVIDER: Optional[PaymentProvider] = None


def get_provider() -> PaymentProvider:
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    name = (os.environ.get("PAYMENT_PROVIDER") or "stub").lower()
    try:
        if name == "stripe":
            _PROVIDER = StripeProvider()
        else:
            _PROVIDER = StubProvider()
    except Exception as e:
        logger.warning("Payment provider '%s' init failed (%s) — falling back to stub", name, e)
        _PROVIDER = StubProvider()
    logger.info("payments: provider=%s", _PROVIDER.name)
    return _PROVIDER
