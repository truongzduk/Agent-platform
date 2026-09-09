# AUDIT_AND_PLAN — agent-platform

Tài liệu audit hiện trạng + kế hoạch Giai đoạn 1. Mọi khẳng định về code dưới đây được trích trực tiếp từ file đã đọc thật trong repo tại thời điểm audit (2026-09-09). Không có file nào ngoài tài liệu này bị tạo/sửa/xóa.

---

## 1. HIỆN TRẠNG

### Cây thư mục thực tế (đã liệt kê bằng Glob/PowerShell, không suy đoán)

```
agent-platform/
├── .env                          [tồn tại — KHÔNG đọc nội dung theo yêu cầu bảo mật]
├── .env.example
├── .gitignore
├── README.md
├── SETUP-MAY.md
├── docker-compose.yml
├── preflight.py
├── requirements.txt
├── settings.py
├── setup.py
├── agents/
│   └── __init__.py               [rỗng]
├── evals/
│   └── __init__.py               [rỗng]
├── harness/
│   └── __init__.py               [rỗng]
├── llm/
│   └── __init__.py               [rỗng]
├── orchestrators/
│   └── __init__.py               [rỗng]
├── serve/
│   └── __init__.py               [rỗng]
├── configs/                       [thư mục tồn tại nhưng KHÔNG có file nào bên trong, kể cả file ẩn]
└── __pycache__/preflight.cpython-314.pyc   [build artifact, không liên quan]
```

Không có `tests/`, không có `.claude/`, không có `docs/`. Không có bất kỳ file `.py` nào trong `serve/`, `orchestrators/`, `harness/`, `llm/`, `agents/`, `evals/` ngoài `__init__.py` rỗng của mỗi thư mục (xác nhận bằng Glob riêng từng thư mục).

### Mô tả từng file

- **`.env`** — tồn tại trên máy, không đọc nội dung (cấm theo yêu cầu).
- **`.env.example`** — 9 dòng, liệt kê tên biến để trống: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `DEFAULT_PROVIDER`, `DEFAULT_MODEL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `API_BEARER_TOKEN`.
- **`.gitignore`** — bỏ qua `.env`, `__pycache__/`, `*.pyc`, `.venv/`, `data/`, `*.log`.
- **`README.md`** — mô tả vai trò từng thư mục và quy trình setup (preflight → pip install → setup.py). Chỉ là tài liệu, không phải code.
- **`SETUP-MAY.md`** — checklist cài máy cho người dùng cuối (Docker, Git, VS Code, tạo API key + spend limit). Tài liệu thuần.
- **`docker-compose.yml`** — 10 dòng, `services: {}`. Placeholder tường minh, comment ghi rõ "CHƯA có service nào".
- **`preflight.py`** — script chỉ dùng stdlib. Kiểm tra Python≥3.11, Git, Docker/daemon, Docker Compose v2, đang trong git repo, remote origin private. Đồng thời tự tạo (không đè) `.gitignore`, `.env.example`, `.env`, và các thư mục package (`agents/llm/harness/orchestrators/serve/evals` + `configs/`) nếu thiếu. Không cài phần mềm, không chạy git thay đổi state.
- **`requirements.txt`** — 8 dòng: `pydantic==2.13.5`, `python-dotenv==1.2.3`, `anthropic==1.4.0`, `google-generativeai==0.8.6`, `openai==3.8.0`, `pyyaml==6.0.3`, `fastapi==0.141.1`, `uvicorn==0.52.4`. Không có `chainlit`, không có thư viện Telegram, không có thư viện OCR nào, không có `python-multipart`.
- **`setup.py`** — CLI tương tác cho người dùng cuối để nhập API key qua `getpass` (ẩn ký tự), ghi vào `.env`. Hỗ trợ `--add-provider`, `--show` (che key, chỉ hiện 4 ký tự cuối), `--check` (gọi thử API thật, không log key). Import `preflight` để tái dùng hàm tạo skeleton.
- **`settings.py`** — điểm DUY NHẤT gọi `load_dotenv`. Raise `RuntimeError` ngay khi import nếu `.env` không tồn tại hoặc không có provider nào có key. Export các hằng `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `DEFAULT_PROVIDER`, `DEFAULT_MODEL`, `LANGFUSE_*`, `API_BEARER_TOKEN`, `AVAILABLE_PROVIDERS`. Đây là **side-effect toàn module khi import** (dòng 24–58): raise ngay ở import-time, không lazy.
- **`agents/__init__.py`, `llm/__init__.py`, `harness/__init__.py`, `orchestrators/__init__.py`, `serve/__init__.py`, `evals/__init__.py`** — tất cả **[rỗng]**, chỉ tồn tại để biến thư mục thành Python package. Không có logic gì.
- **`configs/`** — **[không có file nào]**. Không có YAML agent, flow, permission, hay model nào tồn tại.

