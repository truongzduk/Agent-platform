# Thêm một thành phần mới

Đọc hết mục 1 trước khi gõ dòng nào. Chọn sai giữa tool và agent là loại lỗi
đắt nhất trong hệ này: nó làm sai ngân sách token, sai cách test, và sai cả
cách gỡ lỗi về sau.

---

## 1. Cây quyết định: đây nên là TOOL hay AGENT?

```
Thành phần bạn sắp viết có gọi LLM không?
│
├─ KHÔNG ──────────────────────────────────────► type: tool
│   Ví dụ: tải mail về đĩa, đọc file, parse CSV,
│   gọi REST API, xuất Excel, đổi định dạng ngày,
│   lọc/sắp xếp/gom nhóm dữ liệu.
│   → CẤM có tier. Không tính vào ngân sách token.
│   → Kết quả XÁC ĐỊNH: cùng input luôn ra cùng output.
│
└─ CÓ ─────────────────────────────────────────► type: agent
    Ví dụ: tóm tắt, phân loại ý định, rút trích trường
    từ văn bản tự do, viết lại, so sánh hai đoạn, đọc ảnh.
    → BẮT BUỘC có tier. Tính vào ngân sách token.
    → Kết quả KHÔNG xác định: phải có eval, không chỉ có unit test.
```

Ba câu hỏi để tự bắt lỗi khi phân vân:

1. **"Tôi viết được bằng `if`/`for`/regex không?"** Viết được → tool. Đừng dùng
   LLM để làm việc mà `str.upper()` làm được: nó chậm hơn, đắt hơn, và thỉnh
   thoảng sai.
2. **"Cùng input, tôi có cần đúng cùng output mỗi lần không?"** Cần → tool.
3. **"Việc này có phần 'hiểu' ngôn ngữ tự nhiên không?"** Có → agent.

Trường hợp hay gặp: *"đọc file PDF rồi rút ra số hóa đơn"*. Đây là **hai**
thành phần, không phải một: một **tool** đọc PDF ra text, và một **agent** rút
trích trường từ text. Tách ra thì phần xác định được test bằng unit test, và
chỉ phần thật sự cần LLM mới tốn token.

## 2. Nếu là agent: chọn tier nào?

Agent khai báo `tier`, **không bao giờ** khai báo tên model. Ánh xạ tier →
provider + model nằm duy nhất ở `configs/tiers.yaml`.

| Tier | Chọn khi | Dấu hiệu nhận biết | Đắt/chậm |
|---|---|---|---|
| `fast` | Nhiều lượt gọi, mỗi lượt một việc nhỏ và rõ | Rút trích trường, phân loại vào danh sách nhãn có sẵn, chuẩn hoá, kiểm tra có/không | Rẻ nhất |
| `standard` | Mặc định khi không có lý do rõ ràng để chọn hai tier kia | Tóm tắt, viết lại, trả lời câu hỏi trên một tài liệu | Vừa |
| `deep` | Ít lượt gọi, mỗi lượt suy luận nhiều bước | Tổng hợp 200 kết quả đã gom, phát hiện mâu thuẫn, đề xuất có lập luận | Đắt nhất |

Tiêu chí quyết định, theo thứ tự:

1. **Số lượt gọi trên một run.** Chạy 500 lần trong một vòng lặp → `fast`. Chạy
   một lần ở cuối → cân nhắc `deep`.
2. **Hậu quả khi sai một lượt.** Một lượt sai bị bước sau bắt được hoặc bị lẫn
   trong 500 lượt khác → `fast`. Sai là hỏng cả kết quả cuối → `deep`.
3. **Đầu vào có cần suy luận nhiều bước không.** Rút một trường ra khỏi văn bản
   là một bước → `fast`. So sánh chéo nhiều nguồn rồi kết luận là nhiều bước →
   `deep`.

Nghi ngờ thì bắt đầu ở `fast`, đo lại bằng eval, rồi mới nâng. Nâng tier là sửa
một dòng YAML, không phải sửa code — nên đừng chọn `deep` "cho chắc".

---

## 3. Template — TOOL

`configs/tools/<id>.yaml`:

