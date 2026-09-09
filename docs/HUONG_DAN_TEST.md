# Hướng dẫn test và thao tác thủ công

Hướng dẫn này chia làm 4 tầng, từ không cần API key đến chạy thật. Mọi lệnh
trong file đã được chạy thử trên máy Windows + Python 3.14 của repo này.

| Tầng | Cần API key? | Dùng khi |
|---|---|---|
| 1. Test tự động | Không | Trước mỗi lần commit |
| 2. Thao tác thủ công từng lớp | Không | Đang viết tool/agent mới, cần soi từng bước |
| 3. Thao tác thủ công qua HTTP | Không (giả lập) | Kiểm tra contract HTTP, hội thoại, background run |
| 4. Chạy thật | **Có** | Nghiệm thu, đo token/chi phí thật |

Quy ước: mọi lệnh chạy từ thư mục gốc repo. Trên máy này `pytest` **không** nằm
trong PATH — luôn gọi `python -m pytest`.

---

## Tầng 1 — Test tự động

```bash
python -m pytest -q                        # toàn bộ
python -m pytest tests/test_flow_runner.py -v   # một file, xem tên từng test
python -m pytest -k "tier" -v              # lọc theo tên
```

Kết quả đúng hiện tại: **38 passed, 1 skipped**. Test bị skip là test symlink —
Windows cần bật Developer Mode mới tạo được symlink; skip là bình thường.

Mỗi file test chứng minh điều gì:

| File | Chứng minh |
|---|---|
| `tests/test_resolve_path.py` | Agent không thoát được ra ngoài workspace của run (`..`, `C:\Windows\...`, `/etc/passwd`, symlink) |
| `tests/test_registry.py` | Tool và agent có schema KHÁC nhau: agent thiếu `tier` là lỗi, tool có `tier`/`model` là lỗi, tier lạ là lỗi |
| `tests/test_flow_runner.py` | Flow 2 bước chạy đúng thứ tự, nối được output→input, tier lấy từ YAML |
| `tests/test_usage.py` | Chỉ bước agent bị tính token; bước tool đếm riêng |

**Không có test nào được gọi API thật.** Nếu bạn thêm test mà nó chậm bất
thường hoặc cần mạng, tức là bạn quên mock — LLM giả luôn được truyền vào qua
tham số `complete`.

---

## Tầng 2 — Thao tác thủ công từng lớp (không cần API key)

Dùng khi bạn vừa viết một tool/agent mới và muốn soi từng lớp một, thay vì chạy
cả hệ rồi đoán chỗ hỏng. Thứ tự dưới đây đi từ trong ra ngoài.

### 2.1 Chạy một TOOL trực tiếp

Tool không gọi LLM nên chạy được ngay, không cần gì cả.

```bash
python -c "
import tempfile, pathlib
from harness.run_context import RunContext
from tools.upper_text import run
ctx = RunContext.create('thu_tay', runs_dir=pathlib.Path(tempfile.mkdtemp()))
print(run({'text': 'xin chao cac ban'}, ctx))
"
```

Kết quả: `{'text': 'XIN CHAO CAC BAN'}`

`runs_dir=tempfile.mkdtemp()` để không rác thư mục `runs/` thật. Bỏ tham số đó
đi nếu bạn muốn xem file được ghi ở đâu trong `runs/`.

### 2.2 Chạy một AGENT trực tiếp, với LLM giả

Đây là cách soi **agent gửi gì lên LLM** — thứ hay sai nhất khi viết agent mới.

```bash
python -c "
import tempfile, pathlib
from harness.run_context import RunContext
from orchestrators.registry import load_registry
from llm.client import Completion
from agents.summarize_text.agent import run

def gia(messages, *, system=None, max_tokens=None):
    print('  agent gui len LLM :', messages[0]['content'][:60])
    print('  system prompt     :', (system or '')[:60], '...')
    return Completion('Day la tom tat gia.', 12, 5, 'fast', 'model-gia')

spec = load_registry().agents['summarize_text']
ctx = RunContext.create('thu_agent', runs_dir=pathlib.Path(tempfile.mkdtemp()))
print(run({'text':'noi dung dai'}, ctx, spec, gia))
print('file da ghi:', (ctx.workspace_dir/'output'/'summary.txt').read_text(encoding='utf-8'))
"
```

Chú ý chữ ký `gia(messages, *, system, max_tokens)` — **không có tham số
`tier`**. Đó là bằng chứng cấu trúc: agent nhận `complete` đã bị kẹp sẵn tier,
nó không chọn được tier và không thấy tên model.

