# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Hùng Mạnh             |
| MSSV               | [MSSV]                     |
| Khóa/Lớp         | K3              |
| Tên nhóm         | K3-Day10-Data-Pipeline-Observability     |
| Vai trò chính    | Source Ingestion Owner                 |
| Repository         | https://github.com/nhmanhDev/K3_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Crossref parsing | `src/ingestion/crossref.py::parse_crossref_payload` | Raw JSON payload từ `/works` | `list[PaperRecord]` | Hoàn thành |
| Crossref fetching + retry | `src/ingestion/crossref.py::fetch_source_records` | `Settings` (query, filter, max_results) | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |
| Raw snapshot loading | `src/ingestion/crossref.py::load_raw_records` | Đường dẫn JSON snapshot | `list[PaperRecord]` (dùng lại cho repair) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Bổ sung fallback category từ Crossref `type` khi `subject` rỗng | A (`testset.py`), D (`phase1.py`) | Sửa lỗi eval set có ground_truth rỗng/NaN cho loại câu hỏi "categories" |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Gọi Crossref API với retry 429/503, backoff nhân đôi (2s→32s, tối đa 5 lần) | `fetch_source_records` | 24 bản ghi thô, không mất request nào phải retry ở lần chạy thực tế | `data/raw/crossref_response.json` (raw HTTP), `data/raw/crossref_records.json` (24 `PaperRecord`) |
| Parse payload thành `PaperRecord`, lọc record thiếu title/abstract | `parse_crossref_payload` | 24/24 record hợp lệ được giữ lại (query đã có `has-abstract:true`) | So khớp `message.items` trong raw response với `crossref_records.json` |

Output cụ thể: `data/raw/crossref_records.json` — 24 `PaperRecord` phẳng (paper_id, title, summary có tag HTML/XML còn nguyên, authors, categories, published, updated, abs_url, pdf_url, comment) — là input trực tiếp cho `cleaning.py` của A và là raw snapshot dùng để repair ở checkpoint C4.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref trả về JSON lồng nhau (author là list dict given/family, published là `date-parts` dạng `[[year, month, day]]`, subject thường rỗng), cần biến đổi thành cấu trúc phẳng `PaperRecord` mà các module sau (cleaning, index) dùng được, đồng thời phải chịu lỗi tạm thời từ API (429 Too Many Requests, 503 Service Unavailable) mà không làm sập cả pipeline.

### Cách triển khai

- `paper_id` = DOI viết thường, dùng làm khóa chính duy nhất xuyên suốt pipeline (kể cả sau corruption/repair).
- Ngày tháng (`published`, `updated`) được trích từ `date-parts` với fallback thứ tự: `published-print` → `published-online` → `published` → `issued`; `updated` fallback `indexed` → `deposited` → `created`, rồi fallback về chính `published` nếu không có.
- `categories`: ban đầu chỉ lấy `subject` (ASJC taxonomy), nhưng phát hiện 0/24 record có trường này (nhiều publisher không khai báo). Bổ sung fallback dùng Crossref `type` (vd. `journal-article` → "journal article") — trường này 100% có mặt (Counter: journal-article 15, posted-content 8, report 1).
- Retry: vòng lặp tối đa 5 lần, chỉ retry khi status code là 429/503 hoặc lỗi mạng (`requests.RequestException`), backoff nhân đôi mỗi lần.
- Lưu 2 dạng raw riêng biệt: response thô nguyên bản (audit nguồn) và records đã parse phẳng (dùng cho cleaning + repair sau này).

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `Settings` (source_query, source_filter, max_results) từ `core.config.load_settings()` |
| Output                         | `list[PaperRecord]`, ghi ra `data/raw/crossref_response.json` + `crossref_records.json` |
| Module phụ thuộc             | `core.config`, `core.utils` (normalize_whitespace, read_json, write_json) |
| Module sử dụng output        | `ingestion.cleaning.build_clean_dataframe` (A), `pipelines.phase1`/`corruption_flow` (D) khi cần repair |
| Điều kiện lỗi cần xử lý | HTTP 429/503 (retry), record thiếu DOI/title/abstract (bỏ qua), DOI trùng lặp (dedupe bằng `seen_ids`) |

### Cách xác minh

```bash
uv run python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; fetch_source_records(load_settings())"
```