```yaml
id: doc_file_text              # duy nhất toàn catalog, nên trùng tên file
type: tool                     # CẤM tier, model, provider, system_prompt
name: Đọc file text
description: >                 # LLM đọc trường này để chọn tool -> viết rõ,
  Đọc một file text trong       # nói rõ nhận gì và trả gì
  workspace của run và trả về nội dung dạng chuỗi.

entrypoint: tools.doc_file_text:run     # module:function

inputs:
  - name: filename
    type: string               # string | integer | number | boolean | object | array
    required: true
    description: Tên file tương đối trong workspace của run.

outputs:
  - name: content
    type: string
    description: Nội dung file.
```

`tools/doc_file_text.py`:

```python
"""Chữ ký chuẩn của MỌI tool: run(inputs, ctx) -> dict."""
from __future__ import annotations

from typing import Any

from harness.run_context import RunContext


def run(inputs: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    # Mọi thao tác đĩa đi qua ctx — không tự ghép đường dẫn, không dùng open().
    return {"content": ctx.read_text(inputs["filename"])}
```

Tool **không** nhận tham số `complete`, nên về mặt cấu trúc nó không thể gọi
LLM. Đó là chủ ý, không phải thiếu sót.

## 4. Template — AGENT

`configs/agents/<id>.yaml`:

```yaml
id: phan_loai_email
type: agent
name: Phân loại email
description: >
  Đọc nội dung một email và gán đúng một nhãn trong: hoa_don, hop_dong, khac.

tier: fast                     # BẮT BUỘC. fast | standard | deep. KHÔNG ghi tên model.
entrypoint: agents.phan_loai_email.agent:run

system_prompt: >               # chuỗi TĨNH — cấm nội suy biến trong YAML
  Bạn là bộ phân loại email. Trả lời bằng ĐÚNG một trong ba từ:
  hoa_don, hop_dong, khac. Không giải thích, không thêm chữ nào khác.

inputs:
  - name: body
    type: string
    required: true
    description: Nội dung email cần phân loại.

outputs:
  - name: label
    type: string
    description: Một trong ba nhãn hoa_don, hop_dong, khac.
```

`agents/phan_loai_email/agent.py`:

```python
"""Chữ ký chuẩn của MỌI agent: run(inputs, ctx, spec, complete) -> dict."""
from __future__ import annotations

from typing import Any, Callable

from harness.run_context import RunContext

NHAN_HOP_LE = {"hoa_don", "hop_dong", "khac"}


def run(inputs: dict[str, Any], ctx: RunContext, spec: Any,
        complete: Callable[..., Any]) -> dict[str, Any]:
    # `complete` do flow_runner truyền vào, đã KẸP SẴN tier lấy từ YAML.
    # Agent không chọn tier, không thấy tên model, không import SDK nào.
    completion = complete(
        [{"role": "user", "content": str(inputs["body"])}],
        system=spec.system_prompt,          # prompt lấy từ YAML, không hardcode
    )
    label = completion.content.strip().lower()
    if label not in NHAN_HOP_LE:            # LLM không xác định -> luôn kiểm tra đầu ra
        label = "khac"
    return {"label": label}
```

Bốn điều agent **không được** làm:

1. `import anthropic` / `import openai` / `import google.generativeai` — chỉ
   `llm/` được phép.
2. Viết tên model ở bất kỳ đâu.
3. Tự chọn tier, hoặc gọi thẳng `llm.client.complete` — phải dùng `complete`
   được truyền vào, vì đó là đường duy nhất có bộ đếm limits + usage.
4. `open()` / `Path(...)` với đường dẫn tự ghép — mọi thao tác đĩa qua `ctx`.

---

## 5. Đăng ký

Không có bước đăng ký thủ công nào. `orchestrators/registry.py` quét
`configs/tools/*.yaml`, `configs/agents/*.yaml`, `configs/flows/*.yaml` mỗi lần
nạp. Đặt file YAML đúng thư mục là xong; `GET /v1/catalog` và bộ chọn của
orchestrator hội thoại thấy nó ngay lần khởi động sau.