✅ Mục 1 — HIỆN TRẠNG hoàn thành.

---

## 2. KHOẢNG TRỐNG

So với kiến trúc đã chốt ở Context, các phần sau **hoàn toàn chưa tồn tại**:

- **Seam HTTP (`serve/`)**: trống — chưa có FastAPI app, chưa có một route nào. Do đó hiện tại không có "một contract HTTP duy nhất" nào để adapter gọi vào — vì chưa có gì để gọi.
- **Adapter Telegram**: không có bất kỳ dòng code, file, hay dependency (`python-telegram-bot`/`aiogram`) nào liên quan đến Telegram trong toàn repo, dù Context nói đã chọn Telegram làm kênh điều khiển.
- **Web chat UI (Chainlit)**: `chainlit` không có trong `requirements.txt`, không có file `chainlit_app.py` hay tương đương.
- **Local runner / kết nối WebSocket đi ra (Giai đoạn 2)**: không có code, không có thiết kế nào tồn tại trong repo.
- **Khái niệm run_id / job bất đồng bộ**: không tồn tại ở bất kỳ đâu (vì `serve/` trống).
- **Task agent OCR hóa đơn**: `agents/` trống — chưa có agent nào, chưa có logic nhận ảnh/PDF, chưa có lời gọi vision-LLM.
- **Lớp gọi LLM thống nhất (`llm/`)**: trống — README có nhắc "core.py của agent không bao giờ gọi thẳng SDK" nhưng `core.py` đó chưa tồn tại, và `llm/` chưa có gì để nó gọi vào.
- **`harness/`**: trống — chưa có logging, giới hạn (rate/size), hay lớp an toàn nào bọc lời gọi agent.
- **`configs/`**: trống hoàn toàn — chưa có `agent.yaml`, `flow.yaml`, `permissions.yaml`, `model.yaml`. Do đó cũng chưa có cơ chế đọc config nào trong code (không có YAML nào để đọc).
- **Phân quyền owner vs member (~20 người)**: không tồn tại dưới bất kỳ hình thức nào. `settings.py` chỉ có **một** `API_BEARER_TOKEN` toàn cục — không phân biệt ai là owner, ai chỉ được chạy.
- **Scope truy cập file trên máy cá nhân**: không có khái niệm workspace/thư mục được phép, không có cơ chế giới hạn đường dẫn nào trong code (vì không có code xử lý file nào cả).
- **Dependency còn thiếu trong `requirements.txt`** để thực hiện kiến trúc đã chốt: `chainlit` (web UI), thư viện Telegram bot, thư viện/route OCR (Pillow + pytesseract, hoặc dùng vision multimodal của provider đã có key — cần quyết định, xem Mục 6), `python-multipart` (bắt buộc để FastAPI nhận `UploadFile`), thư viện WebSocket client cho Giai đoạn 2.
- **Test / CI**: không có file test nào trong repo, không có workflow CI.

✅ Mục 2 — KHOẢNG TRỐNG hoàn thành.

---

## 3. RỦI RO PHÁ VỠ KHI CÓ NHIỀU NGƯỜI DÙNG

