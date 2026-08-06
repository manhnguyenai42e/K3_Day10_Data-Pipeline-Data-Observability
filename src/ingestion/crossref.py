from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_API_URL = "https://api.crossref.org/works"
_RETRYABLE_STATUS_CODES = {429, 503}
_MAX_ATTEMPTS = 5
_INITIAL_BACKOFF_SECONDS = 2.0


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _extract_date(item: dict, keys: list[str]) -> str:
    for key in keys:
        block = item.get(key)
        if not block:
            continue
        parts = block.get("date-parts")
        if not parts or not parts[0] or not parts[0][0]:
            continue
        date_parts = parts[0]
        year = date_parts[0]
        month = date_parts[1] if len(date_parts) > 1 and date_parts[1] else 1
        day = date_parts[2] if len(date_parts) > 2 and date_parts[2] else 1
        try:
            return date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            return date(int(year), 1, 1).isoformat()
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a raw Crossref `/works` response into flat `PaperRecord`s.

    Only records with a non-empty title AND abstract are kept here; length
    thresholds and HTML/XML stripping are the cleaning stage's job, not
    ingestion's, so raw text is preserved as-is for audit purposes.
    """
    items = (payload.get("message") or {}).get("items") or []
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()

    for item in items:
        doi = item.get("DOI")
        titles = item.get("title") or []
        title = normalize_whitespace(titles[0]) if titles else ""
        abstract = (item.get("abstract") or "").strip()

        if not doi or not title or not abstract:
            continue

        paper_id = doi.strip().lower()
        if paper_id in seen_ids:
            continue
        seen_ids.add(paper_id)

        authors: list[str] = []
        for author in item.get("author") or []:
            given = (author.get("given") or "").strip()
            family = (author.get("family") or "").strip()
            full_name = normalize_whitespace(f"{given} {family}")
            if full_name:
                authors.append(full_name)

        categories = [normalize_whitespace(subject) for subject in (item.get("subject") or []) if subject]
        if not categories:
            # Crossref's `subject` (ASJC taxonomy) is rarely populated by publishers;
            # fall back to the work `type` (e.g. journal-article) so categories_joined
            # is never empty for downstream eval/quality checks.
            work_type = normalize_whitespace((item.get("type") or "").replace("-", " "))
            if work_type:
                categories = [work_type]
        primary_category = categories[0] if categories else ""

        published = _extract_date(item, ["published-print", "published-online", "published", "issued"])
        updated = _extract_date(item, ["indexed", "deposited", "created"]) or published

        abs_url = item.get("URL") or ""
        pdf_url = ""
        for link in item.get("link") or []:
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL") or ""
                break

        comment = normalize_whitespace(", ".join(item.get("container-title") or []))

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=abstract,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Call the Crossref API with retry/backoff and persist both raw artifacts."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {"User-Agent": "K3-Day10-DataPipelineLab/1.0 (mailto:lab-student@example.com)"}

    backoff = _INITIAL_BACKOFF_SECONDS
    response: requests.Response | None = None
    last_error: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = requests.get(CROSSREF_API_URL, params=params, headers=headers, timeout=30)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == _MAX_ATTEMPTS:
                raise
            time.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
            time.sleep(backoff)
            backoff *= 2
            continue
        break

    if response is None:
        raise RuntimeError(f"Crossref request failed with no response: {last_error}")
    response.raise_for_status()

    payload = response.json()
    write_json(settings.paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a previously saved raw records JSON snapshot back into `PaperRecord`s."""
    payload = read_json(path)
    return [PaperRecord(**item) for item in payload]
