# agent-platform

Nền tảng AI agent nội bộ. Mỗi project có một orchestrator (agent tổng) gọi
các task agent; harness bọc mọi lời gọi để kiểm soát/log thống nhất.

## Thư mục dùng làm gì

- `agents/` — code của từng task agent (agent làm một việc cụ thể).
- `llm/` — lớp gọi LLM duy nhất; mọi lời gọi tới Anthropic/Gemini/OpenAI đều đi qua đây. `core.py` của agent không bao giờ gọi thẳng SDK nhà cung cấp.
- `harness/` — bọc và kiểm soát mọi lời gọi của agent (logging, giới hạn, an toàn).
- `orchestrators/` — agent tổng điều phối, gọi các task agent theo từng project.
- `serve/` — code phục vụ API/HTTP (FastAPI) để chạy agent qua web.
- `configs/` — file YAML cấu hình provider/model/project. Đổi provider, đổi model, thêm project = sửa file ở đây, không sửa code.
- `evals/` — script đánh giá chất lượng agent.

## File gốc

- `preflight.py` — kiểm tra máy đã đủ điều kiện chạy dự án chưa (Python, Docker, Git...), tự tạo file/thư mục cấu hình còn thiếu.
- `setup.py` — cách duy nhất để nhập API key vào hệ thống.
- `settings.py` — điểm duy nhất đọc file `.env`; mọi module khác phải import từ đây.
- `docker-compose.yml` — khung Docker Compose (hiện chỉ là placeholder, chưa có service).
- `.env.example` / `.env` — danh sách biến môi trường cần có; `.env` chứa giá trị thật, không commit lên Git.

## Cách chạy setup.py

1. `python preflight.py` — kiểm tra máy, tự tạo các file cấu hình còn thiếu.
2. `pip install -r requirements.txt` — cài thư viện cần thiết.
3. `python setup.py` — chọn nhà cung cấp (Anthropic / Gemini / OpenAI), nhập API key (ẩn ký tự khi gõ). Chỉ cần ít nhất một nhà là chạy được toàn hệ thống.
4. `python setup.py --show` — xem nhà nào đã có key (dạng che, không hiện đầy đủ).
5. `python setup.py --check` — gọi thử API của các nhà đã cấu hình để xác nhận key hoạt động.

## Cách thêm nhà cung cấp sau

Chạy `python setup.py --add-provider gemini` (hoặc `openai` / `anthropic`) — chỉ thêm key cho nhà đó, không đụng đến key đã có sẵn. Không cần sửa code, không cần chạy lại toàn bộ setup.
