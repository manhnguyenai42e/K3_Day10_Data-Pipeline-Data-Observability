# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | D             |
| MSSV               | [MSSV]                     |
| Khóa/Lớp         | K3              |
| Tên nhóm         | K3-Day10-Data-Pipeline-Observability     |
| Vai trò chính    | Integration & Comparison Owner                 |
| Repository         | https://github.com/nhmanhDev/K3_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Baseline pipeline | `src/pipelines/phase1.py::main` | Toàn bộ module của Mạnh/A/B | `data/results/baseline_*`, `data/reports/phase1_report.md` | Hoàn thành |
| Corruption/repair flow | `src/pipelines/corruption_flow.py::main` | Module của C + baseline artifacts | `data/results/corrupted_*`, `repaired_*`, `data/reports/corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Phát hiện và báo lỗi NaN trong ground_truth khi chạy tích hợp lần đầu | A (`testset.py`), Mạnh (`crossref.py`) | Xác định root cause, phối hợp sửa fallback category + `_safe_str()` |
| Đề xuất mở rộng signature `generate_corruption_report` | B (`reporting.py`) | Có đủ baseline_quality/baseline_freshness để làm bảng so sánh 3 cột đúng yêu cầu C4 |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Ghép ingest → clean → index → eval → quality → report thành 1 lệnh chạy | `phase1.py::main`, `script/run_phase1.py` | `retrieval_hit_rate=1.00`, quality PASS, freshness fresh | `data/reports/phase1_report.md` |
| Ghép corrupt → evaluate → repair (từ raw) → evaluate → compare | `corruption_flow.py::main`, `script/run_corruption_flow.py` | Baseline→Corrupted→Repaired: 1.00→0.67→1.00 | `data/reports/corruption_report.md` |

Output cụ thể: `data/reports/corruption_report.md` là sản phẩm tích hợp cuối cùng, tổng hợp output của cả 4 thành viên khác (raw/clean của Mạnh-A, quality/freshness/report của B, corruption log của C) thành một bằng chứng duy nhất chứng minh chuỗi nhân quả Corruption → Quality signal → Answer impact → Repair recovery.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

`phase1.py` và `corruption_flow.py` là 2 file duy nhất gọi trực tiếp đến code của cả 4 thành viên khác — bất kỳ sai lệch nhỏ nào về contract (tên cột, kiểu dữ liệu, thứ tự gọi hàm) đều khiến pipeline không chạy được. Cần đảm bảo: (a) mỗi trạng thái (baseline/corrupted/repaired) dùng đúng 1 collection ChromaDB riêng để không ghi đè lẫn nhau, (b) test set không bị sinh lại giữa các lần chạy, (c) repair phải xuất phát từ raw snapshot chứ không phải từ file corrupted.

### Cách triển khai

- `phase1.py`: kiểm tra `settings.paths.raw_records_json.exists()` trước khi quyết định gọi `fetch_source_records` (gọi API thật) hay `load_raw_records` (dùng lại snapshot đã lưu) — tránh gọi lại Crossref API không cần thiết mỗi lần chạy thử.
- Tương tự với `eval_testset.exists()`: nếu file đã có, **không** gọi lại `build_test_set` — đây là cơ chế "đóng băng" test set bắt buộc theo yêu cầu bài lab.
- `corruption_flow.py`: gọi `LocalEmbeddingIndex.build(df, settings, embeddings_output_path=...)` với 3 đường dẫn manifest khác nhau (`embeddings_json`/`corrupted_embeddings_json`/`repaired_embeddings_json`) — `LocalEmbeddingIndex._derive_collection_name` tự map đường dẫn này sang đúng `collection_name` (papers-baseline/-corrupted/-repaired) đã định nghĩa sẵn trong `Settings`, đảm bảo 3 trạng thái có 3 collection ChromaDB độc lập, không ghi đè lên nhau dù dùng chung 1 thư mục persist (`data/chroma/`).
- Repair: gọi `ingestion.crossref.load_raw_records(settings.paths.raw_records_json)` rồi `ingestion.cleaning.build_clean_dataframe(...)` — **cùng hàm cleaning** dùng ở baseline, đảm bảo repair không phải là "sửa tay" mà là tái chạy đúng pipeline chuẩn trên raw snapshot chưa từng bị corruption.
- Cả 2 file đều chạy `run_data_quality_checks` + `build_freshness_report` cho từng trạng thái trước khi gọi `reporting.py` để tổng hợp — đảm bảo report luôn phản ánh đúng dữ liệu vừa được index/evaluate, không dùng lại số liệu cũ.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Toàn bộ output của Mạnh (raw), A (clean+testset), B (quality+reporting), C (corruption) |
| Output                         | `data/results/*_metrics.json`, `*_answers.json`, `data/reports/phase1_report.md`, `corruption_report.md` |
| Module phụ thuộc             | Tất cả module trong `src/` (trừ `retrieval/` dùng nguyên bản từ starter) |
| Module sử dụng output        | `group_report.md` (số liệu tổng hợp), tổ chấm bài |
| Điều kiện lỗi cần xử lý | Chạy `corruption_flow.py` khi chưa có baseline (`clean_csv`/`baseline_metrics` chưa tồn tại) → raise `RuntimeError` rõ ràng thay vì lỗi mơ hồ giữa chừng |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Cả 2 lệnh chạy xong không lỗi, in ra dòng tóm tắt metrics cuối cùng.
- **Kết quả thực tế:** `Phase 1 baseline complete: 24 clean records, retrieval_hit_rate=1.00, ... quality_passed=True, freshness_is_fresh=True`; `Corruption flow complete. retrieval_hit_rate: baseline=1.00 -> corrupted=0.67 -> repaired=1.00; quality: corrupted_passed=False, repaired_passed=True`.
- **Artifact/log:** `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định nơi gọi `run_data_quality_checks`/`build_freshness_report` cho baseline trong `corruption_flow.py` — gọi lại từ đầu hay tái sử dụng kết quả đã có sẵn từ `phase1.py`.
- **Các phương án đã cân nhắc:** (1) Đọc lại `data/quality/baseline_quality.json`/`baseline_freshness.json` đã được `phase1.py` ghi sẵn; (2) Tính lại từ đầu trên `baseline_df` ngay trong `corruption_flow.py`.
- **Phương án đã chọn:** (2) Tính lại từ đầu.
- **Lý do:** Đảm bảo `corruption_flow.py` có thể chạy độc lập, tự-đủ (self-contained) và luôn phản ánh đúng trạng thái hiện tại của `papers_clean.csv` tại thời điểm chạy — nếu chỉ đọc lại file JSON cũ, dữ liệu quality/freshness baseline có thể "lệch pha" nếu ai đó chạy lại `phase1.py` với dữ liệu mới mà quên chạy lại `corruption_flow.py`.
- **Bằng chứng quyết định phù hợp:** `baseline_quality.json`/`baseline_freshness.json` trong report luôn khớp 100% với `papers_clean.csv` hiện tại, không có rủi ro stale cache.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Lần chạy `script/run_phase1.py` đầu tiên báo `TypeError: expected string or bytes-like object, got 'float'` tại `_token_f1` trong `evaluation/metrics.py`, dừng pipeline giữa chừng (sau khi đã gọi Gemini judge 4 lần).
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_phase1.py` (khi `data/eval/test_set.json` đã được sinh trước đó từ một dataframe đọc qua `pd.read_csv`).
- **Nguyên nhân gốc:** `test_set.json` đã đóng băng từ trước chứa 1 giá trị `ground_truth = NaN` (câu hỏi "categories" của 1 tài liệu có `categories_joined` rỗng, bị pandas CSV round-trip biến thành float NaN).
- **Cách xử lý:** Không sửa trong `phase1.py` (vì lỗi không nằm ở tầng integration) — phối hợp với A vá `testset.py` (`_safe_str()`) và với Mạnh vá `crossref.py` (fallback category từ `type`), sau đó xóa và tái sinh lại `test_set.json` từ dataframe in-memory (không qua CSV) trước khi chạy lại pipeline.
- **Cách xác minh sau khi sửa:** `script/run_phase1.py` chạy hết toàn bộ 12 câu hỏi, in ra dòng tóm tắt cuối cùng không còn traceback.
- **Điều học được:** Với vai trò integration, việc "chạy thử sớm và thường xuyên" (chạy pipeline ngay khi từng module vừa xong, thay vì đợi tất cả xong mới ghép) giúp phát hiện lỗi tương tác giữa các module (ở đây là CSV round-trip) sớm hơn nhiều so với chỉ test từng module riêng lẻ.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref API → raw response/records (Mạnh) → clean dataframe (A) → `LocalEmbeddingIndex.build` encode `text_for_embedding` bằng MiniLM và nạp vào ChromaDB collection tương ứng — toàn bộ chuỗi này được `phase1.py` gọi tuần tự trong 1 lần `main()`.
2. `test_set.json` chứa `ground_truth_doc_ids`; `evaluation.metrics.evaluate_pipeline` gọi `retrieval.qa.answer_question` cho từng câu, so `retrieved_doc_ids` với `ground_truth_doc_ids` để tính hit rate, và so `answer` với `ground_truth` bằng token F1 + Gemini judge.
3. Quality checks (uniqueness/completeness/validity) là điều kiện tĩnh trên dataframe tại 1 thời điểm; freshness monitoring là một tín hiệu con tách riêng (dựa hoàn toàn vào `age_days`) nhưng được đo cùng lúc với quality trong cả `phase1.py` lẫn `corruption_flow.py` để không bỏ sót trạng thái nào.
4. Test set phải cố định vì `corruption_flow.py` so sánh corrupted/repaired với **cùng** `baseline_metrics.json` đã lưu từ `phase1.py` — nếu câu hỏi khác nhau giữa 2 lần chạy, phép trừ "Corruption Δ"/"Repair Δ" trong report sẽ vô nghĩa.
5. Repair được coi là thành công dựa trên artifact: `repaired_metrics.json` ≈ `baseline_metrics.json`, và `repaired_quality.json`/`repaired_freshness.json` đều PASS — đây chính là điều kiện tôi kiểm tra trước khi coi checkpoint C4 là "qua".

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.67 |     1.00 | Pipeline tích hợp phản ánh đúng 1/3 tài liệu vẫn được tìm thấy nhờ semantic fallback |
| `mean_token_f1`      |     1.00 |      0.51 |     1.00 | — |
| `judge_accuracy`     |     1.00 |      0.50 |     1.00 | — |
| `mean_judge_score`   |        5 |      3.08 |        5 | — |
| Quality checks         |     PASS |      FAIL |     PASS | 3/5 check FAIL, khớp đúng với corruption log |
| Freshness status       |    Fresh |     Stale (2/24) |    Fresh | — |

### Kết luận từ số liệu

1. Toàn bộ chuỗi Ingestion → Cleaning → Index → Eval hoạt động đúng thiết kế: khi input (clean dataframe) bị corrupt ở tầng dữ liệu, tín hiệu lan truyền đúng thứ tự quality/freshness FAIL trước, rồi mới tới retrieval/answer metric giảm — không có bước nào "che giấu" lỗi.
2. Repair chứng minh tính idempotent của cleaning pipeline: cùng một hàm `build_clean_dataframe` chạy trên cùng raw input cho ra kết quả giống hệt baseline, không phụ thuộc vào việc dữ liệu đã từng bị corrupt hay chưa.

Kết quả nào khác với kỳ vọng ban đầu: tôi ban đầu lo `corruption_flow.py` sẽ tốn nhiều thời gian chạy do phải re-embed + re-evaluate 2 lần (corrupted + repaired) bằng Gemini judge, nhưng thực tế cả pipeline (bao gồm cả phase1) chạy trong vài phút vì tập dữ liệu chỉ có 24 bản ghi/12 câu hỏi — nếu scale lên vài trăm bản ghi, cần cân nhắc chạy judge song song hoặc giới hạn batch.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Vai trò integration nên bắt đầu viết khung pipeline song song với các module khác (dùng dữ liệu giả/mock trước), thay vì chờ tất cả xong mới bắt đầu ghép — nếu không sẽ là bottleneck ở cuối buổi.
2. Việc mỗi trạng thái (baseline/corrupted/repaired) có collection ChromaDB riêng (thay vì dùng chung 1 collection rồi ghi đè) là điều kiện bắt buộc để so sánh công bằng — nếu dùng chung, đánh giá corrupted có thể vô tình lẫn dữ liệu baseline còn sót trong index.
3. "Chạy thử sớm và thường xuyên" giúp bắt lỗi tương tác giữa module (như lỗi NaN qua CSV round-trip) mà việc test từng module riêng lẻ không phát hiện được.

### Nếu có thêm thời gian

Thêm một chế độ `--dry-run` cho cả 2 script để in ra checklist các bước sẽ chạy (fetch/clean/index/evaluate/report) và trạng thái file đầu vào cần thiết trước khi thực sự chạy, giúp debug nhanh hơn khi một checkpoint chưa qua được — đo bằng thời gian trung bình để xác định bước nào đang thiếu artifact.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** D
**Ngày xác nhận:** 2026-08-06