Kiểm tra khi viết agent mới: system prompt in ra có đúng chuỗi trong YAML
không? Nếu ra rỗng là bạn quên dùng `spec.system_prompt`, hoặc quên khai
`system_prompt` trong file YAML.

### 2.3 Chạy cả FLOW, xem thứ tự bước và usage

```bash
python -c "
import tempfile, pathlib, json
from harness.run_context import RunContext
from harness.usage import RunUsage
from llm.client import Completion
from orchestrators import flow_runner
from orchestrators.registry import load_registry

nhat_ky = []
def gia(tier, messages, *, system=None, max_tokens=None):
    nhat_ky.append(('agent', tier, messages[0]['content']))
    return Completion('Tom tat gia.', 12, 5, tier, 'model-gia')

reg = load_registry()
ctx = RunContext.create('thu_flow', runs_dir=pathlib.Path(tempfile.mkdtemp()))
usage = RunUsage(run_id=ctx.run_id, flow_id='demo_two_step')
kq = flow_runner.run_flow('demo_two_step', {'text':'xin chao'}, registry=reg, ctx=ctx,
                          usage=usage, complete=gia,
                          on_status=lambda s: nhat_ky.append(('status', s)))
print('nhat ky :', nhat_ky)
print('ket qua :', kq['output'])
print('index   :', json.dumps(usage.to_index_record('done'), ensure_ascii=False))
"
```

Kết quả đúng:

```
nhat ky : [('status', 'running'), ('agent', 'fast', 'XIN CHAO'), ('status', 'done')]
ket qua : Tom tat gia.
index   : {... "tool_steps": 1, "agent_steps": 1, "total_tokens": 17,
           "tiers": {"fast": {"calls": 1, ...}} ...}
```

Ba thứ cần đọc kỹ trong nhật ký:

1. `('agent','fast','XIN CHAO')` — agent nhận chuỗi **đã viết hoa**, tức là
   bước tool chạy trước và output đã nối sang input. Nếu thấy `'xin chao'`
   thường là bạn nối sai `from: step` trong YAML.
2. `status` đi đúng `running → done`. Nếu flow lỗi sẽ là `running → error`.
3. `tool_steps: 1` nhưng chỉ có tier `fast` trong `tiers` — bước tool **không**
   sinh token. Đây là bất biến quan trọng nhất của hệ.

### 2.4 Kiểm tra registry chặn đúng chỗ

Thử làm sai có chủ đích trên một **bản sao** của `configs/`, không đụng file thật:

```bash
python -c "
import shutil, pathlib, tempfile
from orchestrators.registry import load_registry, RegistryError
dst = pathlib.Path(tempfile.mkdtemp())/'configs'
shutil.copytree('configs', dst)
f = dst/'tools'/'upper_text.yaml'
f.write_text(f.read_text(encoding='utf-8').replace('type: tool','type: tool\ntier: fast'), encoding='utf-8')
try:
    load_registry(dst)
    print('SAI: le ra phai loi')
except RegistryError as e:
    print('DUNG:', str(e)[:120])
"
```

Kết quả đúng: `DUNG: ...upper_text.yaml: 'tier' là trường chỉ dành cho type: agent...`

Đổi dòng `.replace(...)` để thử các lỗi khác: thêm `model: abc` vào agent, đổi
`tier: fast` thành `tier: turbo`, đổi `ref:` sang id không tồn tại. Tất cả phải
raise `RegistryError` **lúc nạp catalog**, không phải lúc chạy.

### 2.5 Kiểm tra rào chắn đường dẫn

```bash
python -c "
import tempfile, pathlib
from harness.run_context import RunContext
ctx = RunContext.create('thu_path', runs_dir=pathlib.Path(tempfile.mkdtemp()))
for xau in ['../../etc/passwd', r'C:\Windows\System32', 'output/../../thoat.txt']:
    try:
        ctx.resolve_path(xau); print('SAI - lot luoi:', xau)
    except PermissionError as e:
        print('CHAN DUNG:', xau)
print('hop le  :', ctx.resolve_path('output/kq.json'))
"
```

---

## Tầng 3 — Thao tác thủ công qua HTTP, không cần API key

Tầng này kiểm tra contract HTTP, trí nhớ hội thoại, và việc chạy nền — mà không
cần key thật. Cách làm: mồi cache của `settings` bằng giá trị giả và thay
`llm.client.complete` bằng hàm giả.

Lưu đoạn sau thành `smoke.py` (file dùng một lần, xoá sau khi test — **đừng**
commit):

