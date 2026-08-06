from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

_MIN_DOCUMENTS = 3
_MAX_REPRESENTATIVE_PAPERS = 3


def _pick_representative_indices(row_count: int, n: int) -> list[int]:
    if row_count <= n:
        return list(range(row_count))
    step = row_count / n
    return sorted({int(i * step) for i in range(n)})


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a frozen evaluation set from the cleaned dataframe.

    Each representative paper yields four question types (summary, authors,
    date, categories). Questions embed the paper title in single quotes so
    that `retrieval.qa.answer_question`'s exact-title lookup can resolve
    them deterministically, and each question's `ground_truth` is phrased to
    match the corresponding extraction branch in `qa._extract_answer`.
    """
    if len(df) < _MIN_DOCUMENTS:
        raise ValueError(
            f"Cleaned dataset has only {len(df)} rows; need at least {_MIN_DOCUMENTS} to build a test set."
        )

    indices = _pick_representative_indices(len(df), _MAX_REPRESENTATIVE_PAPERS)
    rows = df.iloc[indices]

    test_set: list[dict[str, Any]] = []
    counter = 1
    for _, row in rows.iterrows():
        title = row["title"]
        paper_id = row["paper_id"]

        test_set.append(
            {
                "id": f"q{counter}",
                "question_type": "summary",
                "question": f"What is the main summary of the paper titled '{title}'?",
                "ground_truth": first_sentence(row["summary"]),
                "ground_truth_doc_ids": [paper_id],
            }
        )
        counter += 1

        test_set.append(
            {
                "id": f"q{counter}",
                "question_type": "authors",
                "question": f"Who authored the paper titled '{title}'?",
                "ground_truth": row["authors_joined"],
                "ground_truth_doc_ids": [paper_id],
            }
        )
        counter += 1

        test_set.append(
            {
                "id": f"q{counter}",
                "question_type": "date",
                "question": f"When was the paper titled '{title}' published?",
                "ground_truth": row["published"],
                "ground_truth_doc_ids": [paper_id],
            }
        )
        counter += 1

        test_set.append(
            {
                "id": f"q{counter}",
                "question_type": "categories",
                "question": f"What categories does the paper titled '{title}' belong to?",
                "ground_truth": row["categories_joined"],
                "ground_truth_doc_ids": [paper_id],
            }
        )
        counter += 1

    write_json(output_path, test_set)
    return test_set
