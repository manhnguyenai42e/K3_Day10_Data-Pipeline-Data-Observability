# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K3              |
| Tên nhóm         | K3-Day10-Data-Pipeline-Observability     |
| Repository         | https://github.com/nhmanhDev/K3_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Hùng Mạnh | [MSSV] | Source Ingestion Owner | `src/ingestion/crossref.py` |
| 2 | Nguyễn Văn A | [MSSV] | Data Model & Eval Set Owner | `src/ingestion/cleaning.py`, `src/evaluation/testset.py` |
| 3 | B | [MSSV] | Data Observability Owner | `src/observability/quality.py`, `src/observability/reporting.py` |
| 4 | C | [MSSV] | Corruption & Repair Owner | `src/ingestion/corruption.py` |
| 5 | D | [MSSV] | Integration & Comparison Owner | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` |

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm đã hoàn thành toàn bộ 6 checkpoint (C0–C5) của bài lab. Baseline pipeline (`script/run_phase1.py`) fetch 24 bài báo từ Crossref API (query "agentic retrieval augmented generation large language model"), làm sạch còn 24 dòng hợp lệ, index vào ChromaDB, và đạt `retrieval_hit_rate = 1.00`, `mean_token_f1 = 1.00`, `judge_accuracy = 1.00` trên bộ 12 câu hỏi eval cố định. Data quality và freshness đều PASS ở baseline.

Nhóm áp dụng 6 kịch bản corruption có kiểm soát (blank summary, stale date, title truncate, noise injection, duplicate rows, drop latest records), cố tình nhắm vào 3 tài liệu nằm trong `ground_truth_doc_ids` của test set. Corruption ảnh hưởng rõ nhất đến retrieval là **blank summary** và **title truncate** kết hợp — vì `retrieval.qa.answer_question` dựa vào exact-title lookup và trích xuất trực tiếp từ `summary`/`published`/`categories_joined`, nên khi các trường này bị hỏng, cả retrieval lẫn answer đều sai theo. Kết quả: `retrieval_hit_rate` giảm còn 0.67, `mean_token_f1` giảm còn 0.51, `judge_accuracy` giảm còn 0.50; quality checks FAIL ở 3 dimension (uniqueness do duplicate `paper_id`, validity do summary quá ngắn, freshness do stale date).

Repair từ raw snapshot (`data/raw/crossref_records.json`) đã phục hồi **100%** tất cả metrics về đúng mức baseline (1.00 / 1.00 / 1.00) và quality/freshness đều PASS trở lại — chứng minh pipeline làm sạch là deterministic và raw snapshot đủ để tái tạo lại dữ liệu sạch mà không cần gọi lại API.

Giới hạn còn lại: bộ eval set chỉ có 12 câu trên 3 tài liệu đại diện (do `df` chỉ có 24 bản ghi từ 1 lần fetch), nên các con số run-to-run có thể dao động nếu Crossref trả về tập kết quả khác; Ragas chưa bật (`RUN_RAGAS=1`) do tốn thời gian.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records         (data/raw/)
    -> cleaning và data modeling        (data/clean/papers_clean.*)
    -> embedding + ChromaDB index       (data/embeddings/, data/chroma/)
    -> evaluation baseline              (data/results/baseline_*)
    -> quality/freshness reports        (data/quality/baseline_*)
    -> corruption                       (data/clean/papers_clean_corrupted.*, data/results/corruption_log.json)
    -> re-index và re-evaluate          (data/results/corrupted_*)
    -> repair từ dữ liệu nguồn          (data/clean/papers_clean_repaired.*)
    -> re-index và re-evaluate          (data/results/repaired_*)
    -> comparison report                (data/reports/corruption_report.md)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API (`/works`) | Query + retry 429/503, parse payload thành `PaperRecord` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Nguyễn Hùng Mạnh |
| Cleaning          | `crossref_records.json` | Strip XML/HTML, join authors/categories, tính `age_days`, tạo `text_for_embedding`, lọc bản ghi xấu | `data/clean/papers_clean.csv`, `papers_clean.json` | Nguyễn Văn A |
| Eval set          | `papers_clean.json` | Sinh câu hỏi factual (summary/authors/date/categories) bám ground truth | `data/eval/test_set.json` | Nguyễn Văn A |
| Embedding/index   | `papers_clean.json` | MiniLM embedding + ChromaDB collection (đã có sẵn trong starter) | `data/embeddings/*.json`, `data/chroma/` | (dùng chung, không cần sửa) |
| Evaluation        | `test_set.json` + index | Trả lời câu hỏi, tính `retrieval_hit_rate`, `mean_token_f1`, LLM judge (Gemini) | `data/results/*_metrics.json`, `*_answers.json` | D gọi `evaluation/metrics.py` trong pipeline |
| Observability     | `papers_clean.json` (mỗi trạng thái) | Completeness/uniqueness/validity checks + freshness report | `data/quality/*_quality.json`, `*_freshness.json` | B |
| Corruption/repair | `papers_clean.csv` + `test_set.json` | Corrupt có kiểm soát (trúng doc trong eval set) + repair từ raw snapshot | `data/clean/papers_clean_corrupted.csv`, `data/results/corruption_log.json` | C |
| Orchestration     | Toàn bộ module trên | Ghép baseline pipeline (`phase1.py`) và corruption/repair/compare flow (`corruption_flow.py`) | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | D |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | gemini         |
| `LLM_MODEL`                | gemini-2.5-flash         |
| Embedding model              | sentence-transformers/all-MiniLM-L6-v2         |
| Số lượng Crossref records | 24 (max_results, query: "agentic retrieval augmented generation large language model")        |
| Retrieval `top_k`           | 4         |
| Freshness threshold          | 180 ngày         |
| Random seed (corruption)     | 42        |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

```bash
uv sync
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | 2026-08-06 | `data/reports/phase1_report.md`, `data/results/baseline_metrics.json` |
| Corruption flow   | Thành công | 2026-08-06 | `data/reports/corruption_report.md`, `data/results/corrupted_metrics.json`, `repaired_metrics.json` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API — `https://api.crossref.org/works` |
| Query/filter                | query="agentic retrieval augmented generation large language model", filter="from-pub-date:...,has-abstract:true" |
| Thời điểm lấy dữ liệu | 2026-08-06 (chạy lại sẽ trả kết quả khác vì Crossref index liên tục cập nhật) |
| Số record nhận được    | 24 (rows=24, đã lọc `has-abstract:true` ở tầng filter) |
| Cơ chế retry/backoff      | Retry tối đa 5 lần, backoff nhân đôi (2s, 4s, 8s...) khi gặp HTTP 429/503 |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id`      | string (DOI, lowercase) | Có | Khóa chính duy nhất | Bỏ record trùng DOI |
| `title`         | string          | Có | Tiêu đề bài báo | Bỏ record nếu rỗng sau khi strip tag |
| `summary`       | string          | Có | Tóm tắt/abstract | Bỏ record nếu < 100 ký tự sau khi strip tag |
| `published`     | string (YYYY-MM-DD) | Có | Ngày xuất bản chuẩn hóa | Fallback sang `updated`; bỏ record nếu cả hai đều không parse được |
| `authors_joined`| string (comma-separated) | Không | Danh sách tác giả | Rỗng nếu Crossref không có `author` |
| `categories_joined` | string (comma-separated) | Không | Chủ đề/loại công trình | Fallback sang Crossref `type` (vd. "journal article") khi `subject` rỗng |
| `age_days`      | int             | Có | Số ngày kể từ lúc xuất bản, dùng cho freshness check | Luôn tính được vì `published` bắt buộc hợp lệ |
| `text_for_embedding` | string     | Có | `Title: ... \| Authors: ... \| Summary: ...` dùng để embed | Rebuild lại mỗi khi title/summary bị corrupt |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Bỏ record thiếu title/abstract ở tầng ingestion (`crossref.py`) | Completeness | 0/24 (query đã có `has-abstract:true`) | `data/raw/crossref_records.json` |
| Bỏ record có summary < 100 ký tự (`cleaning.py`) | Validity | 0/24 | `data/clean/papers_clean.csv` (24 dòng, bằng số record fetch) |
| Bỏ record không parse được ngày published/updated | Completeness/Freshness | 0/24 | `age_days` luôn là số nguyên hợp lệ trong clean data |
| Strip thẻ XML/HTML (`<jats:p>`, `<b>`...) khỏi title/summary | Validity | 24/24 (áp dụng cho mọi record) | So sánh `data/raw/crossref_records.json` (còn tag) với `papers_clean.json` (đã sạch) |

`text_for_embedding` được ghép theo đúng format `Title: {title} | Authors: {authors_joined} | Summary: {summary}`. `paper_id` dùng trực tiếp DOI viết thường làm document ID (đảm bảo duy nhất và ổn định qua các lần chạy lại). `age_days` = số ngày giữa thời điểm chạy pipeline và `published` (đã parse chuẩn ISO).

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 12 (3 bài báo đại diện × 4 loại câu hỏi)         |
| Các `question_type`                    | summary, authors, date, categories        |
| Ground-truth document ID                 | `[paper_id]` của chính bài báo được hỏi (1 doc/câu)     |
| Embedding model                          | sentence-transformers/all-MiniLM-L6-v2 (384 chiều)        |
| Vector store/collection                  | ChromaDB tại `data/chroma/`, collection `papers-baseline` / `papers-corrupted` / `papers-repaired`        |
| Retrieval `top_k`                       | 4        |
| LLM provider/model                       | Gemini (`gemini-2.5-flash`) qua `GOOGLE_API_KEY`        |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (không đổi qua baseline/corrupted/repaired) |

Test set được đóng băng (chỉ sinh 1 lần ở checkpoint C2, `phase1.py` không ghi đè nếu file đã tồn tại) để đảm bảo baseline, corrupted và repaired được chấm trên đúng cùng 12 câu hỏi — nếu không, sự thay đổi về metric có thể do đổi câu hỏi thay vì do corruption/repair, làm mất tính so sánh được (apples-to-apples).

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | `crossref_response.json` (raw HTTP), `crossref_records.json` (24 `PaperRecord`) |
| Cleaned dataset          | `data/clean/`                        | Có | `papers_clean.csv`/`.json`, 24 dòng |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/`   | Có | `papers_embeddings.json` (manifest), Chroma persist tại `data/chroma/` |
| Evaluation set           | `data/eval/test_set.json`            | Có | 12 câu hỏi cố định |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Xem bảng bên dưới |
| Quality/freshness        | `data/quality/baseline_quality.json`, `baseline_freshness.json` | Có | Cả hai PASS |
| Baseline report          | `data/reports/phase1_report.md`      | Có | Sinh tự động bởi `reporting.generate_phase1_report` |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     1.00 | Cả 12/12 câu hỏi đều retrieve đúng `paper_id` trong top-4, nhờ exact-title lookup trong `qa.answer_question` |
| `mean_token_f1`      |     1.00 | Answer trích xuất trực tiếp từ field tương ứng (authors_joined/published/categories_joined/summary) nên khớp tuyệt đối với ground truth ở baseline |
| `judge_accuracy`     |     1.00 | Gemini judge chấm tất cả 12 câu là "correct" |
| `mean_judge_score`   |     5 | Điểm tối đa (thang 1–5) cho toàn bộ câu trả lời baseline |
| Ragas                 | N/A (skipped) | Chưa bật `RUN_RAGAS=1` vì tốn thời gian chạy; có thể bật để lấy thêm faithfulness/context precision |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `row_count_min` | Completeness | row_count > 0 | PASS (24 rows) | `data/quality/baseline_quality.json` |
| `paper_id_not_null_and_unique` | Uniqueness | 0 null, 0 duplicate | PASS (0, 0) | `data/quality/baseline_quality.json` |
| `title_not_null` | Completeness | 0 blank | PASS (0) | `data/quality/baseline_quality.json` |
| `summary_min_length` | Validity | ≥ 100 ký tự | PASS (0 vi phạm) | `data/quality/baseline_quality.json` |
| `freshness_age_days` | Freshness | age_days ≤ 180 | PASS (0 stale rows) | `data/quality/baseline_quality.json` |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | `data/clean/papers_clean.csv` (baseline) |
| Timestamp mới nhất       | 2026-08-01 (latest_published)         |
| Ngưỡng freshness         | 180 ngày (`freshness_threshold_days`) |
| Trạng thái baseline      | Fresh (is_fresh = true, 0/24 stale rows)               |
| Lý do                     | Toàn bộ 24 bài báo được publish trong khoảng 2026-02-12 → 2026-08-01, tức trong vòng 180 ngày kể từ ngày chạy pipeline |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| Blank summary | Gán `summary = ""` cho 1 doc trong eval set | 1 | Validity (`summary_min_length`) FAIL | Góp phần làm `mean_token_f1`/`judge_accuracy` giảm cho câu hỏi "summary" của doc đó | Rebuild `summary` từ `data/raw/crossref_records.json` |
| Stale date | Gán `published = 2000-01-01` cho 2 doc trong eval set | 2 | Freshness (`freshness_age_days`) FAIL | `is_fresh = false`, `stale_rows = 2`; câu hỏi "date" trả lời sai | Parse lại `published` gốc từ raw record |
| Title truncate | Cắt còn 1/3 độ dài title cho cả 3 doc trong eval set | 3 | — (không có check riêng cho title length, nhưng phá exact-title lookup) | Retrieval fallback về semantic search thay vì exact match → giảm `retrieval_hit_rate` | Rebuild `title` từ raw record |
| Noise injection | Nối chuỗi rác vào cuối `summary` cho 3 doc khác + 1 doc trong eval set | 4 | Có thể ảnh hưởng validity nếu vượt ngưỡng | Làm nhiễu embedding, giảm chất lượng semantic search | Rebuild `text_for_embedding` từ raw record sạch |
| Duplicate rows | Nhân đôi dòng của 1 doc trong eval set + 1 doc khác, giữ nguyên `paper_id` | 2 (thêm 2 dòng) | Uniqueness (`paper_id_not_null_and_unique`) FAIL | Trùng `paper_id` trong Chroma (ghi đè theo `record_id` nhưng vẫn phá quality check) | Repair từ raw = data gốc chỉ có 1 dòng/paper_id |
| Drop latest records | Xóa 2 dòng có `published` mới nhất, không nằm trong eval set | 2 (xóa) | Completeness (`row_count_min` giảm) | Giảm `total_rows` từ 24 xuống còn số ít hơn (không ảnh hưởng trực tiếp metric RAG vì không nằm trong eval set) | Repair đọc lại toàn bộ raw records, không phụ thuộc vào state đã bị xóa |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi đầy đủ 6 loại corruption, danh sách `affected_paper_ids` cụ thể cho từng loại, và `target_doc_ids_from_eval_set` để chứng minh corruption trúng đích vào các document nằm trong `ground_truth_doc_ids` của test set.

Repair đảm bảo phục hồi từ nguồn đáng tin cậy (không chỉ che lỗi) vì `corruption_flow.py` gọi lại đúng `ingestion.cleaning.build_clean_dataframe()` — hàm cleaning chuẩn dùng ở baseline — trên `data/raw/crossref_records.json`, tức là raw snapshot được lưu **trước khi** corruption xảy ra. Vì vậy dữ liệu repaired không phải là "sửa tay" từng lỗi mà là tái tạo lại toàn bộ pipeline sạch từ nguồn gốc, cho ra kết quả giống hệt baseline (retrieval_hit_rate 1.00, quality PASS).

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |     1.00 |      0.67 |     1.00 |                    -0.33 |            +0.33 | Phục hồi hoàn toàn |
| `mean_token_f1`        |     1.00 |      0.51 |     1.00 |                    -0.49 |            +0.49 | Phục hồi hoàn toàn |
| `judge_accuracy`       |     1.00 |      0.50 |     1.00 |                    -0.50 |            +0.50 | Phục hồi hoàn toàn |
| `mean_judge_score`     |        5 |      3.08 |        5 |                    -1.92 |            +1.92 | Phục hồi hoàn toàn |
| Quality checks pass/fail |     PASS |      FAIL |     PASS |     3 dimension FAIL (uniqueness, validity, freshness) |             PASS trở lại | Phục hồi hoàn toàn |
| Freshness status         |    Fresh |     Stale (2/24 stale rows) |    Fresh |      2 rows bị stale hóa |             0 stale rows | Phục hồi hoàn toàn |

Hai kết luận nhân quả được hỗ trợ bởi artifacts:

1. **Stale-date corruption → freshness FAIL → answer sai cho câu hỏi ngày xuất bản.** `corruption_log.json` cho thấy 2 document trong eval set bị gán `published = 2000-01-01`; `corrupted_freshness.json` ghi nhận `stale_rows = 2, is_fresh = false`; và `corrupted_metrics.json` cho thấy `mean_token_f1` giảm còn 0.51 vì câu hỏi loại "date" trả lời sai ngày.
2. **Title-truncate + blank-summary corruption → phá exact-title lookup trong `qa.answer_question` → retrieval_hit_rate giảm từ 1.00 xuống 0.67.** Sau khi `repair` rebuild lại `title`/`summary` từ `data/raw/crossref_records.json` (không fetch lại API), `repaired_metrics.json` cho thấy `retrieval_hit_rate` quay về đúng 1.00 — chứng minh nguyên nhân gốc là dữ liệu bị hỏng, không phải do agent/model.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi build `data/eval/test_set.json` lần đầu bằng cách đọc lại `papers_clean.csv` qua `pd.read_csv`, câu hỏi loại "categories" có `ground_truth` là `NaN` (kiểu float) thay vì chuỗi rỗng, khiến `evaluate_pipeline` crash tại `_token_f1` với `TypeError: expected string or bytes-like object, got 'float'`.
- **Nguyên nhân:** Pandas mặc định chuyển ô CSV rỗng (`""`) thành `NaN` khi đọc lại bằng `read_csv`; đồng thời Crossref hiếm khi trả về trường `subject` (0/24 record có category), nên `categories_joined` luôn rỗng ở nguồn.
- **Cách xử lý:** (1) Thêm hàm `_safe_str()` trong `testset.py` để chống NaN bất kể nguồn dữ liệu vào là gì; (2) Thêm fallback trong `crossref.py`: khi `subject` rỗng, dùng Crossref `type` (vd. "journal-article" → "journal article") làm category thay thế, vì trường này gần như luôn có mặt (100% trong 24 record đã fetch).
- **Cách xác minh:** Chạy lại `evaluation.testset.build_test_set` và kiểm tra 12/12 câu đều có `ground_truth` là chuỗi không rỗng (xem `data/eval/test_set.json`); chạy lại `script/run_phase1.py` thành công, không còn crash.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Eval set chỉ có 12 câu trên 3/24 tài liệu | Độ bao phủ corruption/retrieval hạn chế, dễ bị nhiễu nếu 1 câu sai | Tăng `_MAX_REPRESENTATIVE_PAPERS` trong `testset.py` lên 6–8 và đo lại xem `retrieval_hit_rate` có ổn định hơn không |
| Ragas chưa được bật (`RUN_RAGAS` mặc định tắt) | Thiếu faithfulness/context precision để đối chiếu với token-F1/LLM judge | Chạy `RUN_RAGAS=1 python script/run_phase1.py` và bổ sung số liệu Ragas vào báo cáo |
| Kết quả fetch Crossref không cố định qua các lần chạy (API index liên tục thay đổi) | Nếu tổ chấm chạy lại `fetch_source_records`, con số baseline có thể khác | Đặt `REFRESH_SOURCE=false` (mặc định) để luôn tái sử dụng `data/raw/crossref_records.json` đã lưu, đảm bảo tái lập kết quả |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set (`data/eval/test_set.json`, không bị ghi đè).
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng (xem `report/individual_*.md`).
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
