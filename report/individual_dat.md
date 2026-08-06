# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Minh Đạt             |
| MSSV               | [MSSV]                     |
| Khóa/Lớp         | K3              |
| Tên nhóm         | K3-Day10-Data-Pipeline-Observability     |
| Vai trò chính    | Data Model & Eval Set Owner                 |
| Repository         | https://github.com/nhmanhDev/K3_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Cleaning pipeline | `src/ingestion/cleaning.py::build_clean_dataframe` | `list[PaperRecord]` từ Mạnh | `data/clean/papers_clean.csv`, `papers_clean.json` | Hoàn thành |
| Frozen evaluation set | `src/evaluation/testset.py::build_test_set` | Clean dataframe | `data/eval/test_set.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Debug lỗi NaN trong ground_truth khi tích hợp | Mai Anh (`phase1.py`) | Xác định nguyên nhân là CSV round-trip biến `""` thành NaN, phối hợp với Mạnh để thêm fallback category |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Strip HTML/XML, ghép authors/categories, tính `age_days`, tạo `text_for_embedding` | `build_clean_dataframe` | 24/24 record raw → 24 dòng clean hợp lệ | `data/clean/papers_clean.csv`, so khớp với `data/raw/crossref_records.json` |
| Sinh 12 câu hỏi eval cố định trên 3 tài liệu đại diện | `build_test_set` | `data/eval/test_set.json`, mỗi câu có đủ `id/question_type/question/ground_truth/ground_truth_doc_ids` | `retrieval_hit_rate = 1.00` ở baseline chứng minh câu hỏi bám sát dữ liệu thật |

Output cụ thể: `data/eval/test_set.json` — 12 câu hỏi (4 loại: summary/authors/date/categories × 3 tài liệu), mỗi câu đều nhúng title trong dấu nháy đơn để tận dụng cơ chế exact-title lookup có sẵn trong `retrieval.qa.answer_question`, đảm bảo baseline đạt hit rate tối đa và corruption sau này có "chỗ để giảm".

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Dữ liệu Crossref thô chứa thẻ XML/JATS trong title/abstract (`<jats:p>`, `<b>`...), author là danh sách dict lồng nhau, ngày tháng chưa chuẩn hóa. Cần biến thành dataframe "sẵn sàng để embed" với schema cố định, đồng thời phải sinh ra bộ câu hỏi đánh giá vừa thực tế (có đáp án đúng trong data) vừa đóng băng được để dùng lại cho cả 3 trạng thái baseline/corrupted/repaired.

### Cách triển khai

- Cleaning dùng regex `<[^>]+>` để bóc tag, sau đó `normalize_whitespace` để gộp khoảng trắng thừa.
- Loại bỏ record nếu: không có title sau khi strip tag, hoặc summary < 100 ký tự, hoặc không parse được ngày published/updated — đảm bảo mọi dòng còn lại đều có `age_days` là số nguyên hợp lệ (điều kiện tiên quyết để quality/freshness check không bị lỗi kiểu dữ liệu).
- `text_for_embedding` ghép đúng format `Title: {title} | Authors: {authors_joined} | Summary: {summary}` theo đúng contract của bài lab.
- Test set: chọn 3 tài liệu đại diện bằng cách lấy chỉ số trải đều (`_pick_representative_indices`, dùng `linspace`-style step) thay vì chỉ lấy 3 dòng đầu, để tránh thiên lệch nếu dữ liệu được sort theo ngày.
- Mỗi câu hỏi được thiết kế để khớp đúng nhánh trích xuất tương ứng trong `retrieval.qa._extract_answer` (dò chuỗi "who authored" / "when was" / "what categories" / mặc định lấy câu đầu của summary), đảm bảo ground_truth và cách agent trả lời nhất quán với nhau ở baseline.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `list[PaperRecord]` (cleaning), `pd.DataFrame` đã clean (testset) |
| Output                         | `pd.DataFrame` theo schema contract (cleaning); `list[dict]` 12 câu hỏi ghi ra JSON (testset) |
| Module phụ thuộc             | `core.utils` (normalize_whitespace, compact_join, first_sentence, write_json) |
| Module sử dụng output        | `retrieval.index` (embed `text_for_embedding`), `observability.quality` (age_days, title, summary), `evaluation.metrics` (test_set) |
| Điều kiện lỗi cần xử lý | Giá trị NaN/rỗng khi field đến từ nguồn không đảm bảo (CSV round-trip) — xử lý bằng `_safe_str()` |

### Cách xác minh

```bash
uv run python -c "
from core.config import load_settings
from ingestion.crossref import load_raw_records
from ingestion.cleaning import build_clean_dataframe
from evaluation.testset import build_test_set
from core.utils import now_utc
s = load_settings()
records = load_raw_records(s.paths.raw_records_json)
df = build_clean_dataframe(records, now_utc())
print(len(df))
build_test_set(df, s.paths.eval_testset)
"
```

- **Kết quả mong đợi:** 24 dòng clean, 12 câu hỏi hợp lệ không NaN.
- **Kết quả thực tế:** Đúng như kỳ vọng sau khi vá lỗi NaN (mục 6).
- **Artifact/log:** `data/clean/papers_clean.json`, `data/eval/test_set.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định câu hỏi eval nên tự do (LLM-generated) hay theo template cố định bám sát field có sẵn.
- **Các phương án đã cân nhắc:** (1) Dùng LLM để sinh câu hỏi tự nhiên hơn từ summary; (2) Dùng template cố định theo 4 field (summary/authors/date/categories) với title nhúng trong dấu nháy đơn.
- **Phương án đã chọn:** (2) Template cố định.
- **Lý do:** Đảm bảo `ground_truth` luôn trích xuất được chính xác từ chính dữ liệu clean (không phụ thuộc LLM có thể "bịa" câu hỏi không có đáp án rõ ràng), và q trùng khớp với logic trích xuất có sẵn trong `qa._extract_answer`, giúp baseline đạt điểm tối đa một cách có kiểm soát — làm nền so sánh sạch cho corruption ở C4.
- **Bằng chứng quyết định phù hợp:** `retrieval_hit_rate = 1.00`, `mean_token_f1 = 1.00` ở baseline (`data/results/baseline_metrics.json`).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `TypeError: expected string or bytes-like object, got 'float'` tại `_token_f1` khi Mai Anh chạy `evaluate_pipeline` lần đầu.
- **Lệnh hoặc bước tái hiện:** `df = pd.read_csv(settings.paths.clean_csv)` rồi `build_test_set(df, ...)` — câu hỏi loại "categories" có `ground_truth = nan`.
- **Nguyên nhân gốc:** `categories_joined` là chuỗi rỗng `""` ở nguồn (Crossref `subject` không có), và `pd.read_csv` mặc định parse ô rỗng thành `NaN` (kiểu float) thay vì chuỗi rỗng.
- **Cách xử lý:** Thêm hàm `_safe_str()` trong `testset.py` (chuyển NaN/None thành `""` trước khi dùng), đồng thời phối hợp với Mạnh để `categories_joined` không bao giờ rỗng ngay từ ingestion (fallback `type`), giảm khả năng NaN xuất hiện ở bất kỳ đường đọc dữ liệu nào (CSV hay JSON).
- **Cách xác minh sau khi sửa:** Rebuild test set, kiểm tra script xác nhận 12/12 câu có `ground_truth` là chuỗi không rỗng; chạy lại `run_phase1.py` không còn crash.
- **Điều học được:** Không nên giả định `pd.DataFrame` giữ nguyên kiểu dữ liệu qua một vòng ghi/đọc CSV — luôn kiểm tra dữ liệu round-trip nếu pipeline có bước ghi CSV rồi đọc lại ở module khác.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref trả JSON thô → Mạnh parse thành `PaperRecord` → tôi strip HTML/chuẩn hóa thành dataframe với `text_for_embedding` → dataframe này được encode bằng MiniLM và nạp vào ChromaDB.
2. `ground_truth_doc_ids` là `paper_id` (DOI) của tài liệu chứa đáp án; khi agent retrieve, hệ thống so `retrieved_doc_ids` với danh sách này để tính hit rate, độc lập với việc answer text có đúng hay không.
3. Quality check là bức ảnh chụp tại một thời điểm (đúng/sai theo ngưỡng cố định: null, duplicate, độ dài, stale), còn freshness report tập trung riêng vào phân bố ngày xuất bản (latest/oldest/stale_rows) — hai khái niệm bổ sung cho nhau chứ không trùng lặp.
4. Test set phải cố định vì nếu sinh lại câu hỏi mỗi lần chạy, baseline/corrupted/repaired sẽ được chấm trên các câu khác nhau — không còn là phép so sánh công bằng (fair comparison) như tên bài lab yêu cầu.
5. Repair thành công khi `repaired_metrics.json` phục hồi về gần/bằng `baseline_metrics.json` và `repaired_quality.json`/`repaired_freshness.json` PASS — không chỉ dựa vào "code chạy không lỗi".

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.67 |     1.00 | Test set của tôi nhạy với corruption vì câu hỏi bám trực tiếp vào title/summary/date/categories |
| `mean_token_f1`      |     1.00 |      0.51 |     1.00 | Giảm mạnh vì 2/3 tài liệu trong eval set bị stale date, 1/3 bị blank summary |
| `judge_accuracy`     |     1.00 |      0.50 |     1.00 | Nhất quán với token_f1 |
| `mean_judge_score`   |        5 |      3.08 |        5 | — |
| Quality checks         |     PASS |      FAIL |     PASS | — |
| Freshness status       |    Fresh |     Stale |    Fresh | — |