```python
import json, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import settings
settings._cache = {                      # mồi cache -> không đụng .env
    "ANTHROPIC_API_KEY": "fake", "GEMINI_API_KEY": None, "OPENAI_API_KEY": None,
    "DEFAULT_PROVIDER": None, "DEFAULT_MODEL": None,
    "LANGFUSE_PUBLIC_KEY": None, "LANGFUSE_SECRET_KEY": None, "LANGFUSE_HOST": None,
    "API_BEARER_TOKEN": "token-kiem-chung",
    "AVAILABLE_PROVIDERS": ["anthropic"],
}

import llm.client
from llm.client import Completion


def fake_complete(tier, messages, *, system=None, max_tokens=None):
    if system and "CATALOG" in system:            # lượt CHỌN của orchestrator
        last = messages[-1]["content"]
        if "demo" in last.lower():
            body = json.dumps({"action": "run", "target": "demo_two_step",
                               "inputs": {"text": last}})
        else:
            body = json.dumps({"action": "reply",
                               "message": f"Da nhan {len(messages)} tin nhan."})
        return Completion(body, 30, 12, tier, "model-gia")
    return Completion("Day la ban tom tat mot cau.", 11, 7, tier, "model-gia")


llm.client.complete = fake_complete

from fastapi.testclient import TestClient
import serve.app as app_mod

client = TestClient(app_mod.app)
AUTH = {"Authorization": "Bearer token-kiem-chung"}

print("health          :", client.get("/v1/health").json())
print("catalog no token:", client.get("/v1/catalog").status_code, "(mong doi 401)")
for it in client.get("/v1/catalog", headers=AUTH).json():
    print("   ", it["id"], "| type =", it["type"], "| tier =", it["tier"])

r1 = client.post("/v1/messages", headers=AUTH,
                 json={"session_id": "s1", "text": "Xin chao, toi ten Long."})
r2 = client.post("/v1/messages", headers=AUTH,
                 json={"session_id": "s1", "text": "Toi vua noi gi?"})
print("luot 1:", r1.json()["reply"])
print("luot 2:", r2.json()["reply"], "  <- so tin nhan tang = da nho luot truoc")

r3 = client.post("/v1/messages", headers=AUTH,
                 json={"session_id": "s2", "text": "chay demo voi cau nay"})
run_id = r3.json()["run_id"]
for _ in range(50):
    run = client.get(f"/v1/runs/{run_id}", headers=AUTH).json()
    if run["status"] in ("done", "error"):
        break
    time.sleep(0.1)
print("run:", run["status"], "| output =", run["result"]["output"])
print("usage:", json.dumps(run["usage"]["tiers"], ensure_ascii=False))
print("tool_steps =", run["usage"]["tool_steps"], "| agent_steps =", run["usage"]["agent_steps"])
print("index.jsonl dong cuoi:", (ROOT/"runs"/"index.jsonl").read_text(encoding="utf-8").splitlines()[-1])
```

Chạy: `python smoke.py`

Kết quả đúng:

```
health          : {'status': 'ok'}
catalog no token: 401 (mong doi 401)
    upper_text | type = tool  | tier = None
    summarize_text | type = agent | tier = fast
    demo_two_step | type = flow  | tier = None
luot 1: Da nhan 1 tin nhan.
luot 2: Da nhan 3 tin nhan.   <- 3 = user1 + assistant1 + user2
run: done | output = Day la ban tom tat mot cau.
usage: {"fast": {"calls": 1, "input_tokens": 11, "output_tokens": 7, ...}}
tool_steps = 1 | agent_steps = 1
```

`Da nhan 3 tin nhan` ở lượt 2 chính là bằng chứng hội thoại có trí nhớ: lịch sử
gửi lên LLM gồm cả lượt trước, khoá theo `session_id`.

### Soi orchestrator hội thoại chọn gì

Khi orchestrator chọn sai thành phần, chạy đoạn này để xem nó thấy gì:

```bash
python -c "
import json
from llm.client import Completion
from orchestrators import chat
from orchestrators.registry import load_registry

def gia(tier, messages, *, system=None, max_tokens=None):
    print('tier dung de chon :', tier)
    print('catalog gui cho LLM:')
    for t in json.loads(system.split('CATALOG:')[1]):
        print('   -', t['name'], '|', t['kind'], '|', t['description'][:60])
    print('lich su gui len   :', [m['role'] for m in messages])
    return Completion(json.dumps({'action':'run','target':'demo_two_step','inputs':{'text':'abc'}}), 30, 10, tier, 'model-gia')

kq = chat.handle_message([{'role':'user','content':'tom tat giup toi'}], load_registry(), complete=gia)
print('-> chon:', kq.target, '| kind:', kq.target_kind, '| inputs:', kq.inputs)
"
```