- **Kết quả mong đợi:** ghi được `data/raw/crossref_response.json` và `crossref_records.json`, không raise exception.
- **Kết quả thực tế:** 24 records fetch thành công, không gặp 429/503 nên retry logic chưa được kích hoạt trong lần chạy thực tế (đã review code path thủ công để đảm bảo đúng logic).
- **Artifact/log:** `data/raw/crossref_records.json` (24 phần tử).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Trường `categories_joined` cần luôn có giá trị vì `quality.py` và eval set (`testset.py`) đều dùng nó; nhưng Crossref `subject` gần như luôn rỗng với query thực tế của nhóm.
- **Các phương án đã cân nhắc:** (1) Chấp nhận `categories_joined` rỗng và bỏ câu hỏi loại "categories" khỏi eval set; (2) Gọi thêm một API khác (vd. OpenAlex) để lấy category; (3) Fallback dùng trường `type` sẵn có trong response Crossref.
- **Phương án đã chọn:** (3) Fallback dùng `type`.
- **Lý do:** Không cần thêm nguồn dữ liệu ngoài phạm vi bài lab (giữ đúng yêu cầu "Crossref API" là nguồn duy nhất), và `type` có tỉ lệ phủ 100% trong dữ liệu thực tế, giữ được đủ 4 loại câu hỏi trong eval set như pseudo-code yêu cầu.
- **Bằng chứng quyết định phù hợp:** Sau khi thêm fallback, `data/eval/test_set.json` có 12/12 câu với `ground_truth` không rỗng (kiểm tra bằng script), và `data/quality/baseline_quality.json` không còn cảnh báo liên quan.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `TypeError: expected string or bytes-like object, got 'float'` khi chạy `evaluate_pipeline` (xảy ra ở bước tích hợp của D, nhưng nguyên nhân gốc nằm ở dữ liệu ingestion/cleaning).
- **Lệnh hoặc bước tái hiện:** Đọc `papers_clean.csv` bằng `pd.read_csv` rồi gọi `build_test_set` trên dataframe đó.
- **Nguyên nhân gốc:** `categories_joined` rỗng (do Crossref `subject` không có) bị pandas biến thành `NaN` (float) khi round-trip qua CSV, kết hợp với việc `categories` chưa có fallback.
- **Cách xử lý:** Thêm fallback `type` → `categories` trong `parse_crossref_payload` (mô tả ở mục 5) để giá trị không bao giờ rỗng ngay từ ingestion, giảm khả năng gặp lại vấn đề NaN dù dữ liệu có đi qua CSV hay không.
- **Cách xác minh sau khi sửa:** Re-parse raw response đã lưu sẵn (không cần fetch lại API), rebuild clean data + test set, kiểm tra không còn giá trị rỗng/NaN.
- **Điều học được:** Dữ liệu thật từ API bên ngoài luôn có trường "tưởng như bắt buộc" nhưng thực tế rỗng phần lớn — cần kiểm tra tỉ lệ phủ (coverage) của từng trường trên dữ liệu thật trước khi thiết kế contract, thay vì giả định theo tài liệu API.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Dữ liệu đi từ Crossref (`/works` REST API) → `fetch_source_records` lưu raw response + parse thành `PaperRecord` → `cleaning.build_clean_dataframe` chuẩn hóa thành dataframe → `LocalEmbeddingIndex.build` encode `text_for_embedding` bằng MiniLM và nạp vào ChromaDB.
2. Evaluation set (`test_set.json`) chứa `ground_truth_doc_ids` là `paper_id` (DOI) của đúng tài liệu chứa câu trả lời; khi agent trả lời, hệ thống so `retrieved_doc_ids` (từ ChromaDB) với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so `answer` với `ground_truth` để tính `token_f1`/LLM judge.
3. Quality checks kiểm tra tại một thời điểm (completeness/uniqueness/validity/freshness của dataframe hiện tại), còn freshness monitoring là một phần trong đó tập trung riêng vào `age_days` so với ngưỡng `freshness_threshold_days`.
4. Phải dùng cùng test set vì nếu đổi câu hỏi giữa 3 trạng thái, sự thay đổi metric có thể do câu hỏi khác nhau chứ không phải do corruption/repair — làm mất khả năng so sánh nhân quả.
5. Repair thành công khi `repaired_metrics.json` khớp lại với `baseline_metrics.json` (không cần giống 100% nhưng phải phục hồi rõ rệt so với `corrupted_metrics.json`), và `repaired_quality.json`/`repaired_freshness.json` PASS trở lại.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.67 |     1.00 | Corruption phá exact-title lookup (title truncate) và raw snapshot đủ để phục hồi hoàn toàn |
| `mean_token_f1`      |     1.00 |      0.51 |     1.00 | Blank summary + stale date trực tiếp làm sai answer text |
| `judge_accuracy`     |     1.00 |      0.50 |     1.00 | Nhất quán với token_f1 |
| `mean_judge_score`   |        5 |      3.08 |        5 | Gemini judge phản ánh đúng mức độ hỏng dữ liệu |
| Quality checks         |     PASS |      FAIL |     PASS | FAIL ở uniqueness/validity/freshness — đúng như 3 trong 6 kịch bản corruption gây ra |
| Freshness status       |    Fresh |     Stale |    Fresh | Stale date corruption gây ra chính xác 2 stale rows |

### Kết luận từ số liệu

1. Corruption làm hỏng trường nguồn (title/summary/published) → quality/freshness signal chuyển sang FAIL → retrieval và answer metric giảm tương ứng.
2. Repair đọc lại raw snapshot đã lưu từ bước ingestion (không gọi lại API) → build lại đúng cleaning logic → mọi signal phục hồi 100% về baseline.

Corruption ảnh hưởng rõ nhất: **title truncate**, vì `qa.answer_question` dựa vào exact-title match trong dấu nháy đơn để đảm bảo retrieval chính xác — cắt ngắn title phá vỡ cơ chế này, buộc hệ thống rơi về semantic search kém chính xác hơn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw artifact (response thô + record đã parse) là tài sản quan trọng nhất của pipeline — nó là thứ duy nhất cho phép "undo" mọi lỗi ở tầng cleaning/corruption mà không cần phụ thuộc vào API bên ngoài còn khả dụng hay không.
2. Field "tưởng như luôn có" theo tài liệu API (Crossref `subject`) có thể rỗng gần như hoàn toàn trên dữ liệu thật — luôn kiểm tra coverage thực tế trước khi thiết kế contract.
3. Retry với backoff cần giới hạn số lần thử rõ ràng, tránh vòng lặp vô hạn khi API thật sự down.

### Nếu có thêm thời gian

Thêm cache theo ngày cho raw response (vd. không fetch lại nếu đã fetch trong 24h) để giảm tải lên Crossref API khi cả nhóm cùng chạy thử nhiều lần, đo bằng số lần gọi API thực tế giảm so với hiện tại (mỗi lần chạy `refresh_source=true` đều gọi lại).

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hùng Mạnh
**Ngày xác nhận:** 2026-08-06