### Kết luận từ số liệu

1. Corruption nhắm đúng vào 3 tài liệu trong eval set (`corruption_log.json.target_doc_ids_from_eval_set`) → mọi field bị hỏng đều có câu hỏi tương ứng để "bắt" được sai lệch → retrieval_hit_rate và token_f1 cùng giảm đồng thời, không riêng lẻ.
2. Repair rebuild lại đúng `build_clean_dataframe` (cùng hàm với baseline) trên raw snapshot → toàn bộ 12 câu hỏi được trả lời lại đúng như baseline.

Kết quả nào khác với kỳ vọng ban đầu: ban đầu tôi lo `retrieval_hit_rate` corrupted sẽ về 0.00 do title bị cắt hoàn toàn phá exact-match, nhưng thực tế còn 0.67 vì semantic search (ChromaDB) vẫn tìm đúng 1/3 tài liệu nhờ nội dung summary còn giữ lại phần lớn ngữ nghĩa gốc — cho thấy semantic search có khả năng chống chịu corruption tốt hơn exact-match.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Thiết kế câu hỏi eval nên bám sát cơ chế trích xuất/trả lời thực tế của hệ thống, không chỉ bám vào dữ liệu — nếu không, baseline sẽ không đạt điểm tối đa và khó phân biệt "lỗi do corruption" với "lỗi do câu hỏi mơ hồ".
2. Freshness và quality là hai lát cắt bổ sung, không thay thế nhau: một dataset có thể PASS mọi completeness/uniqueness check nhưng vẫn stale, hoặc ngược lại.
3. Dữ liệu tưởng "sạch" (24/24 record qua hết filter) vẫn có thể chứa lỗ hổng ẩn (NaN sau CSV round-trip) không lộ ra cho tới khi tích hợp toàn bộ pipeline.

### Nếu có thêm thời gian

Thêm câu hỏi loại "multi-hop" (so sánh giữa 2 tài liệu) để kiểm tra khả năng retrieval khi câu hỏi không nhúng sẵn title — đo bằng cách so `retrieval_hit_rate` của nhóm câu hỏi này với nhóm câu hỏi hiện tại.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Minh Đạt
**Ngày xác nhận:** 2026-08-06
