# Thêm một flow

Flow là cách nối nhiều tool/agent lại. Có đúng hai loại, và ranh giới giữa
chúng là ranh giới cứng.

---

## 1. Quy tắc quyết định

```
Flow của bạn có BẤT KỲ thứ nào sau đây không?
  - vòng lặp (chạy cùng một bước trên nhiều phần tử)
  - rẽ nhánh (nếu A thì chạy X, không thì chạy Y)
  - retry (thử lại khi lỗi)
  - fan-out / fan-in (tách ra nhiều nhánh rồi gom lại)
  - số bước phụ thuộc dữ liệu lúc chạy
│
├─ KHÔNG ─► kind: sequential — khai báo trọn vẹn bằng YAML
│
└─ CÓ ────► kind: python — BẮT BUỘC viết hàm trong orchestrators/flows/
```

**Không có lựa chọn thứ ba.** Cụ thể là **CẤM** thêm `if`, `for`, biểu thức,
hay nội suy biến vào YAML để né việc viết Python. YAML trong `configs/` là
CATALOG; ngay khi nó bắt đầu chứa điều kiện, nó thành một ngôn ngữ lập trình
tồi — không debug được, không test được, không có stack trace.

---

## 2. Khi nào dùng YAML (`kind: sequential`)

Đủ điều kiện khi flow là một chuỗi thẳng: bước 1 → bước 2 → bước 3, số bước cố
định, không có quyết định nào lúc chạy.

Ví dụ đầy đủ: `configs/flows/demo_two_step.yaml`.

```yaml
id: demo_two_step
type: flow
kind: sequential
name: Demo hai bước
description: >
  Viết hoa văn bản rồi tóm tắt kết quả thành một câu.

inputs:
  - name: text
    type: string
    required: true
    description: Văn bản đầu vào của flow.

steps:
  - id: upper
    ref: upper_text            # type: tool  -> chạy hàm Python, không tốn token
    input:
      text:
        from: flow_input       # nguồn dạng 1: lấy từ input của flow
        name: text

  - id: summarize
    ref: summarize_text        # type: agent -> đi qua llm/client với tier trong YAML agent
    input:
      text:
        from: step             # nguồn dạng 2: lấy output của bước trước
        step: upper
        output: text

output:
  from: step
  step: summarize
  output: summary
```

Chỉ có **hai** dạng nguồn dữ liệu (`from: flow_input`, `from: step`), viết dưới
dạng mapping khai báo. Không có chuỗi mẫu, không có hằng số inline. Cần biến đổi
dữ liệu giữa hai bước (đổi định dạng, lọc, gom) → **viết thêm một tool**, đừng
nhét logic vào YAML.

Bước không khai báo mình là tool hay agent. `flow_runner` tra `ref` trong
catalog rồi phân nhánh theo `type`. Đổi một bước từ tool sang agent không phải
sửa flow.

Đặc tả đầy đủ mọi trường: `docs/SCHEMA.md` §7.

---

## 3. Khi nào BẮT BUỘC viết Python (`kind: python`)

### Ví dụ minh hoạ: xử lý một loạt email

Yêu cầu nghiệp vụ:

1. Tải toàn bộ email chưa đọc trong hộp thư về workspace của run — **tool**
   `tai_email` (không LLM, không token).
2. Với **từng** email vừa tải, rút trích các trường cần thiết — **agent**
   `rut_trich_email`, `tier: fast` (nhiều lượt, mỗi lượt một việc nhỏ).
3. Gom toàn bộ kết quả rút trích lại, phân tích tổng thể và báo cáo — **agent**
   `phan_tich_lo`, `tier: deep` (một lượt duy nhất, suy luận nhiều bước).

Vì sao flow này **KHÔNG THỂ** khai báo bằng YAML:

> **Bước 2 là fan-out.** Số lần chạy `rut_trich_email` chỉ biết được *lúc chạy*,
> sau khi bước 1 trả về — hôm nay 3 email, mai 300. Schema YAML ở §7.2 của
> SCHEMA.md là một **danh sách bước tĩnh**: mỗi phần tử `steps[]` chạy đúng một
> lần, và `from: step / step: X / output: Y` trỏ tới **một** giá trị của **một**
> bước. Không có cách nào diễn đạt "chạy bước này một lần cho mỗi phần tử của
> mảng rồi gom kết quả lại" mà không thêm cú pháp vòng lặp vào YAML — thứ đã bị
> cấm tuyệt đối.

Hai lý do phụ cũng đòi Python trong cùng ví dụ này:

- **Fan-in** ở bước 3: đầu vào của `phan_tich_lo` là *danh sách* kết quả của N
  lượt chạy, không phải output của một bước cụ thể.
- **Retry**: một email hỏng định dạng làm agent lỗi thì nên bỏ qua email đó và
  chạy tiếp, không giết cả run. Đó là `try/except` — là logic.

### Khai báo trong catalog

`configs/flows/xu_ly_lo_email.yaml`:

```yaml
id: xu_ly_lo_email
type: flow
kind: python                   # -> KHÔNG có steps, KHÔNG có output
name: Xử lý lô email
description: >
  Tải email chưa đọc, rút trích từng email bằng tier fast, rồi phân tích tổng
  thể bằng tier deep. Fan-out theo số email nên phải viết bằng Python.

entrypoint: orchestrators.flows.xu_ly_lo_email:run

inputs:
  - name: so_luong_toi_da
    type: integer
    required: true
    description: Số email tối đa cần xử lý trong một run.
```

### Hàm Python

`orchestrators/flows/xu_ly_lo_email.py`:

```python
"""Chữ ký chuẩn của MỌI flow Python: run(inputs, ctx, deps) -> Any."""
from __future__ import annotations

from typing import Any

from harness.run_context import RunContext


def run(inputs: dict[str, Any], ctx: RunContext, deps: Any) -> Any:
    # Bước 1 — tool, chạy một lần.
    tai = deps.run_component("tai_email", {"so_luong": inputs["so_luong_toi_da"]})

    # Bước 2 — FAN-OUT: số lượt chỉ biết ở đây. Đây chính là lý do flow này
    # không khai báo được bằng YAML.
    da_rut_trich: list[dict] = []
    for duong_dan in tai["files"]:
        deps.limits.check_deadline()          # tôn trọng trần thời gian của run
        try:
            ket_qua = deps.run_component("rut_trich_email", {"filename": duong_dan})
        except Exception:                     # retry/bỏ qua cũng là logic -> Python
            continue
        da_rut_trich.append(ket_qua)

    # Bước 3 — FAN-IN: gom N kết quả thành một đầu vào cho agent tier deep.
    return deps.run_component("phan_tich_lo", {"muc": da_rut_trich})["bao_cao"]
```

`deps` là `orchestrators.flow_runner.FlowDeps`. Dùng `deps.run_component(id,
inputs)` để chạy tool/agent, **đừng** tự import và gọi hàm agent: chỉ đường này
mới đi qua bộ đếm `limits` + `usage`, mới kẹp đúng tier từ config, và mới bảo
đảm bước tool không bị tính token còn bước agent thì có.

Trong ví dụ trên, một run điển hình 50 email sẽ ghi vào `runs/index.jsonl`:
`tool_steps: 1`, tier `fast` khoảng 50 lượt gọi, tier `deep` đúng 1 lượt — tách
riêng từng tier nên nhìn ra ngay chỗ nào tốn tiền.

---

## 4. Bảng tra nhanh

| Tình huống | Loại |
|---|---|
| A → B → C, luôn đúng 3 bước | `sequential` |
| Chạy một agent cho mỗi phần tử của danh sách | `python` (fan-out) |
| Gom N kết quả thành một đầu vào | `python` (fan-in) |
| Nếu phân loại là X thì chạy agent này, không thì agent kia | `python` (rẽ nhánh) |
| Thử lại tối đa 3 lần khi lỗi | `python` (retry) |
| Lặp tới khi đạt điều kiện | `python` (vòng lặp) |
| Cần đổi định dạng dữ liệu giữa hai bước | `sequential` + **viết thêm một tool** |

## 5. Checklist trước khi dùng thật

- [ ] Đã kiểm lại: flow này thật sự không có vòng lặp/rẽ nhánh/retry/fan-out?
- [ ] Không có `if`/`for`/biểu thức/nội suy biến nào trong file YAML.
- [ ] `kind: sequential` → có `steps` + `output`, **không** có `entrypoint`.
- [ ] `kind: python` → có `entrypoint`, **không** có `steps`/`output`.
- [ ] Mọi `steps[].ref` trỏ tới tool/agent có thật (registry sẽ báo lỗi nếu không).
- [ ] `from: step` chỉ trỏ về bước đã chạy **trước** nó.
- [ ] Flow Python chỉ chạy thành phần qua `deps.run_component()`.
- [ ] Flow có vòng lặp: đã ước lượng số lượt × token so với trần trong
      `harness/limits.py`; vượt trần thì run bị raise, không chạy tiếp.
- [ ] `python -m pytest` xanh, LLM được mock, không có test nào chạm mạng.
