"""Explicit, one-request paid staging validation. Never imported by application startup."""

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from .config import AISettings
from .errors import AIServiceError
from .providers import build_provider
from .schemas import BrandDiscoveryRequest
from .service import BrandDiscoveryService
from .usage import UsageIdentity


class PaidCallConfirmationError(Exception):
    pass


def validate_paid_call_confirmation(*, allow_paid_call: bool, settings: AISettings) -> None:
    if not allow_paid_call:
        raise PaidCallConfirmationError("Pass --allow-paid-call to authorize exactly one paid request.")
    if not settings.openai_enabled:
        raise PaidCallConfirmationError("Paid staging call requires OpenAI mode with mock mode disabled.")


async def run_one_paid_call(settings: AISettings, *, result_limit: int) -> dict[str, object]:
    # Disable service retries so this command can make at most one HTTP provider request.
    one_call_settings = replace(
        settings,
        max_retries=0,
        max_output_tokens=min(settings.max_output_tokens, 1200),
    ).validate()
    service = BrandDiscoveryService(one_call_settings, build_provider(one_call_settings))
    result = await service.preview(
        BrandDiscoveryRequest(
            industry="sustainable consumer goods",
            location="India",
            campaign_objective="small creator-awareness pilot",
            result_limit=result_limit,
        ),
        usage_identity=UsageIdentity(user_id="manual-staging-script", ip_address="local-script"),
    )
    summary = service.last_call_summary
    return {
        "provider": result.provider,
        "model": summary.model if summary else one_call_settings.model,
        "results_returned": result.count,
        "duration_ms": summary.duration_ms if summary else 0,
        "usage": {
            "input_tokens": summary.actual_input_tokens if summary else 0,
            "output_tokens": summary.actual_output_tokens if summary else 0,
        },
        "cost": {
            "estimated_max_usd": summary.estimated_max_cost_usd if summary else 0.0,
            "actual_usd": summary.actual_cost_usd if summary else 0.0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run exactly one controlled Brand Discovery OpenAI call.")
    parser.add_argument("--allow-paid-call", action="store_true")
    parser.add_argument("--result-limit", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args(argv)

    if not args.allow_paid_call:
        print("Pass --allow-paid-call to authorize exactly one paid request.", file=sys.stderr)
        return 2

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    try:
        settings = AISettings.from_env()
        validate_paid_call_confirmation(
            allow_paid_call=args.allow_paid_call,
            settings=settings,
        )
        safe_summary = asyncio.run(run_one_paid_call(settings, result_limit=args.result_limit))
    except PaidCallConfirmationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except AIServiceError as exc:
        print(json.dumps({"ok": False, "error": exc.code}), file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, **safe_summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
