from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the baseline pipeline end-to-end: ingest -> clean -> index -> evaluate -> report."""
    settings = load_settings()

    if settings.paths.raw_records_json.exists() and not settings.refresh_source:
        records = load_raw_records(settings.paths.raw_records_json)
    else:
        records = fetch_source_records(settings)

    run_date = now_utc()
    df = build_clean_dataframe(records, run_date)
    if df.empty:
        raise RuntimeError("Clean dataframe is empty; check ingestion/cleaning logic or the source query.")

    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=settings.paths.embeddings_json)

    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        pass
    else:
        build_test_set(df, settings.paths.eval_testset)

    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    quality = run_data_quality_checks(df, settings, report_name="baseline")
    freshness = build_freshness_report(df, settings, settings.paths.quality_dir / "baseline_freshness.json")

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "records_fetched": len(records),
        "records_after_cleaning": len(df),
        "run_at": run_date.isoformat(),
    }

    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )

    print(
        f"Phase 1 baseline complete: {len(df)} clean records, "
        f"retrieval_hit_rate={bundle.summary['retrieval_hit_rate']:.2f}, "
        f"mean_token_f1={bundle.summary['mean_token_f1']:.2f}, "
        f"quality_passed={quality['passed']}, freshness_is_fresh={freshness['is_fresh']}"
    )


if __name__ == "__main__":
    main()