**Ghi chú quan trọng về giới hạn của audit này**: `serve/`, `orchestrators/`, `harness/`, `llm/`, `agents/` đều trống, nên **không tồn tại logic nghiệp vụ nào** để chỉ ra "dòng/hàm cụ thể" đang giả định một người dùng trong xử lý request/response/hội thoại — vì chưa có request/response/hội thoại nào được code. Phần dưới chỉ audit được những gì thực sự đang tồn tại trong 3 file gốc (`settings.py`, `setup.py`, `preflight.py`), và ghi rõ những điểm sẽ thành rủi ro multi-user **khi** code thực tế được viết ở các bước sau.

### Rủi ro đã xác minh được trong code hiện có

- **`settings.py` dòng 43** — `API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN") or None`: đây là **một token toàn cục duy nhất cho toàn bộ process**, không có khái niệm nhiều token/nhiều user. Với kiến trúc Giai đoạn 1 (mỗi người chạy instance riêng trên máy riêng), rủi ro này bị giới hạn vì mỗi máy có `.env` riêng — nhưng nếu bất kỳ ai sau này lỡ triển khai `serve/` như một server dùng chung cho cả 20 người (vi phạm giả định "chạy local trên máy mỗi người"), token đơn này sẽ là **shared secret cho tất cả**, không thể revoke riêng từng người, không truy vết được ai gọi request nào.
- **`settings.py` dòng 24–58** — toàn bộ việc load `.env` và raise lỗi chạy **ngay khi import module** (module-level side effect, không lazy, không theo request). Đây là mẫu **global state cấp process**: một `DEFAULT_PROVIDER`/`DEFAULT_MODEL` áp dụng cho toàn bộ tiến trình, không thể override theo từng user/từng agent trong cùng một tiến trình đang chạy. Với mô hình "1 tiến trình = 1 máy = 1 người" của Giai đoạn 1 thì đây không phải bug — nhưng đây là điểm PHẢI xem lại nếu Giai đoạn 2 dùng một orchestrator server chung xử lý nhiều local runner.
- **`setup.py` — `ENV_PATH = ROOT / ".env"` (dòng 34) và `save_env_dict()` (dòng 86–98)**: đường dẫn `.env` cứng, và ghi đè **toàn bộ file** mỗi lần gọi, không có file lock, không phân biệt "ai" đang chạy script. Đây hợp lý cho mô hình 1 máy 1 người tự chạy `setup.py` cho chính mình; sẽ là race condition nếu logic này bị tái dùng trong ngữ cảnh nhiều người cùng ghi vào một `.env` chung.
- **`preflight.py` — `ensure_env()`, `ensure_dirs()` (dòng 236–261)**: ghi trực tiếp vào `ROOT = Path(__file__).resolve().parent` (dòng 28) — đường dẫn tuyệt đối cứng, không tham số hoá theo user. Không có guard nếu hai process gọi đồng thời. Rủi ro thấp vì đây là script CLI 1 máy, nhưng là mẫu code cần tránh lặp lại khi viết `serve/`.

### Rủi ro cần phòng trước khi viết code ở các bước sau (chưa xảy ra, vì code chưa tồn tại)

Đây không phải audit của code hiện tại (không có), mà là điều kiện bắt buộc khi Bước 9–10 ở Mục 5 được viết:
- **Không dùng biến module-level (list/dict cấp module) để giữ lịch sử hội thoại hoặc trạng thái run** — kể cả khi chỉ có 1 người dùng trên 1 máy, nếu Chainlit UI mở nhiều tab/nhiều session trình duyệt, hoặc FastAPI xử lý nhiều request đồng thời (multipart upload + polling status), một dict toàn cục không khóa theo `run_id`/`session_id` sẽ bị hai request ghi đè lẫn nhau.
- **`run_id` phải là khóa duy nhất bắt buộc** cho mọi state lưu trong `serve/` — không suy ra state từ thứ tự request hay từ biến toàn cục "run hiện tại".
- **Không xử lý OCR đồng bộ chặn event loop của FastAPI** — lời gọi vision-LLM (network I/O, có thể vài giây) phải chạy qua `BackgroundTasks`/thread pool/asyncio task, không gọi trực tiếp trong handler `async def` (sẽ chặn toàn bộ server, kể cả các request `GET /v1/runs/{id}` polling khác, dù chỉ có 1 người dùng cục bộ nhưng nhiều tab/nhiều run cùng lúc).

