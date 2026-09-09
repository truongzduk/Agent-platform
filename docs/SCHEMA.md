# SCHEMA — đặc tả mọi trường trong `configs/`

Tài liệu này là hợp đồng giữa file YAML trong `configs/` và bộ nạp/validate
(`orchestrators/registry.py`). Mọi trường không được liệt kê ở đây đều bị coi là
sai và phải làm validate thất bại (`extra = "forbid"`).

Nguyên tắc bao trùm:

- `configs/` chứa **CATALOG**, không chứa **LOGIC**.
- **KHÔNG** `if`, `for`, biểu thức, hay nội suy biến trong bất kỳ file YAML nào.
  Liên kết dữ liệu chỉ được viết bằng mapping khai báo (`from: flow_input` /
  `from: step`).
- Tên model chỉ được xuất hiện trong `configs/tiers.yaml`. Không ở đâu khác,
  kể cả file `.py`.

---

## 0. Bảng phân biệt TOOL và AGENT (phần quan trọng nhất)

| Trường | `type: tool` | `type: agent` | Ghi chú |
|---|---|---|---|
| `id` | bắt buộc | bắt buộc | duy nhất trên toàn catalog (tool + agent + flow dùng chung một không gian tên) |
| `type` | bắt buộc, `tool` | bắt buộc, `agent` | trường phân biệt |
| `name` | bắt buộc | bắt buộc | tên hiển thị |
| `description` | bắt buộc | bắt buộc | LLM đọc trường này để chọn thành phần → viết cho máy đọc |
| `entrypoint` | bắt buộc | bắt buộc | dạng `module:function` |
| `inputs` | bắt buộc | bắt buộc | xem §6 |
| `outputs` | bắt buộc | bắt buộc | xem §6 |
| `tier` | **CẤM** → lỗi validate | **BẮT BUỘC** → thiếu là lỗi validate | |
| `model` | **CẤM** | **CẤM** | tên model chỉ nằm ở `configs/tiers.yaml` |
| `provider` | **CẤM** | **CẤM** | suy ra từ tier |
| `system_prompt` | **CẤM** | tuỳ chọn | tool không có prompt vì tool không gọi LLM |
| Gọi LLM | không bao giờ | có | |
| Tính vào ngân sách token của run | **không** | **có** | xem `harness/limits.py`, `harness/usage.py` |
| Được ghi nhận trong usage | chỉ đếm **số bước đã chạy** | đếm token in/out, tách theo tier | |

Quy tắc quyết định: **thành phần này có gọi LLM không?** Có → `agent`, bắt buộc
có `tier`. Không → `tool`, cấm có `tier`. Không có trường hợp ở giữa.

---

## 1. `configs/providers.yaml`

Khai báo provider nào owner cho phép dùng.

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `providers` | list | có | Danh sách provider. |
| `providers[].id` | string | có | Định danh provider. Hợp lệ: `anthropic`, `gemini`, `openai` — trùng khớp khoá trong `settings._PROVIDER_KEYS`. |
| `providers[].enabled` | bool | có | `false` = cấm dùng dù trên máy có API key. |
| `providers[].api_key_env` | string | có | **Tên** biến môi trường chứa key (ví dụ `ANTHROPIC_API_KEY`). Không bao giờ chứa giá trị key. |
| `providers[].description` | string | không | Ghi chú cho người đọc. |

**Đối chiếu với `settings.py`:** một provider chỉ dùng được khi `enabled: true`
**VÀ** `id` có mặt trong `settings.AVAILABLE_PROVIDERS` (danh sách provider thực
sự có key trên máy đang chạy). File YAML là *ý muốn* của owner;
`settings.AVAILABLE_PROVIDERS` là *thực tế* trên máy. Lệch nhau thì
`llm/client.py` phải raise lỗi nói rõ provider nào thiếu key, không im lặng đổi
sang provider khác.

---

## 2. `configs/tiers.yaml`

Nơi **duy nhất** ánh xạ tier → provider + model.

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `tiers` | mapping | có | Khoá là tên tier. Đúng ba khoá: `fast`, `standard`, `deep`. |
| `tiers.<tier>.description` | string | có | Khi nào nên chọn tier này. |
| `tiers.<tier>.provider` | string | có | Phải là một `providers[].id` đang `enabled`. Chuỗi rỗng = chưa cấu hình. |
| `tiers.<tier>.model` | string | có | Tên model thật của provider đó. Chuỗi rỗng = chưa cấu hình. |
| `tiers.<tier>.max_tokens` | int > 0 | có | Trần token **output** cho mỗi lời gọi LLM ở tier này. Đây là trần duy nhất cho một lời gọi; agent không có trần riêng. |
| `tiers.<tier>.cost_per_1m_input_usd` | float hoặc `null` | có | USD trên 1.000.000 token input. `null` = chưa biết giá. |
| `tiers.<tier>.cost_per_1m_output_usd` | float hoặc `null` | có | USD trên 1.000.000 token output. `null` = chưa biết giá. |

