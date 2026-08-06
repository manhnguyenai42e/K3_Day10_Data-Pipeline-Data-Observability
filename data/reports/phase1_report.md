# Phase 1 Report — Baseline Pipeline

Generated at: 2026-08-06T04:00:40.524920+00:00

## 1. Source Summary

- **source_api**: Crossref REST API
- **source_query**: agentic retrieval augmented generation large language model
- **source_filter**: from-pub-date:2026-02-07,has-abstract:true
- **records_fetched**: 24
- **records_after_cleaning**: 24
- **run_at**: 2026-08-06T03:59:56.668456+00:00

## 2. RAG Evaluation Metrics

| Metric | Value |
| --- | ---: |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 1.0000 |
| `judge_accuracy` | 1.0000 |
| `mean_judge_score` | 5 |
| `samples` | 12 |

## 3. Data Quality Checks

Overall: **PASS**

| Check | Dimension | Passed | Details |
| --- | --- | --- | --- |
| `row_count_min` | completeness | PASS | {'row_count': 24} |
| `paper_id_not_null_and_unique` | uniqueness | PASS | {'null_count': 0, 'duplicate_count': 0} |
| `title_not_null` | completeness | PASS | {'null_or_blank_count': 0} |
| `summary_min_length` | validity | PASS | {'threshold_chars': 100, 'violating_rows': 0} |
| `freshness_age_days` | freshness | PASS | {'threshold_days': 180, 'stale_rows': 0} |

## 4. Freshness Report

- Latest published: 2026-08-01
- Oldest published: 2026-02-12
- Stale rows: 0 / 24
- Is fresh: YES
