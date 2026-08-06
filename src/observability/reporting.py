from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text


def _format_metrics_table(metrics: dict[str, Any]) -> str:
    lines = ["| Metric | Value |", "| --- | ---: |"]
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score", "samples"):
        if key in metrics:
            value = metrics[key]
            formatted = f"{value:.4f}" if isinstance(value, float) else str(value)
            lines.append(f"| `{key}` | {formatted} |")
    return "\n".join(lines)


def _format_quality_table(quality: dict[str, Any]) -> str:
    lines = ["| Check | Dimension | Passed | Details |", "| --- | --- | --- | --- |"]
    for check in quality.get("checks", []):
        passed = "PASS" if check["passed"] else "FAIL"
        lines.append(f"| `{check['name']}` | {check['dimension']} | {passed} | {check['details']} |")
    return "\n".join(lines)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline phase markdown report."""
    lines = [
        "# Phase 1 Report — Baseline Pipeline",
        "",
        f"Generated at: {now_utc().isoformat()}",
        "",
        "## 1. Source Summary",
        "",
        *(f"- **{key}**: {value}" for key, value in source_summary.items()),
        "",
        "## 2. RAG Evaluation Metrics",
        "",
        _format_metrics_table(metrics),
        "",
        "## 3. Data Quality Checks",
        "",
        f"Overall: **{'PASS' if quality['passed'] else 'FAIL'}**",
        "",
        _format_quality_table(quality),
        "",
        "## 4. Freshness Report",
        "",
        f"- Latest published: {freshness['latest_published']}",
        f"- Oldest published: {freshness['oldest_published']}",
        f"- Stale rows: {freshness['stale_rows']} / {freshness['total_rows']}",
        f"- Is fresh: {'YES' if freshness['is_fresh'] else 'NO'}",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    baseline_freshness: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write the baseline/corrupted/repaired comparison markdown report."""

    def metric_row(label: str, key: str, fmt: str = "{:.4f}") -> str:
        base = baseline_metrics.get(key)
        corr = corrupted_metrics.get(key)
        rep = repaired_metrics.get(key)
        base_s = fmt.format(base) if isinstance(base, float) else str(base)
        corr_s = fmt.format(corr) if isinstance(corr, float) else str(corr)
        rep_s = fmt.format(rep) if isinstance(rep, float) else str(rep)
        delta = (corr - base) if isinstance(base, (int, float)) and isinstance(corr, (int, float)) else None
        recovery = (rep - corr) if isinstance(rep, (int, float)) and isinstance(corr, (int, float)) else None
        delta_s = fmt.format(delta) if isinstance(delta, float) else "n/a"
        recovery_s = fmt.format(recovery) if isinstance(recovery, float) else "n/a"
        return f"| `{key}` | {base_s} | {corr_s} | {rep_s} | {delta_s} | {recovery_s} |"

    lines = [
        "# Corruption Comparison Report — Baseline vs Corrupted vs Repaired",
        "",
        f"Generated at: {now_utc().isoformat()}",
        "",
        "## 1. RAG Evaluation Metrics",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Corruption Δ | Repair Δ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        metric_row("Retrieval hit rate", "retrieval_hit_rate"),
        metric_row("Mean token F1", "mean_token_f1"),
        metric_row("Judge accuracy", "judge_accuracy"),
        metric_row("Mean judge score", "mean_judge_score", fmt="{:.2f}"),
        "",
        "## 2. Data Quality (pass/fail)",
        "",
        "| State | Passed | Failing checks |",
        "| --- | --- | --- |",
        (
            f"| Baseline | {'PASS' if baseline_quality['passed'] else 'FAIL'} | "
            f"{[c['name'] for c in baseline_quality['checks'] if not c['passed']]} |"
        ),
        (
            f"| Corrupted | {'PASS' if corrupted_quality['passed'] else 'FAIL'} | "
            f"{[c['name'] for c in corrupted_quality['checks'] if not c['passed']]} |"
        ),
        (
            f"| Repaired | {'PASS' if repaired_quality['passed'] else 'FAIL'} | "
            f"{[c['name'] for c in repaired_quality['checks'] if not c['passed']]} |"
        ),
        "",
        "## 3. Freshness",
        "",
        "| State | Stale rows / total | Is fresh |",
        "| --- | --- | --- |",
        (
            f"| Baseline | {baseline_freshness['stale_rows']} / {baseline_freshness['total_rows']} | "
            f"{'YES' if baseline_freshness['is_fresh'] else 'NO'} |"
        ),
        (
            f"| Corrupted | {corrupted_freshness['stale_rows']} / {corrupted_freshness['total_rows']} | "
            f"{'YES' if corrupted_freshness['is_fresh'] else 'NO'} |"
        ),
        (
            f"| Repaired | {repaired_freshness['stale_rows']} / {repaired_freshness['total_rows']} | "
            f"{'YES' if repaired_freshness['is_fresh'] else 'NO'} |"
        ),
        "",
    ]
    write_text(report_path, "\n".join(lines))