Orchestrator chọn dựa **hoàn toàn** vào trường `description` trong YAML. Chọn
sai gần như luôn là do `description` mơ hồ hoặc trùng ý với thành phần khác —
sửa YAML, không sửa code.

---

## Tầng 4 — Chạy thật với API key

### 4.1 Ba việc phải làm trước, theo đúng thứ tự

**a) Điền `configs/tiers.yaml`.** Hiện `provider` và `model` của cả ba tier đang
để trống. Điền tối thiểu tier bạn định dùng: `provider` là một id trong
`configs/providers.yaml` (`anthropic`/`gemini`/`openai`), `model` là tên model
chép nguyên văn từ tài liệu provider, và hai dòng `cost_per_1m_*_usd` nếu muốn
cột chi phí trong `runs/index.jsonl` khác `null`.

Lưu ý: orchestrator hội thoại dùng tier **`standard`** để chọn thành phần, còn
agent mẫu dùng tier `fast`. Muốn chạy hết luồng thì phải điền **cả hai** tier.

**b) Nạp API key provider:**

```bash
python setup.py                    # nhập key, ký tự bị ẩn
python setup.py --show             # liệt kê nhà nào đã có key (dạng che)
python setup.py --check            # gọi thử API thật để xác nhận key sống
```

**c) Đặt `API_BEARER_TOKEN` trong `.env` — phải làm THỦ CÔNG.**

> `setup.py` chỉ quản lý key của provider, **không** sinh `API_BEARER_TOKEN`.
> `preflight.py` chỉ tạo dòng trống cho biến này. Bạn phải tự sinh và tự dán
> giá trị vào `.env`.

Sinh một token ngẫu nhiên:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Rồi tự mở `.env` và sửa dòng `API_BEARER_TOKEN=` thành `API_BEARER_TOKEN=<giá
trị vừa sinh>`.

Xác nhận cấu hình đã đủ (lệnh này **không** in ra key, chỉ in có/không):

```bash
python -c "
import settings
print('providers co key:', settings.AVAILABLE_PROVIDERS)
print('bearer token da dat:', bool(settings.API_BEARER_TOKEN))
"
```

Cả hai dòng phải khác rỗng/`False` thì mới sang bước sau được. Chừng nào
`AVAILABLE_PROVIDERS` còn rỗng thì **mọi** endpoint có auth đều trả 500, kể cả
`/v1/catalog` vốn không cần LLM — vì `settings.load()` raise trước khi kịp so
token.

### 4.2 Khởi động server

```bash
python -m uvicorn serve.app:app --host 127.0.0.1 --port 8000
```

Mở một terminal thứ hai để gọi API.

### 4.3 Gọi API — Git Bash

```bash
TOKEN='<token vua dat trong .env>'

curl http://127.0.0.1:8000/v1/health

curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/v1/catalog

curl -X POST http://127.0.0.1:8000/v1/messages \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"session_id":"s1","text":"tom tat giup toi doan van sau: ..."}'

curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/v1/runs/<run_id>
```

### 4.3b Gọi API — PowerShell

Trong PowerShell, `curl` là bí danh của `Invoke-WebRequest` và **không** nhận cú
pháp `-H`/`-d` của curl. Dùng `Invoke-RestMethod`:

```powershell
$TOKEN = '<token vua dat trong .env>'
$H = @{ Authorization = "Bearer $TOKEN" }

Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/health

Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/catalog -Headers $H |
    Format-Table id, type, tier, name

$body = @{ session_id = 's1'; text = 'tom tat giup toi doan van sau: ...' } | ConvertTo-Json
$r = Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/messages -Method Post `
        -Headers $H -ContentType 'application/json' -Body $body
$r

Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($r.run_id)" -Headers $H |
    ConvertTo-Json -Depth 6
