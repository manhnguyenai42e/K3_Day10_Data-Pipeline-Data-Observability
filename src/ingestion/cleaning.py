from __future__ import annotations

from datetime import datetime
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

_TAG_RE = re.compile(r"<[^>]+>")
_MIN_SUMMARY_CHARS = 100


def _strip_tags(text: str) -> str:
    return normalize_whitespace(_TAG_RE.sub(" ", text or ""))


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw Crossref records into an embed-ready dataframe.

    Rows without a title, a summary of at least 100 chars, or a parseable
    publication date are dropped so every surviving row has a valid
    `age_days` for freshness checks downstream.
    """
    rows: list[dict] = []
    seen_ids: set[str] = set()

    for record in records:
        if record.paper_id in seen_ids:
            continue

        title = _strip_tags(record.title)
        summary = _strip_tags(record.summary)

        if not title or len(summary) < _MIN_SUMMARY_CHARS:
            continue

        published_dt = _parse_date(record.published) or _parse_date(record.updated)
        if published_dt is None:
            continue

        seen_ids.add(record.paper_id)

        authors_joined = compact_join(record.authors)
        categories_joined = compact_join(record.categories)
        text_for_embedding = f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"

        rows.append(
            {
                "paper_id": record.paper_id,
                "title": title,
                "summary": summary,
                "published": published_dt.date().isoformat(),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "age_days": (run_date.date() - published_dt.date()).days,
                "text_for_embedding": text_for_embedding,
                "summary_chars": len(summary),
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
            }
        )

    columns = [
        "paper_id",
        "title",
        "summary",
        "published",
        "authors_joined",
        "categories_joined",
        "age_days",
        "text_for_embedding",
        "summary_chars",
        "abs_url",
        "pdf_url",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df

    df = df.drop_duplicates(subset="paper_id", keep="first")
    df = df.sort_values("published", ascending=False).reset_index(drop=True)
    return df