**Trạng thái chưa cấu hình:** `provider` hoặc `model` rỗng không làm hỏng việc
nạp catalog (registry vẫn validate và liệt kê được), nhưng **phải** làm
`llm/client.complete()` raise lỗi rõ ràng ngay khi có ai đó gọi tier đó — không
đoán model, không im lặng rơi về `settings.DEFAULT_MODEL`.

**Chi phí `null`:** usage vẫn ghi đủ token; cột chi phí ước tính ghi `null`.
Không đoán giá.

Ba tier và tiêu chí chọn:

- `fast` — nhiều lượt gọi, mỗi lượt việc nhỏ và rõ (rút trích trường, phân loại,
  chuẩn hoá). Sai một lượt không phá kết quả tổng.
- `standard` — mặc định khi không có lý do rõ ràng để chọn hai tier kia.
- `deep` — ít lượt gọi, mỗi lượt suy luận nhiều bước trên dữ liệu đã gom sẵn.

---

## 3. `configs/permissions.yaml`

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `owners` | list | có | Người được sửa `configs/`. |
| `owners[].id` | string | có | Email hoặc tên đăng nhập git. |
| `owners[].note` | string | không | Ghi chú. |
| `members` | list | có | Người chỉ được chạy. Có thể là list rỗng. |
| `members[].id` | string | có | Như trên. |
| `members[].note` | string | không | Ghi chú. |

**Phạm vi hiệu lực:** đây là **quy ước tổ chức**, không phải cơ chế cưỡng chế
lúc chạy. Giai đoạn 1, mỗi người chạy instance riêng trên máy riêng với
`API_BEARER_TOKEN` riêng do chính họ sinh bằng `python setup.py`. `serve/` xác
thực bằng bearer token đơn và **không** đọc file này. Việc chặn member sửa
`configs/` được thực thi ở tầng quyền repo, không ở runtime.

---

## 4. `configs/tools/<id>.yaml` — type: tool

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `id` | string | có | Duy nhất toàn catalog. Nên trùng tên file. |
| `type` | `"tool"` | có | Giá trị khác `tool` là lỗi trong thư mục này. |
| `name` | string | có | Tên hiển thị. |
| `description` | string | có | LLM đọc để chọn tool. |
| `entrypoint` | string `module:function` | có | Hàm Python được gọi thẳng, ví dụ `tools.upper_text:run`. |
| `inputs` | list | có | Xem §6. |
| `outputs` | list | có | Xem §6. |
| `tier` | — | **CẤM** | Có mặt là lỗi validate. |
| `model` / `provider` / `system_prompt` | — | **CẤM** | Có mặt là lỗi validate. |

---

## 5. `configs/agents/<id>.yaml` — type: agent

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `id` | string | có | Duy nhất toàn catalog. |
| `type` | `"agent"` | có | |
| `name` | string | có | Tên hiển thị. |
| `description` | string | có | LLM đọc để chọn agent. |
| `tier` | `fast` \| `standard` \| `deep` | **có** | Thiếu → lỗi validate. Giá trị không có trong `configs/tiers.yaml` → lỗi validate. |
| `entrypoint` | string `module:function` | có | Ví dụ `agents.summarize_text.agent:run`. |
| `system_prompt` | string | không | Chuỗi **tĩnh**. Không nội suy biến. Dữ liệu chạy được truyền qua `inputs`, không nhét vào prompt bằng template trong YAML. |
| `inputs` | list | có | Xem §6. |
| `outputs` | list | có | Xem §6. |
| `model` / `provider` | — | **CẤM** | Suy ra từ `tier`. |

---

## 6. Khối `inputs` / `outputs` (dùng chung cho tool, agent, flow)

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `[].name` | string | có | Tên tham số. Duy nhất trong cùng danh sách. |
| `[].type` | `string` \| `integer` \| `number` \| `boolean` \| `object` \| `array` | có | Kiểu dữ liệu. |
| `[].required` | bool | chỉ có ở `inputs`, mặc định `true` | `outputs` không có trường này. |
| `[].description` | string | có | Đi thẳng vào JSON schema sinh cho LLM tool-calling. |

