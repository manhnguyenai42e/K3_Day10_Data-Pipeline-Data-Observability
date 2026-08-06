from __future__ import annotations

from datetime import date
from pathlib import Path
import random
from typing import Any

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_json

_STALE_DATE = "2000-01-01"
_NOISE_SNIPPET = " ##CORRUPTED-NOISE-lorem-ipsum-zzz-random-glitch-inject## "
_RANDOM_SEED = 42


def _rebuild_text_for_embedding(row: pd.Series) -> str:
    return f"Title: {row['title']} | Authors: {row['authors_joined']} | Summary: {row['summary']}"


def _load_frozen_eval_doc_ids() -> set[str]:
    """Load ground_truth_doc_ids from the frozen test set so corruption is guaranteed
    to overlap at least one evaluated document (per the lab's C4 warning)."""
    try:
        settings = load_settings()
        test_set = read_json(settings.paths.eval_testset)
    except (FileNotFoundError, OSError):
        return set()
    return {doc_id for item in test_set for doc_id in item.get("ground_truth_doc_ids", [])}


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Apply controlled, logged corruption scenarios to the clean dataframe.

    Scenarios deliberately target documents referenced by the frozen
    evaluation set's `ground_truth_doc_ids` so the impact is measurable in
    retrieval/answer metrics, not just in quality checks.
    """
    rng = random.Random(_RANDOM_SEED)
    working = df.copy().reset_index(drop=True)
    target_ids = _load_frozen_eval_doc_ids() & set(working["paper_id"])
    target_ids_list = sorted(target_ids)
    other_ids = [pid for pid in working["paper_id"] if pid not in target_ids]

    scenarios: list[dict[str, Any]] = []

    # 1. Blank summary on the first half of targeted docs (at least one row).
    half = max(1, len(target_ids_list) // 2) if target_ids_list else 0
    blank_ids = target_ids_list[:half]
    if not blank_ids and len(working):
        blank_ids = [working.iloc[0]["paper_id"]]
    mask = working["paper_id"].isin(blank_ids)
    working.loc[mask, "summary"] = ""
    scenarios.append({"type": "blank_summary", "affected_paper_ids": blank_ids, "affected_rows": int(mask.sum())})

    # 2. Stale publication date on the remaining targeted docs.
    stale_ids = target_ids_list[half:] or target_ids_list
    mask = working["paper_id"].isin(stale_ids)
    working.loc[mask, "published"] = _STALE_DATE
    stale_age = (now_utc().date() - date(2000, 1, 1)).days
    working.loc[mask, "age_days"] = stale_age
    scenarios.append({"type": "stale_date", "affected_paper_ids": stale_ids, "affected_rows": int(mask.sum())})

    # 3. Truncate titles for every targeted doc.
    mask = working["paper_id"].isin(target_ids_list)
    working.loc[mask, "title"] = working.loc[mask, "title"].apply(lambda t: t[: max(5, len(t) // 3)])
    scenarios.append({"type": "title_truncate", "affected_paper_ids": target_ids_list, "affected_rows": int(mask.sum())})

    # 4. Inject noise into the summary text: a few random non-target docs plus one target doc.
    noise_sample_size = min(3, len(other_ids))
    noise_ids = rng.sample(other_ids, noise_sample_size) if noise_sample_size else []
    if target_ids_list:
        noise_ids = noise_ids + [target_ids_list[0]]
    mask = working["paper_id"].isin(noise_ids)
    working.loc[mask, "summary"] = working.loc[mask, "summary"].apply(lambda s: f"{s}{_NOISE_SNIPPET}")
    scenarios.append({"type": "noise_injection", "affected_paper_ids": noise_ids, "affected_rows": int(mask.sum())})

    # 5. Duplicate rows (same paper_id kept, per lab spec) for one target doc and one other doc.
    dup_ids = ([target_ids_list[0]] if target_ids_list else []) + (other_ids[:1] if other_ids else [])
    dup_rows = working[working["paper_id"].isin(dup_ids)]
    working = pd.concat([working, dup_rows], ignore_index=True)
    scenarios.append({"type": "duplicate_rows", "affected_paper_ids": dup_ids, "affected_rows": len(dup_rows)})

    # 6. Drop a couple of the latest non-targeted records (affects completeness/row count
    #    without erasing the ability to answer frozen eval questions entirely).
    sorted_idx = working.sort_values("published", ascending=False).index
    drop_candidates = [i for i in sorted_idx if working.loc[i, "paper_id"] not in target_ids_list][:2]
    dropped_ids = working.loc[drop_candidates, "paper_id"].tolist()
    working = working.drop(index=drop_candidates).reset_index(drop=True)
    scenarios.append({"type": "drop_latest_records", "affected_paper_ids": dropped_ids, "affected_rows": len(drop_candidates)})

    # Rebuild derived fields since title/summary changed.
    working["text_for_embedding"] = working.apply(_rebuild_text_for_embedding, axis=1)
    working["summary_chars"] = working["summary"].astype(str).str.len()

    log = {
        "corrupted_at": now_utc().isoformat(),
        "random_seed": _RANDOM_SEED,
        "target_doc_ids_from_eval_set": target_ids_list,
        "total_rows_before": len(df),
        "total_rows_after": len(working),
        "scenarios": scenarios,
    }
    write_json(Path(output_log_path), log)
    return working
