# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | B             |
| MSSV               | [MSSV]                     |
| Khóa/Lớp         | K3              |
| Tên nhóm         | K3-Day10-Data-Pipeline-Observability     |
| Vai trò chính    | Data Observability Owner                 |
| Repository         | https://github.com/nhmanhDev/K3_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Data quality checks | `src/observability/quality.py::run_data_quality_checks` | Dataframe clean (baseline/corrupted/repaired) + `Settings` | `data/quality/{state}_quality.json` | Hoàn thành |
| Freshness report | `src/observability/quality.py::build_freshness_report` | Dataframe clean + `Settings` | `data/quality/{state}_freshness.json` | Hoàn thành |
| Markdown reporting | `src/observability/reporting.py` (`generate_phase1_report`, `generate_corruption_report`) | Metrics/quality/freshness dict | `data/reports/phase1_report.md`, `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Mở rộng chữ ký `generate_corruption_report` để nhận thêm `baseline_quality`/`baseline_freshness` | D (`corruption_flow.py`) | Bảng so sánh 3 cột (Baseline/Corrupted/Repaired) đầy đủ cho cả quality lẫn freshness thay vì chỉ 2 cột như signature gốc |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| 5 quality check (row_count, paper_id unique/not-null, title not-null, summary length, freshness age_days) | `run_data_quality_checks` | Baseline PASS toàn bộ; Corrupted FAIL 3/5 check; Repaired PASS trở lại | `data/quality/*_quality.json` |
| Freshness report (latest/oldest published, stale rows, is_fresh) | `build_freshness_report` | Baseline/Repaired: 0/24 stale; Corrupted: 2/24 stale | `data/quality/*_freshness.json` |
| Markdown report tự động cho cả 2 phase | `reporting.py` | `phase1_report.md` (baseline), `corruption_report.md` (3-way so sánh) | `data/reports/` |

Output cụ thể: `data/reports/corruption_report.md` — bảng so sánh RAG metrics, quality pass/fail, và freshness qua 3 trạng thái, kèm cột "Corruption Δ" và "Repair Δ" tính tự động, là bằng chứng chính cho chuỗi nhân quả Corruption → Quality signal → Answer impact mà bài lab yêu cầu chứng minh.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần một cơ chế phát hiện sự cố dữ liệu độc lập với kết quả RAG (không chỉ nhìn vào answer sai mới biết có lỗi), đo được 4 quality dimension (completeness, uniqueness, validity, freshness) và tổng hợp thành cả JSON (máy đọc được) lẫn Markdown (người đọc được), tái sử dụng được cho cả 3 trạng thái baseline/corrupted/repaired mà không cần sửa code giữa các lần gọi.

### Cách triển khai

- `run_data_quality_checks` trả về `dict` có cấu trúc cố định (`passed`, `checks: [{name, dimension, passed, details}]`) để `reporting.py` và `group_report.md` có thể tham chiếu nhất quán qua 3 lần gọi (baseline/corrupted/repaired) chỉ khác `report_name`.
- Freshness tách riêng khỏi quality checks (dù cả hai đều dùng `age_days`) vì freshness cần thêm thông tin phân bố (latest/oldest/stale_rows/total_rows) mà một pass/fail đơn thuần không thể hiện được.
- `reporting.py`: mở rộng chữ ký gốc của `generate_corruption_report` (vốn chỉ nhận `corrupted_quality`/`repaired_quality`/`corrupted_freshness`/`repaired_freshness`) để thêm `baseline_quality`/`baseline_freshness`, vì checkpoint C4 yêu cầu rõ bảng so sánh **3 cột** (Baseline-Corrupted-Repaired) cho cả metrics RAG lẫn observability signal — signature gốc trong starter code không đủ tham số để làm điều đó.
- Bảng metric trong report tự tính cột "Δ" (corruption delta, repair delta) bằng phép trừ trực tiếp giữa các dict metrics, tránh phải tính tay và dễ sai sót khi cập nhật báo cáo thủ công.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `pd.DataFrame` (clean/corrupted/repaired), `Settings.freshness_threshold_days` |
| Output                         | `dict` quality/freshness ghi JSON; file `.md` report |
| Module phụ thuộc             | `core.utils` (now_utc, write_json, write_text) |
| Module sử dụng output        | `pipelines.phase1`, `pipelines.corruption_flow` (D); `group_report.md` (toàn nhóm) |
| Điều kiện lỗi cần xử lý | Dataframe rỗng (trả về payload mặc định `is_fresh=false`, `total_rows=0` thay vì crash) |

### Cách xác minh

```bash
uv run python -c "
import pandas as pd
from core.config import load_settings
from observability.quality import run_data_quality_checks, build_freshness_report
s = load_settings()
df = pd.read_json(s.paths.clean_json)
q = run_data_quality_checks(df, s, 'baseline')
f = build_freshness_report(df, s, s.paths.quality_dir / 'baseline_freshness.json')
print(q['passed'], f['is_fresh'])
"
```

- **Kết quả mong đợi:** `True True` cho dataset baseline.
- **Kết quả thực tế:** Đúng như kỳ vọng (xem `data/quality/baseline_quality.json`, `baseline_freshness.json`).
- **Artifact/log:** `data/quality/baseline_quality.json`, `data/quality/baseline_freshness.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Signature gốc của `generate_corruption_report` trong starter code chỉ nhận quality/freshness của corrupted và repaired, không có baseline — nhưng checkpoint C4 yêu cầu rõ "bảng so sánh 3 cột: Baseline - Corrupted - Repaired... cho cả metrics RAG và tín hiệu observability".
- **Các phương án đã cân nhắc:** (1) Giữ nguyên signature, chỉ so sánh 2 trạng thái (corrupted vs repaired) cho quality/freshness; (2) Mở rộng signature thêm 2 tham số `baseline_quality`/`baseline_freshness`.
- **Phương án đã chọn:** (2) Mở rộng signature.
- **Lý do:** Bám sát đúng yêu cầu minh chứng của checkpoint C4 quan trọng hơn giữ nguyên một chữ ký hàm chỉ mang tính gợi ý (pseudo-code) trong starter; vì không có thành viên nào khác phụ thuộc vào chữ ký cũ, việc mở rộng không phá vỡ contract nào.
- **Bằng chứng quyết định phù hợp:** `data/reports/corruption_report.md` mục 2 và 3 hiển thị đủ 3 dòng (Baseline/Corrupted/Repaired) cho cả quality lẫn freshness, đúng yêu cầu checkpoint.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Không có lỗi runtime trực tiếp trong phạm vi `quality.py`/`reporting.py`, nhưng ban đầu thiết kế `build_freshness_report` dùng `df["age_days"].sum()` để đếm stale rows dẫn đến kết quả sai (cộng dồn thay vì đếm số dòng vượt ngưỡng).
- **Lệnh hoặc bước tái hiện:** So sánh thủ công `stale_rows` kỳ vọng (đếm bằng mắt trên `papers_clean_corrupted.csv`, biết trước 2 dòng bị stale) với kết quả hàm trả về.
- **Nguyên nhân gốc:** Nhầm lẫn giữa "tổng age_days" và "số dòng có age_days vượt ngưỡng" — cần dùng so sánh boolean rồi `.sum()` trên mask, không phải sum trực tiếp trên cột số.
- **Cách xử lý:** Sửa thành `(age_days > threshold).sum()` để đúng ngữ nghĩa "đếm số dòng vi phạm".
- **Cách xác minh sau khi sửa:** Chạy lại trên `papers_clean_corrupted.csv`, xác nhận `stale_rows = 2` khớp đúng với 2 tài liệu bị corruption gán `published = 2000-01-01`.
- **Điều học được:** Với các phép đo dạng "đếm số dòng vi phạm ngưỡng", luôn viết rõ mask boolean trước khi `.sum()`, tránh nhầm với phép tổng hợp số liệu (aggregate) thông thường.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Dữ liệu từ Crossref → parse → clean → được `LocalEmbeddingIndex` encode và nạp vào ChromaDB; ở mỗi trạng thái (baseline/corrupted/repaired), dataframe clean tương ứng đi qua module của tôi để sinh quality + freshness report song song với việc index/evaluate.
2. Evaluation set dùng `ground_truth_doc_ids` để tính retrieval hit rate — đây là tín hiệu "output" của hệ thống RAG, khác với quality/freshness của tôi là tín hiệu "input" (đo trực tiếp trên dataframe, không cần chạy agent).
3. Quality checks trả lời "dữ liệu có đúng cấu trúc/độ đầy đủ không tại 1 thời điểm" (vd. paper_id có null/duplicate không); freshness monitoring trả lời riêng "dữ liệu có còn mới không" — một dataset có thể quality PASS nhưng freshness FAIL (nếu dữ liệu đầy đủ, không trùng, nhưng cũ) hoặc ngược lại.
4. Test set cố định để 3 lần gọi `run_data_quality_checks`/`build_freshness_report`/`evaluate_pipeline` chỉ khác nhau ở dataframe đầu vào, không khác ở câu hỏi — nhờ vậy chênh lệch số liệu chỉ phản ánh đúng 1 biến số (trạng thái dữ liệu).
5. Repair được coi là thành công khi cả `*_quality.json.passed` và `*_freshness.json.is_fresh` đều quay về `true`, không chỉ dựa vào metric RAG.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.67 |     1.00 | Ngoài phạm vi trực tiếp của tôi, nhưng khớp với quality signal FAIL |
| `mean_token_f1`      |     1.00 |      0.51 |     1.00 | — |
| `judge_accuracy`     |     1.00 |      0.50 |     1.00 | — |
| `mean_judge_score`   |        5 |      3.08 |        5 | — |
| Quality checks         |     PASS |      FAIL |     PASS | FAIL đúng 3 dimension: uniqueness (duplicate paper_id), validity (summary < 100 ký tự), freshness (stale date) |
| Freshness status       |    Fresh |     Stale (2/24) |    Fresh | Đúng khớp với số document bị gán stale date trong corruption log |

### Kết luận từ số liệu

1. **Corruption → quality/freshness FAIL → answer metric giảm:** `corrupted_quality.json` liệt kê rõ 3 check FAIL (`paper_id_not_null_and_unique`, `summary_min_length`, `freshness_age_days`); đây chính xác là 3 trong 6 kịch bản corruption của C (duplicate rows, blank summary, stale date) — mỗi FAIL tương ứng 1-1 với 1 kịch bản, không phải suy đoán.
2. **Repair → quality/freshness PASS trở lại → answer metric phục hồi:** `repaired_quality.json`/`repaired_freshness.json` đều PASS, đồng thời `repaired_metrics.json` khớp lại baseline — chứng minh quality/freshness signal là chỉ báo sớm đáng tin cậy cho chất lượng RAG cuối cùng.

Corruption ảnh hưởng rõ nhất đến observability signal: **duplicate_rows**, vì đây là check duy nhất chuyển từ PASS baseline sang FAIL mà không cần đến bất kỳ ngưỡng số nào (chỉ cần > 0 duplicate là FAIL ngay), khiến nó là tín hiệu "nhạy" nhất trong 5 check.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Data quality và data freshness là hai trục quan sát độc lập, cần thiết kế check riêng cho từng trục thay vì gộp chung thành một điểm số duy nhất — nếu không sẽ mất khả năng chẩn đoán "lỗi ở đâu".
2. Report tự động (JSON + Markdown) chỉ đáng tin nếu cấu trúc dict đầu ra ổn định qua nhiều lần gọi — thiết kế contract dict rõ ràng ngay từ đầu giúp `reporting.py` không phải sửa lại khi thêm trạng thái mới (baseline → corrupted → repaired).
3. Một signature hàm trong starter code chỉ là gợi ý, không phải hợp đồng bất biến — khi yêu cầu checkpoint không khớp với signature gợi ý, nên ưu tiên sửa signature miễn là không phá vỡ contract với các thành viên khác.

### Nếu có thêm thời gian

Tích hợp Great Expectations (đã có sẵn trong `pyproject.toml` nhưng chưa dùng, thư mục `data/quality/gx/` còn trống) để có thêm expectation suite chuẩn hóa, đo bằng số lượng expectation PASS/FAIL hiển thị trực tiếp trong report thay vì chỉ 5 check tự viết tay.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** B
**Ngày xác nhận:** 2026-08-06