---

## 7. `configs/flows/<id>.yaml` — type: flow

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `id` | string | có | Duy nhất toàn catalog. |
| `type` | `"flow"` | có | |
| `kind` | `sequential` \| `python` | có | Xem §7.1. |
| `name` | string | có | Tên hiển thị. |
| `description` | string | có | LLM đọc để chọn flow. |
| `inputs` | list | có | Input cấp flow, xem §6. |
| `steps` | list | bắt buộc khi `kind: sequential`; **CẤM** khi `kind: python` | Các bước chạy tuần tự theo đúng thứ tự khai báo. |
| `entrypoint` | string `module:function` | bắt buộc khi `kind: python`; **CẤM** khi `kind: sequential` | Hàm trong `orchestrators/flows/`. |
| `output` | mapping | bắt buộc khi `kind: sequential`; **CẤM** khi `kind: python` | Kết quả trả về của flow, xem §7.4. |

### 7.1 `kind`

- `sequential` — chuỗi bước thẳng: không vòng lặp, không rẽ nhánh, không retry,
  không fan-out. Khai báo được trọn vẹn bằng YAML.
- `python` — mọi thứ còn lại. **BẮT BUỘC** viết hàm trong `orchestrators/flows/`
  rồi đăng ký vào catalog bằng `entrypoint`. Không được mô phỏng vòng lặp/rẽ
  nhánh bằng cách thêm cú pháp vào YAML.

### 7.2 `steps[]`

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `steps[].id` | string | có | Duy nhất **trong flow**. Dùng để bước sau trỏ ngược lại. |
| `steps[].ref` | string | có | `id` của một tool hoặc agent trong catalog. Không tồn tại → lỗi validate. |
| `steps[].input` | mapping | có | Khoá = tên input của thành phần được `ref`. Giá trị = một *nguồn dữ liệu*, xem §7.3. |

Flow **không** khai báo bước là tool hay agent. `flow_runner` tra `ref` trong
catalog rồi phân nhánh theo `type` của thành phần đó. Nhờ vậy đổi một bước từ
tool sang agent không phải sửa flow.

### 7.3 Nguồn dữ liệu — hai dạng, không có dạng thứ ba

Lấy từ input của flow:

```yaml
text:
  from: flow_input
  name: text          # phải khớp một inputs[].name của flow
```

Lấy từ output của một bước trước đó:

```yaml
text:
  from: step
  step: upper         # phải là steps[].id đã chạy TRƯỚC bước hiện tại
  output: text        # phải khớp một outputs[].name của thành phần bước đó ref tới
```

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `from` | `flow_input` \| `step` | có | Loại nguồn. |
| `name` | string | chỉ khi `from: flow_input` | Tên input của flow. |
| `step` | string | chỉ khi `from: step` | `steps[].id` đứng trước. Trỏ tới bước sau hoặc chính nó → lỗi validate. |
| `output` | string | chỉ khi `from: step` | Tên output của bước đó. |

Không có hằng số inline, không có biểu thức, không có chuỗi mẫu. Cần biến đổi
dữ liệu giữa hai bước → viết thêm một `tool`, không nhét logic vào YAML.

### 7.4 `output`

Cùng cấu trúc §7.3 nhưng chỉ nhận `from: step`: flow phải trả về kết quả của
một bước cụ thể.

---

## 8. Bất biến mà validate phải bảo đảm

`orchestrators/registry.py` phải làm việc nạp catalog thất bại khi:

1. `type: agent` mà thiếu `tier`.
2. `type: agent` mà `tier` không có trong `configs/tiers.yaml`.
3. `type: tool` mà có `tier`, `model`, `provider`, hoặc `system_prompt`.
4. Bất kỳ file nào có `model` hoặc `provider` (chỉ `tiers.yaml` được phép).
5. `id` trùng nhau giữa hai file bất kỳ trong catalog.
6. `steps[].ref` trỏ tới `id` không tồn tại, hoặc trỏ tới một `flow`.
7. `from: step` trỏ tới bước chưa chạy (bước sau, hoặc chính nó).
8. `from: step` lấy `output` không có trong `outputs` của thành phần được ref.
9. `from: flow_input` lấy `name` không có trong `inputs` của flow.
10. `kind: sequential` mà có `entrypoint`, hoặc `kind: python` mà có `steps`.
11. Trường lạ không nằm trong đặc tả này (`extra = "forbid"`).
