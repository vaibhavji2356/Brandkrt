"""Safe, schema-tolerant Apollo CSV ingestion for the admin lead workspace."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import re
from urllib.parse import urlsplit

from fastapi import HTTPException

from brand_discovery_ai.discovery_schemas import NormalizedProfile, Platform


MAX_APOLLO_CSV_BYTES = 2 * 1024 * 1024
MAX_APOLLO_ROWS = 500


def parse_apollo_csv(content: bytes) -> tuple[list[tuple[NormalizedProfile, dict]], list[str]]:
    if not content:
        raise HTTPException(status_code=422, detail="Choose a non-empty Apollo CSV file.")
    if len(content) > MAX_APOLLO_CSV_BYTES:
        raise HTTPException(status_code=413, detail="Apollo CSV must be 2 MB or smaller.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="Apollo CSV must use UTF-8 encoding.") from error
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="Apollo CSV header row is missing.")

    results: list[tuple[NormalizedProfile, dict]] = []
    seen: set[str] = set()
    skipped = 0
    for index, raw in enumerate(reader, start=2):
        if index > MAX_APOLLO_ROWS + 1:
            raise HTTPException(status_code=422, detail=f"Apollo CSV supports at most {MAX_APOLLO_ROWS} rows.")
        row = {_column(key): _clean(value) for key, value in raw.items() if key}
        company = _first(row, "companyname", "organizationname", "accountname", "company")
        first_name = _first(row, "firstname", "contactfirstname")
        last_name = _first(row, "lastname", "contactlastname")
        owner_name = " ".join(part for part in (first_name, last_name) if part).strip()
        if not owner_name:
            owner_name = _first(row, "name", "contactname", "personname")
        email = _email(_first(row, "email", "emailaddress", "workemail", "businessemail"))
        phone = _first(row, "phone", "phonenumber", "mobilephone", "workdirectphone", "corporatephone")
        linkedin = _url(_first(row, "linkedinurl", "personlinkedinurl", "contactlinkedinurl"))
        website = _url(_first(row, "website", "companywebsite", "organizationwebsite", "domain"))
        apollo_person_id = _first(row, "id", "personid", "contactid", "apollocontactid")
        apollo_company_id = _first(row, "organizationid", "companyid", "accountid", "apolloaccountid")
        identity = apollo_person_id or email or linkedin or "|".join((company.casefold(), owner_name.casefold()))
        if not identity.strip("|"):
            skipped += 1
            continue
        digest = hashlib.sha256(identity.casefold().encode("utf-8")).hexdigest()
        if digest in seen:
            skipped += 1
            continue
        seen.add(digest)

        city = _first(row, "city", "contactcity", "organizationcity")
        state = _first(row, "state", "stateprovince", "contactstate", "organizationstate")
        country = _first(row, "country", "contactcountry", "organizationcountry")
        location = ", ".join(dict.fromkeys(part for part in (city, state, country) if part)) or None
        industry = _first(row, "industry", "companyindustry", "organizationindustry")
        title = _first(row, "title", "jobtitle", "contacttitle")
        employee_count = _integer(_first(
            row, "numberofemployees", "employees", "employeecount", "organizationemployeecount",
        ))
        keywords = [value for value in (title, industry) if value]
        linked_urls = [linkedin] if linkedin else []
        warnings = []
        if not email and not phone:
            warnings.append("Apollo CSV did not include an email address or phone number for this lead.")
        if not company:
            warnings.append("Apollo CSV did not include a company name.")
        profile = NormalizedProfile(
            entity_type="brand",
            # Apollo is an admin import source, not a social discovery platform.
            # X is used only for the internal normalized-profile scoring contract;
            # the persisted lead is explicitly relabeled as Apollo by the service.
            platform=Platform.X,
            platform_id=f"csv-{digest[:32]}",
            username=owner_name or None,
            display_name=company or owner_name or "Apollo lead",
            profile_url=linkedin,
            biography=" · ".join(value for value in (title, industry) if value) or None,
            categories=[industry] if industry else [],
            keywords=keywords,
            location=location,
            website=website,
            business_email_available=True if email else None,
            linked_social_urls=linked_urls,
            source="apollo_csv",
            source_confidence=0.8,
            collected_at=datetime.now(timezone.utc),
            warnings=warnings,
        )
        details = {
            "owner_name": owner_name or None,
            "job_title": title or None,
            "business_email": email,
            "phone_number": phone or None,
            "company_name": company or None,
            "company_domain": _domain(website),
            "employee_count": employee_count,
            "linkedin_url": linkedin,
            "apollo_person_id": apollo_person_id or None,
            "apollo_company_id": apollo_company_id or None,
        }
        results.append((profile, details))
    if not results:
        raise HTTPException(
            status_code=422,
            detail="No usable Apollo rows found. Export company/contact name, email, LinkedIn URL, or Apollo IDs.",
        )
    warnings = [f"Imported {len(results)} unique Apollo lead rows."]
    if skipped:
        warnings.append(f"Skipped {skipped} empty or duplicate Apollo rows.")
    warnings.append("Apollo CSV values are provider-supplied facts; contact details should be verified before outreach.")
    return results, warnings


def _column(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _first(row: dict[str, str], *names: str) -> str:
    return next((row[name] for name in names if row.get(name)), "")


def _email(value: str) -> str | None:
    value = value.strip().casefold()
    return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) else None


def _url(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _domain(value: str | None) -> str | None:
    if not value:
        return None
    return urlsplit(value).netloc.casefold().removeprefix("www.") or None


def _integer(value: str) -> int | None:
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None
