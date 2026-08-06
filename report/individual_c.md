# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | C             |
| MSSV               | [MSSV]                     |
| Khóa/Lớp         | K3              |
| Tên nhóm         | K3-Day10-Data-Pipeline-Observability     |
| Vai trò chính    | Corruption & Repair Owner                 |
| Repository         | https://github.com/nhmanhDev/K3_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Controlled corruption | `src/ingestion/corruption.py::corrupt_clean_dataframe` | Clean dataframe (baseline) + `data/eval/test_set.json` | `data/clean/papers_clean_corrupted.csv/.json`, `data/results/corruption_log.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Xác nhận cùng D rằng corruption phải đọc `test_set.json` để đảm bảo overlap | D (`corruption_flow.py`) | Đồng thuận: `corrupt_clean_dataframe` tự load test set bên trong thay vì nhận qua tham số, để đảm bảo overlap dù ai gọi hàm |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Implement 6 kịch bản corruption (vượt yêu cầu tối thiểu 3) | `corrupt_clean_dataframe` | `corruption_log.json` ghi rõ từng kịch bản + `affected_paper_ids` | `data/results/corruption_log.json` |
| Đảm bảo corruption trúng đích vào eval set | `_load_frozen_eval_doc_ids` | 3/3 tài liệu trong `ground_truth_doc_ids` đều bị ít nhất 1 kịch bản tác động | `corruption_log.json.target_doc_ids_from_eval_set` khớp 100% với `test_set.json` |

Output cụ thể: `data/results/corruption_log.json` — log có `random_seed=42` (đảm bảo reproducible), liệt kê 6 scenario với `affected_paper_ids` cụ thể, là bằng chứng trực tiếp cho việc corruption "cố tình" chứ không ngẫu nhiên vô định, và là input để D đối chiếu trong `corruption_report.md`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Bài lab cảnh báo rõ: nếu corruption không "đụng trúng" tài liệu nằm trong bộ câu hỏi test frozen, metrics RAG sẽ không đổi và toàn bộ thí nghiệm mất ý nghĩa. Cần thiết kế corruption vừa đa dạng (nhiều loại lỗi thực tế) vừa có kiểm soát (đảm bảo overlap, log lại đầy đủ để tái lập).

### Cách triển khai

- `_load_frozen_eval_doc_ids()`: tự load `Settings` và đọc `data/eval/test_set.json` ngay bên trong `corruption.py`, trích toàn bộ `ground_truth_doc_ids` thành một `set`. Quyết định để hàm tự đọc thay vì nhận qua tham số nhằm đảm bảo bất kỳ ai gọi `corrupt_clean_dataframe` (kể cả gọi độc lập ngoài `corruption_flow.py`) cũng không thể vô tình bỏ qua yêu cầu overlap.
- 6 kịch bản, chia thành 2 nhóm:
  - Nhóm nhắm trực tiếp vào 3 tài liệu trong eval set: blank summary (1 tài liệu), stale date (2 tài liệu còn lại), title truncate (cả 3 tài liệu) — đảm bảo mọi loại câu hỏi (summary/authors/date/categories) đều có ít nhất 1 field nguồn bị hỏng.
  - Nhóm bổ sung để tăng độ đa dạng và tác động lên quality/completeness nói chung: noise injection (3 tài liệu ngoài eval set + 1 trong eval set), duplicate rows (1 tài liệu trong eval set + 1 ngoài), drop latest records (2 tài liệu ngoài eval set, tránh xóa hẳn khả năng trả lời các câu hỏi frozen).
- Dùng `random.Random(42)` (seed cố định) cho phần chọn mẫu ngẫu nhiên (noise injection) để kết quả tái lập được giữa các lần chạy.
- Sau khi sửa `title`/`summary`, bắt buộc rebuild lại `text_for_embedding` và `summary_chars` cho toàn bộ dataframe — nếu quên bước này, corruption sẽ không lan tới embedding/retrieval mà chỉ lộ ra ở quality check, làm mất đi phần "ảnh hưởng đến agent" mà bài lab yêu cầu chứng minh.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `pd.DataFrame` clean (baseline), file `data/eval/test_set.json` (đọc ngầm) |
| Output                         | `pd.DataFrame` đã corrupt + `data/results/corruption_log.json` |
| Module phụ thuộc             | `core.config.load_settings`, `core.utils` (read_json, write_json, now_utc) |
| Module sử dụng output        | `pipelines.corruption_flow` (D) — index lại bằng dataframe này rồi evaluate |
| Điều kiện lỗi cần xử lý | `test_set.json` chưa tồn tại (fallback `target_ids = set()`, vẫn chọn tài liệu đầu tiên làm mục tiêu blank summary để không bị rỗng hoàn toàn) |