✅ Mục 3 — RỦI RO PHÁ VỠ KHI CÓ NHIỀU NGƯỜI DÙNG hoàn thành.

---

## 4. CONTRACT HTTP ĐỀ XUẤT

Tất cả endpoint nằm dưới `serve/` (FastAPI), tiền tố `/v1`. Auth: header `Authorization: Bearer <API_BEARER_TOKEN>` (đối chiếu giá trị từ `settings.API_BEARER_TOKEN`), trừ `/v1/health`.

### `GET /v1/health`
- Không cần auth.
- Response `200`: `{"status": "ok"}`

### `GET /v1/agents`
- Liệt kê agent khả dụng, đọc từ `configs/agents/*.yaml` (chỉ đọc).
- Response `200`:
```json
[
  {
    "agent_id": "invoice_ocr",
    "name": "OCR hóa đơn",
    "description": "Trích thông tin từ ảnh/PDF hóa đơn",
    "accepts_mime": ["image/png", "image/jpeg", "application/pdf"],
    "max_file_size_mb": 10
  }
]
```
- Lỗi: `401` (thiếu/sai token).

### `POST /v1/runs`
- `Content-Type: multipart/form-data`
- Form fields:
  - `agent_id` (string, bắt buộc) — phải khớp một agent trong `GET /v1/agents`.
  - `files` (một hoặc nhiều file, bắt buộc với agent OCR) — ảnh/PDF hóa đơn.
  - `note` (string, tuỳ chọn) — chỉ dẫn thêm bằng ngôn ngữ tự nhiên.
- Response `202 Accepted`:
```json
{"run_id": "01J...", "status": "queued", "agent_id": "invoice_ocr"}
```
- Mã lỗi:
  - `400` — `agent_id` không tồn tại, hoặc thiếu file bắt buộc.
  - `401` — thiếu/sai bearer token.
  - `413` — file vượt `max_file_size_mb`.
  - `415` — mime type không nằm trong `accepts_mime` của agent.
  - `422` — payload không hợp lệ theo schema (pydantic).

### `GET /v1/runs/{run_id}`
- Poll trạng thái run (client tự polling, không yêu cầu WebSocket ở Giai đoạn 1).
- Response `200`:
```json
{
  "run_id": "01J...",
  "agent_id": "invoice_ocr",
  "status": "queued | running | done | error",
  "result": { "...": "..." } ,
  "error": {"code": "string", "message": "string"},
  "created_at": "2026-09-09T10:00:00Z",
  "updated_at": "2026-09-09T10:00:03Z"
}
```
  (`result` là `null` khi chưa `done`; `error` là `null` khi không lỗi.)
- Mã lỗi:
  - `401` — thiếu/sai bearer token.
  - `404` — `run_id` không tồn tại.

### `GET /v1/runs/{run_id}/artifacts/{artifact_id}`
- Tải file kết quả (ví dụ JSON trích xuất, hoặc ảnh đã xử lý), nếu agent tạo ra artifact riêng ngoài `result` inline.
- Response `200`: file stream (`Content-Type` theo loại file).
- Mã lỗi: `401`, `404` (run hoặc artifact không tồn tại).

✅ Mục 4 — CONTRACT HTTP ĐỀ XUẤT hoàn thành.

---

## 5. KẾ HOẠCH GIAI ĐOẠN 1

Chạy toàn bộ trên một máy: FastAPI (`serve/`) + Chainlit UI ở localhost, gọi vào cùng contract HTTP ở Mục 4. Mỗi bước dưới đây sẽ được **thực hiện ở lượt code sau**, không phải trong lượt audit này.

