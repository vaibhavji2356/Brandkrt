"""Deterministic offline fixtures for prompt and output-token calibration."""

from dataclasses import dataclass
import json

from .config import AISettings
from .costing import estimate_text_tokens
from .prompting import build_brand_discovery_prompt
from .providers import response_json_schema
from .schemas import BrandDiscoveryRequest


EVALUATION_RESULT_LIMITS = (1, 5, 10, 20)


@dataclass(frozen=True)
class TokenCalibration:
    result_limit: int
    prompt_tokens: int
    schema_tokens: int
    calibrated_output_tokens: int
    configured_output_cap: int
    truncation_risk: str


def build_evaluation_request(result_limit: int) -> BrandDiscoveryRequest:
    if result_limit not in EVALUATION_RESULT_LIMITS:
        raise ValueError("Unsupported evaluation result limit")
    return BrandDiscoveryRequest(
        industry="sustainable consumer goods",
        niche="refillable personal care and low-waste home products",
        location="India",
        target_audience="urban consumers aged 20 to 40 interested in practical sustainability",
        campaign_objective="evaluate creator partnership fit for an awareness campaign",
        minimum_budget=25_000,
        maximum_budget=150_000,
        preferred_platforms=["Instagram", "YouTube"],
        brand_size="small to medium",
        keywords=["sustainable", "refillable", "low waste"],
        exclusions=["unverified medical claims", "adult products"],
        result_limit=result_limit,
    )


def build_calibrated_output_fixture(result_limit: int) -> dict:
    if result_limit not in EVALUATION_RESULT_LIMITS:
        raise ValueError("Unsupported evaluation result limit")
    results = []
    for index in range(1, result_limit + 1):
        results.append({
            "brand_name": f"Sustainable Candidate {index:02d}",
            "website": f"https://candidate{index:02d}.com",
            "industry": "Sustainable consumer goods",
            "description": "AI-generated candidate aligned with refillable products and practical low-waste positioning.",
            "location": "India",
            "relevance_score": 88 - (index % 8),
            "confidence_score": 72 - (index % 6),
            "fit_reasons": [
                "Matches the requested sustainability niche.",
                "Potential fit for creator-led awareness content.",
            ],
            "outreach_angle": "Suggest a small creator pilot focused on practical refill habits.",
            "source_type": "ai_generated",
            "warnings": ["AI-generated candidate; verify brand and contact details."],
        })
    return {"results": results}


def build_token_calibration(settings: AISettings) -> list[TokenCalibration]:
    schema_tokens = estimate_text_tokens(
        json.dumps(response_json_schema(), separators=(",", ":"), sort_keys=True)
    )
    report = []
    for result_limit in EVALUATION_RESULT_LIMITS:
        prompt = build_brand_discovery_prompt(build_evaluation_request(result_limit))
        prompt_tokens = estimate_text_tokens(
            json.dumps(prompt.as_messages(), ensure_ascii=False, separators=(",", ":"))
        )
        output_tokens = estimate_text_tokens(
            json.dumps(
                build_calibrated_output_fixture(result_limit),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        ratio = output_tokens / settings.max_output_tokens
        risk = "high" if ratio > 0.9 else "medium" if ratio > 0.7 else "low"
        report.append(TokenCalibration(
            result_limit=result_limit,
            prompt_tokens=prompt_tokens,
            schema_tokens=schema_tokens,
            calibrated_output_tokens=output_tokens,
            configured_output_cap=settings.max_output_tokens,
            truncation_risk=risk,
        ))
    return report