### Cách xác minh

```bash
uv run python -c "
import pandas as pd
from core.config import load_settings
from ingestion.corruption import corrupt_clean_dataframe
s = load_settings()
df = pd.read_csv(s.paths.clean_csv)
corrupted = corrupt_clean_dataframe(df, s.paths.corruption_log)
print(len(df), '->', len(corrupted))
"
```

- **Kết quả mong đợi:** Log ghi 6 scenario, `target_doc_ids_from_eval_set` có 3 phần tử khớp với test set.
- **Kết quả thực tế:** Đúng như kỳ vọng — xem `data/results/corruption_log.json`.
- **Artifact/log:** `data/results/corruption_log.json`, `data/clean/papers_clean_corrupted.csv`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Chữ ký hàm gốc trong starter code là `corrupt_clean_dataframe(df, output_log_path)` — không có tham số nào cho phép truyền test set hoặc danh sách tài liệu cần nhắm tới.
- **Các phương án đã cân nhắc:** (1) Thêm tham số `target_doc_ids` vào chữ ký hàm, buộc caller (D) phải tự đọc test set rồi truyền vào; (2) Giữ nguyên chữ ký, để hàm tự đọc `data/eval/test_set.json` bên trong bằng `load_settings()`.
- **Phương án đã chọn:** (2) Tự đọc bên trong.
- **Lý do:** Giữ nguyên contract chữ ký hàm đã được thống nhất ở checkpoint C1 (không phá interface mà D đã dựa vào để viết `corruption_flow.py`), đồng thời đảm bảo overlap là "bất biến" của hàm — không phụ thuộc vào việc caller có nhớ truyền đúng tham số hay không.
- **Bằng chứng quyết định phù hợp:** Corruption thực sự trúng đích: cả 3/3 tài liệu trong `ground_truth_doc_ids` đều bị ít nhất 1 kịch bản tác động, dẫn tới `retrieval_hit_rate` giảm rõ rệt (1.00 → 0.67) thay vì giữ nguyên.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi review log lần đầu, thấy `drop_latest_records.affected_paper_ids` liệt kê cùng một `paper_id` hai lần (`["10.1111/exsy.70341", "10.1111/exsy.70341"]`), trông giống lỗi trùng lặp trong code.
- **Lệnh hoặc bước tái hiện:** Đọc `data/results/corruption_log.json` sau khi chạy `corrupt_clean_dataframe`.
- **Nguyên nhân gốc:** Không phải bug — đây là hệ quả hợp lệ của việc 2 kịch bản chạy tuần tự: `duplicate_rows` đã nhân đôi đúng dòng `10.1111/exsy.70341` (vì nó được chọn ngẫu nhiên làm "1 tài liệu khác" để duplicate); sau đó `drop_latest_records` sort theo `published` và 2 dòng đầu (cả bản gốc lẫn bản duplicate của cùng `paper_id`, do published giống hệt nhau) đều rơi vào diện bị xóa vì không nằm trong target_ids.
- **Cách xử lý:** Không sửa code (hành vi đúng theo thiết kế), nhưng bổ sung ghi chú trong log/báo cáo để giải thích rõ ràng, tránh người đọc report hiểu nhầm là lỗi.
- **Cách xác minh sau khi sửa:** Đối chiếu `total_rows_before=24`, `+2` (duplicate) `-2` (drop) `= total_rows_after=24` — số học khớp chính xác, xác nhận không có tác dụng phụ ngoài ý muốn.
- **Điều học được:** Khi nhiều bước biến đổi dữ liệu chạy tuần tự trên cùng một dataframe, cần luôn đối chiếu tổng số dòng trước/sau (invariant check) để phân biệt "hành vi giao thoa hợp lệ giữa các bước" với "bug thực sự".

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Dữ liệu sạch (từ A) là input duy nhất của corruption; corruption không bao giờ động vào `data/raw/` — đây chính là điều kiện để repair sau này còn nguồn để quay lại.
2. Evaluation set không tự thay đổi qua các trạng thái, nhưng `ground_truth_doc_ids` của nó chính là "bản đồ" để tôi biết nên corrupt tài liệu nào để đo được tác động — nếu không tham chiếu test set, corruption có thể "trớt quớt" hoàn toàn.
3. Quality checks là phép đo tĩnh trên dataframe (đúng/sai theo ngưỡng); freshness monitoring là một khía cạnh hẹp hơn, chỉ nhìn vào trục thời gian (age_days) — corruption của tôi cố tình tác động cả hai (stale date ảnh hưởng freshness, duplicate/blank ảnh hưởng quality chung).
4. Test set cố định để đảm bảo corruption của tôi được đánh giá đúng "trước và sau" trên cùng thước đo — nếu D vô tình sinh lại test set mới sau khi tôi đã log corruption theo test set cũ, toàn bộ `target_doc_ids_from_eval_set` sẽ sai lệch.
5. Repair thành công dựa trên: (a) `repaired_metrics.json` phục hồi gần bằng baseline, (b) `repaired_quality.json`/`repaired_freshness.json` PASS, và quan trọng nhất — (c) repair phải xuất phát từ `data/raw/crossref_records.json` (raw snapshot), không phải từ việc "vá tay" trực tiếp lên `papers_clean_corrupted.csv`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.67 |     1.00 | Đúng 1/3 tài liệu (title truncate) vẫn được tìm thấy nhờ semantic search bù đắp |
| `mean_token_f1`      |     1.00 |      0.51 |     1.00 | Giảm hơn cả retrieval vì answer text bị sai theo field bị hỏng |
| `judge_accuracy`     |     1.00 |      0.50 |     1.00 | — |
| `mean_judge_score`   |        5 |      3.08 |        5 | — |
| Quality checks         |     PASS |      FAIL |     PASS | FAIL đúng 3/5 check — khớp 1-1 với 3 trong 6 kịch bản tôi tạo ra |
| Freshness status       |    Fresh |     Stale (2/24) |    Fresh | Khớp chính xác với 2 tài liệu bị stale_date |