`description` trong YAML chính là thứ LLM đọc để quyết định có chọn thành phần
của bạn hay không. Viết nó như viết docstring cho máy: nhận gì, trả gì, dùng khi
nào.

## 6. Test

Ba tầng, chạy bằng `python -m pytest`:

```python
# 1. Catalog hợp lệ — registry validate được file YAML của bạn.
def test_catalog_nap_duoc():
    reg = load_registry()
    assert reg.agents["phan_loai_email"].tier == "fast"

# 2. Logic — LLM giả, KHÔNG gọi API thật.
def test_nhan_la_bi_ep_ve_khac():
    from llm.client import Completion
    calls = []

    def fake(messages, *, system=None, max_tokens=None):
        calls.append(system)
        return Completion("LUNG TUNG", 5, 2, "fast", "model-gia")

    spec = load_registry().agents["phan_loai_email"]
    out = run({"body": "abc"}, ctx, spec, fake)
    assert out["label"] == "khac"

# 3. Trong flow — chạy qua flow_runner với complete giả (xem tests/test_flow_runner.py).
```

Không bao giờ gọi API thật trong test. Mock luôn ở tham số `complete`.

## 7. Checklist trước khi dùng thật

- [ ] Đã trả lời được câu "vì sao đây là agent chứ không phải tool"?
- [ ] `type` đúng; nếu là tool thì **không** có `tier`/`model`/`system_prompt`.
- [ ] Nếu là agent: có `tier`, và tier đó có trong `configs/tiers.yaml`.
- [ ] Không có tên model ở bất kỳ đâu ngoài `configs/tiers.yaml`.
- [ ] Không `import` SDK provider ngoài `llm/`.
- [ ] Mọi thao tác file đi qua `ctx.resolve_path()`/`write_text()`/`read_text()`.
- [ ] Đầu ra của agent được kiểm tra/ép kiểu trước khi trả — LLM không xác định.
- [ ] `description` đủ rõ để LLM chọn đúng, không lẫn với thành phần khác.
- [ ] `python -m pytest` xanh, không có test nào chạm mạng.
- [ ] Đã chạy thử một lần và đọc dòng tương ứng trong `runs/index.jsonl`: số
      token và tier có đúng như bạn nghĩ không?
- [ ] Nếu là agent chạy trong vòng lặp: đã ước lượng số lượt × token/lượt so với
      trần trong `harness/limits.py` chưa?

---

## 8. Ví dụ hoàn chỉnh, chạy được từ đầu đến cuối

Chính là thành phần mẫu đang có trong repo. Đọc theo thứ tự này:

| Bước | File | Nội dung |
|---|---|---|
| 1 | `configs/tools/upper_text.yaml` | Tool: viết hoa text. Không tier. |
| 2 | `tools/upper_text.py` | 3 dòng, `run(inputs, ctx)`. |
| 3 | `configs/agents/summarize_text.yaml` | Agent: tóm tắt 1 câu, `tier: fast`. |
| 4 | `agents/summarize_text/agent.py` | `run(inputs, ctx, spec, complete)`. |
| 5 | `configs/flows/demo_two_step.yaml` | Nối bước 1 → bước 3. |
| 6 | `tests/test_flow_runner.py` | Chạy cả flow với LLM giả. |
| 7 | `tests/test_usage.py` | Chứng minh chỉ agent bị tính token. |

Chạy thử toàn tuyến:

```bash
python -m pytest -q                       # tất cả phải xanh, không chạm mạng
python -m uvicorn serve.app:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/v1/health                       # {"status":"ok"}
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/v1/catalog
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"session_id":"s1","text":"chay demo_two_step voi cau nay"}' \
     http://127.0.0.1:8000/v1/messages                     # -> run_id
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/v1/runs/<run_id>
tail -1 runs/index.jsonl                                   # token chỉ của bước agent
```

Muốn thấy cơ chế tier hoạt động: đổi `tier: fast` thành `tier: deep` trong
`configs/agents/summarize_text.yaml`, chạy lại — dòng trong `runs/index.jsonl`
đổi sang tier `deep`, và **không có dòng code nào phải sửa**.