1. **`requirements.txt`** (sửa) — thêm `chainlit`, `python-multipart` (bắt buộc để FastAPI parse `UploadFile`), và thư viện OCR/vision tuỳ theo câu trả lời Mục 6 câu 1.
   Kiểm chứng: `pip install -r requirements.txt` chạy không lỗi; `python -c "import chainlit, fastapi, multipart"` không raise.

2. **`configs/providers.yaml`** (mới) — khai báo provider/model cho phép dùng (đối chiếu với `AVAILABLE_PROVIDERS` từ `settings.py`).
   Kiểm chứng: `python -c "import yaml; yaml.safe_load(open('configs/providers.yaml', encoding='utf-8'))"` không lỗi.

3. **`configs/agents/invoice_ocr.yaml`** (mới) — khai báo `agent_id`, model, `accepts_mime`, `max_file_size_mb`, và thư mục workspace cho phép agent này đọc/ghi (scope lock, xem bước 9).
   Kiểm chứng: giống bước 2 + script nhỏ assert các field bắt buộc có mặt.

4. **`configs/permissions.yaml`** (mới) — khai báo `owners: [...]` (chỉ owner được sửa file trong `configs/`), `members: [...]` (chỉ được chạy). Owner cụ thể là ai sẽ do bạn xác nhận, không tự gán.
   Kiểm chứng: giống bước 2.

5. **`llm/client.py`** (mới) — hàm `complete()`/`vision_complete()` dựa trên provider đang có key (đọc từ `settings.AVAILABLE_PROVIDERS` + `configs/providers.yaml`), không agent nào gọi thẳng SDK provider.
   Kiểm chứng: unit test gọi hàm với input giả (mock SDK), assert không có `import anthropic`/`import openai` bên ngoài `llm/`.

6. **`harness/run_context.py`** (mới) — định nghĩa `RunContext` (run_id, workspace_dir, agent_id, timeout, giới hạn số/kích thước file) và **hàm `resolve_path(run_id, filename)` chặn path traversal** (không cho `..`, không cho absolute path ra ngoài workspace).
   Kiểm chứng: pytest — test path traversal (`../../etc/passwd`, `C:\Windows\...`) phải raise `PermissionError`.

7. **`agents/invoice_ocr/agent.py`** (mới) — nhận file trong workspace của run, gọi `llm/` vision, trả JSON các trường hóa đơn (số hóa đơn, ngày, tổng tiền, nhà cung cấp — cụ thể hoá theo câu trả lời Mục 6).
   Kiểm chứng: chạy trực tiếp với 1 ảnh test cục bộ, in JSON kết quả.

8. **`orchestrators/main_orchestrator.py`** (mới) — nhận `agent_id` + input, đọc `configs/agents/*.yaml`, tạo `RunContext`, gọi agent, cập nhật status (`queued→running→done/error`).
   Kiểm chứng: gọi hàm trực tiếp từ REPL với run giả, kiểm tra transition status đúng thứ tự.

9. **`serve/store.py`** (mới) — state run trong-process, khóa bằng `run_id` (dict + `threading.Lock`, vì FastAPI có thể xử lý nhiều request đồng thời dù trên 1 máy 1 người — nhiều tab/nhiều run song song).
   Kiểm chứng: test tạo 2 run đồng thời (2 thread), assert không đè dữ liệu nhau.

10. **`serve/app.py`** (mới) — implement đúng contract Mục 4 (`/v1/health`, `/v1/agents`, `POST /v1/runs`, `GET /v1/runs/{id}`, `GET /v1/runs/{id}/artifacts/{id}`). Xử lý OCR qua `BackgroundTasks` (không chặn event loop). Lưu file upload vào `<workspace_root>/{run_id}/input/`, kết quả vào `<workspace_root>/{run_id}/output/` — **scope lock**: mọi truy cập file của agent chỉ được đi qua `harness.resolve_path()`, không có đường dẫn nào ra ngoài `<workspace_root>` (mặc định: một thư mục `runs/` dưới gốc repo trên máy người dùng đó; xem câu hỏi Mục 6 câu 2 nếu cần mở rộng ra thư mục khác trên máy).
    Kiểm chứng: `uvicorn serve.app:app --host 127.0.0.1 --port 8000` rồi `curl http://127.0.0.1:8000/v1/health` trả `{"status":"ok"}`; `curl -X POST .../v1/runs -F agent_id=invoice_ocr -F files=@test.png` trả `run_id`.