```

### 4.4 Kiểm tra kết quả một run

Run chạy nền, nên `POST /v1/messages` trả `run_id` ngay còn kết quả đến sau.
Gọi lại `GET /v1/runs/{run_id}` tới khi `status` là `done` hoặc `error`.

Ba nơi cần đối chiếu sau mỗi run:

```bash
tail -1 runs/index.jsonl                    # dòng sổ cái: token, chi phí, tool_steps
ls runs/<run_id>/output/                    # file agent đã ghi
cat runs/<run_id>/output/summary.txt
```

Đọc dòng `index.jsonl` và tự hỏi: số token có đúng cỡ bạn nghĩ không? Tier có
đúng là tier bạn khai trong YAML không? `tool_steps` có khớp số bước tool trong
flow không? Sai một trong ba là có lỗi ở tầng dưới.

### 4.5 Kiểm chứng cơ chế tier bằng tay

Đây là bài test đáng giá nhất của cả kiến trúc:

1. Chạy `demo_two_step` một lần, xem tier trong `runs/index.jsonl` là `fast`.
2. Mở `configs/agents/summarize_text.yaml`, đổi `tier: fast` thành `tier: deep`.
3. Khởi động lại server, chạy lại.
4. Dòng mới trong `index.jsonl` phải sang tier `deep`.

**Không sửa một dòng code nào.** Nếu phải sửa code mới đổi được model, tức là
có chỗ nào đó đã lách qua lớp tier — đó là lỗi kiến trúc, phải sửa ngay.

---

## Bảng triệu chứng → nguyên nhân

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Mọi endpoint có auth trả **500**, `/v1/health` vẫn 200 | `.env` chưa có API key provider nào → `settings.load()` raise | Chạy `python setup.py` |
| **500** với thông báo `API_BEARER_TOKEN chưa được cấu hình` | Có key provider nhưng dòng `API_BEARER_TOKEN=` trong `.env` còn trống | Tự sinh và dán token, xem §4.1c |
| **401** | Thiếu header, sai định dạng, hoặc token không khớp | Kiểm tra header đúng dạng `Bearer <token>` |
| Reply là `Chưa chọn được thành phần vì lớp LLM chưa dùng được: TierNotConfiguredError` | `configs/tiers.yaml` chưa điền `provider`/`model` cho tier `standard` | Điền tiers.yaml, xem §4.1a |
| Reply là `... ProviderUnavailableError` | Tier trỏ tới provider chưa có key, hoặc `enabled: false` | Đối chiếu tiers.yaml ↔ providers.yaml ↔ `AVAILABLE_PROVIDERS` |
| `RegistryError: tier 'xxx' không có trong configs/tiers.yaml` | Agent khai tier lạ | Sửa `tier` trong YAML của agent |
| `RegistryError: 'tier' là trường chỉ dành cho type: agent` | Đặt `tier` vào file trong `configs/tools/` | Bỏ `tier`, hoặc chuyển thành agent nếu nó thật sự gọi LLM |
| `LimitExceeded` | Run vượt trần số lời gọi LLM / tổng token / thời gian | Xem lại flow; trần đặt trong `harness/limits.py` |
| `PermissionError` khi agent đọc/ghi file | Agent thử thoát ra ngoài workspace | Dùng đường dẫn tương đối qua `ctx.resolve_path()` |
| `status` mắc kẹt ở `queued` | Task nền chưa chạy hoặc đã chết trước khi kịp đổi status | Xem log của uvicorn ở terminal đang chạy server |
| `ModuleNotFoundError` khi chạy test | Gọi `pytest` trần thay vì `python -m pytest` | Dùng `python -m pytest` |

---

## Checklist hồi quy trước khi giao việc cho người khác

- [ ] `python -m pytest -q` → 38 passed, 1 skipped, không có lỗi mạng
- [ ] `python -c "from orchestrators.registry import load_registry; load_registry()"` chạy không lỗi
- [ ] `python -m uvicorn serve.app:app --host 127.0.0.1 --port 8000` khởi động không traceback
- [ ] `/v1/health` trả `{"status":"ok"}` khi **không** gửi token
- [ ] `/v1/catalog` liệt kê đủ tool (`tier: null`) + agent (`tier` có giá trị) + flow
- [ ] Hai tin nhắn cùng `session_id` → lượt 2 thấy được nội dung lượt 1
- [ ] Chạy một flow → `runs/index.jsonl` thêm **đúng một** dòng
- [ ] Trong dòng đó: token chỉ thuộc tier của agent, `tool_steps` đếm riêng
- [ ] Đổi tier trong YAML → tier trong `index.jsonl` đổi theo, **0 dòng code sửa**
- [ ] `grep -rniE "claude-|gpt-|gemini-" configs/ agents/ tools/ orchestrators/ harness/ serve/` chỉ ra kết quả trong `configs/tiers.yaml`
- [ ] Đã xoá `smoke.py` và các thư mục `runs/thu_*` sinh ra lúc test tay
