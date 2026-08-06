from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run completeness/uniqueness/validity/freshness checks and persist the result."""
    row_count = len(df)

    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "row_count_min",
            "dimension": "completeness",
            "passed": row_count > 0,
            "details": {"row_count": row_count},
        }
    )

    paper_id_nulls = int(df["paper_id"].isna().sum()) if row_count else 0
    paper_id_duplicates = int(df["paper_id"].duplicated().sum()) if row_count else 0
    checks.append(
        {
            "name": "paper_id_not_null_and_unique",
            "dimension": "uniqueness",
            "passed": paper_id_nulls == 0 and paper_id_duplicates == 0,
            "details": {"null_count": paper_id_nulls, "duplicate_count": paper_id_duplicates},
        }
    )

    title_blank = int((df["title"].isna() | (df["title"].astype(str).str.strip() == "")).sum()) if row_count else 0
    checks.append(
        {
            "name": "title_not_null",
            "dimension": "completeness",
            "passed": title_blank == 0,
            "details": {"null_or_blank_count": title_blank},
        }
    )

    short_summaries = int((df["summary"].fillna("").astype(str).str.len() < 100).sum()) if row_count else 0
    checks.append(
        {
            "name": "summary_min_length",
            "dimension": "validity",
            "passed": short_summaries == 0,
            "details": {"threshold_chars": 100, "violating_rows": short_summaries},
        }
    )

    stale_rows = (
        int((pd.to_numeric(df["age_days"], errors="coerce").fillna(0) > settings.freshness_threshold_days).sum())
        if row_count
        else 0
    )
    checks.append(
        {
            "name": "freshness_age_days",
            "dimension": "freshness",
            "passed": stale_rows == 0,
            "details": {"threshold_days": settings.freshness_threshold_days, "stale_rows": stale_rows},
        }
    )

    result = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "row_count": row_count,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }

    output_path = settings.paths.quality_dir / f"{report_name}_quality.json"
    write_json(output_path, result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path) -> dict[str, Any]:
    """Summarize freshness (latest/oldest publish date, stale row count) and persist it."""
    if df.empty:
        payload = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "is_fresh": False,
        }
        write_json(Path(report_path), payload)
        return payload

    published_dates = pd.to_datetime(df["published"], errors="coerce")
    latest = published_dates.max()
    oldest = published_dates.min()
    age_days = pd.to_numeric(df["age_days"], errors="coerce").fillna(0)
    stale_rows = int((age_days > settings.freshness_threshold_days).sum())
    total_rows = len(df)

    payload = {
        "latest_published": latest.date().isoformat() if pd.notna(latest) else None,
        "oldest_published": oldest.date().isoformat() if pd.notna(oldest) else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": stale_rows == 0,
    }
    write_json(Path(report_path), payload)
    return payload