11. **Chainlit UI** — file mới (ví dụ `chainlit_app.py` ở gốc repo) — chỉ gọi HTTP contract ở Mục 4 qua `httpx`, KHÔNG import trực tiếp `orchestrators`/`agents` (giữ đúng nguyên tắc adapter không chứa logic agent).
    Kiểm chứng: `chainlit run chainlit_app.py -w`, mở `http://localhost:8000` (cổng Chainlit mặc định), upload 1 ảnh hóa đơn test, xác nhận nhận được kết quả OCR qua polling.

12. **Scope lock tổng kết** — agent (`agents/invoice_ocr`) chỉ được đọc/ghi trong `<workspace_root>/{run_id}/` (input/output riêng từng run), không đọc/ghi bất kỳ đường dẫn nào khác trên máy trừ khi Mục 6 câu 2 xác nhận yêu cầu khác. Việc chặn này nằm ở `harness.resolve_path()` (bước 6), được gọi từ cả `serve/app.py` (khi lưu upload) và `agents/invoice_ocr/agent.py` (khi đọc/ghi).
    Kiểm chứng: test đã có ở bước 6 (path traversal) + test thủ công: xóa quyền ghi ngoài `runs/`, chạy lại toàn luồng upload→OCR, xác nhận không có file nào được tạo ngoài `runs/`.

13. **`docker-compose.yml`** — giữ nguyên placeholder, KHÔNG sửa trong Giai đoạn 1 (Context đã chốt "toàn bộ chạy local", không cần container hoá ở bước này).

✅ Mục 5 — KẾ HOẠCH GIAI ĐOẠN 1 hoàn thành.

---

## 6. CÂU HỎI CHẶN

1. OCR bằng **vision multimodal của LLM đã có key** (Anthropic/Gemini/OpenAI — không cần cài thêm binary ngoài Python) hay bằng **OCR engine local** (Tesseract, cần cài `pytesseract` + binary `tesseract`/`poppler` ngoài `pip`)? Quyết định này thay đổi trực tiếp `requirements.txt` (bước 1) và độ chính xác/field trích xuất được ở `agents/invoice_ocr` (bước 7).
2. "Agent phải thao tác được file trên máy cá nhân" — nghĩa là **(a)** người dùng upload file qua UI, agent chỉ xử lý trong workspace riêng của run (`runs/{run_id}/`), hay **(b)** agent cần đọc/ghi trực tiếp một thư mục cụ thể đã có sẵn trên máy (ví dụ tự động theo dõi `Downloads/HoaDon/`) mà không cần bước upload? Câu trả lời quyết định phạm vi scope lock ở bước 12.
3. Xác nhận: ở Giai đoạn 1, mỗi người trong ~20 người tự chạy `python setup.py` trên máy riêng để tự sinh `API_BEARER_TOKEN` riêng của mình — **không có server trung tâm phát token chung**. Đúng vậy không?
4. Giới hạn kích thước/định dạng file upload hóa đơn cụ thể là bao nhiêu (ví dụ tối đa 10MB, chỉ `png/jpg/pdf`)? Cần số cụ thể để đưa vào `configs/agents/invoice_ocr.yaml` và validate ở `POST /v1/runs`.
5. Kết quả OCR có cần lưu lại lâu dài (ví dụ tổng hợp vào 1 file/DB để tra cứu lại các hóa đơn đã xử lý) hay mỗi run chỉ trả kết quả một lần, không cần lịch sử?

✅ Mục 6 — CÂU HỎI CHẶN hoàn thành.