### Kết luận từ số liệu

1. Corruption nhắm trúng đích (title truncate + blank summary) → phá vỡ cơ chế exact-title lookup trong `qa.answer_question` → `retrieval_hit_rate` giảm 33 điểm phần trăm.
2. Repair đọc lại raw snapshot (không phải sửa trực tiếp file corrupted) → toàn bộ metrics và quality/freshness phục hồi 100%, chứng minh corruption chỉ là lỗi ở tầng dữ liệu trung gian, không phải lỗi không thể đảo ngược.

Corruption ảnh hưởng rõ nhất đến retrieval: **title truncate**, vì đây là kịch bản duy nhất tấn công trực tiếp cơ chế exact-match mà baseline dựa vào để đạt hit rate tuyệt đối; các kịch bản còn lại (blank summary, stale date) chủ yếu ảnh hưởng đến answer text hơn là khả năng tìm thấy tài liệu.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Corruption ngẫu nhiên không có mục tiêu rất dễ "vô hại" trên giấy tờ — phải chủ động tham chiếu ngược lại eval set để đảm bảo đo được tác động thật.
2. Nhiều bước biến đổi dữ liệu chạy tuần tự có thể tạo ra hiệu ứng giao thoa (một dòng bị cả duplicate lẫn drop) — cần luôn kiểm tra invariant (tổng số dòng) để phân biệt bug với hành vi giao thoa hợp lệ.
3. Corruption và repair chỉ có ý nghĩa khoa học nếu raw snapshot được bảo toàn tuyệt đối — bất kỳ thao tác nào vô tình ghi đè `data/raw/` sẽ làm mất khả năng chứng minh "phục hồi từ nguồn đáng tin cậy".

### Nếu có thêm thời gian

Thêm kịch bản corruption "encoding lỗi" (vd. mojibake trên summary có ký tự Unicode) để kiểm tra xem MiniLM embedding có nhạy với lỗi encoding hay không — đo bằng cosine similarity giữa embedding gốc và embedding bị lỗi encoding.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** C
**Ngày xác nhận:** 2026-08-06
