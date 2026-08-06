# Corruption Comparison Report — Baseline vs Corrupted vs Repaired

Generated at: 2026-08-06T04:04:52.010266+00:00

## 1. RAG Evaluation Metrics

| Metric | Baseline | Corrupted | Repaired | Corruption Δ | Repair Δ |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.6667 | 1.0000 | -0.3333 | 0.3333 |
| `mean_token_f1` | 1.0000 | 0.5116 | 1.0000 | -0.4884 | 0.4884 |
| `judge_accuracy` | 1.0000 | 0.5000 | 1.0000 | -0.5000 | 0.5000 |
| `mean_judge_score` | 5 | 3.08 | 5 | -1.92 | 1.92 |

## 2. Data Quality (pass/fail)

| State | Passed | Failing checks |
| --- | --- | --- |
| Baseline | PASS | [] |
| Corrupted | FAIL | ['paper_id_not_null_and_unique', 'summary_min_length', 'freshness_age_days'] |
| Repaired | PASS | [] |

## 3. Freshness

| State | Stale rows / total | Is fresh |
| --- | --- | --- |
| Baseline | 0 / 24 | YES |
| Corrupted | 2 / 24 | NO |
| Repaired | 0 / 24 | YES |
