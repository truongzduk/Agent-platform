# Setup máy — checklist trước khi chạy agent-platform

Làm theo đúng thứ tự dưới đây. Mỗi bước tick xong mới sang bước tiếp theo.

## 1. Docker Desktop

- [ ] Tải và cài Docker Desktop: https://www.docker.com/products/docker-desktop/
- [ ] Mở ứng dụng Docker Desktop lên, đợi biểu tượng cá voi ở khay hệ thống chạy ổn định (nghĩa là daemon đã chạy)
- [ ] Kiểm tra lại bằng cách chạy `python preflight.py` — mục Docker phải hiện ✅

## 2. Git + repo private tên `agent-platform`

- [ ] Cài Git: https://git-scm.com/downloads
- [ ] Tạo tài khoản GitHub nếu chưa có
- [ ] Tạo một repository mới tên **agent-platform**, chọn chế độ **Private** (không phải Public)
- [ ] Trên máy, khởi tạo git trong thư mục dự án và nối vào repo đó (bạn tự chạy các lệnh git — script preflight sẽ không tự chạy git giúp bạn)

## 3. VS Code + Claude Code

- [ ] Cài VS Code: https://code.visualstudio.com/
- [ ] Cài extension Claude Code trong VS Code (hoặc CLI Claude Code)
- [ ] Đăng nhập Claude Code bằng tài khoản của bạn

## 4. Tạo API key

Bạn chỉ cần **ít nhất MỘT** trong ba nhà cung cấp dưới đây là đã chạy được toàn bộ hệ thống. Muốn thêm nhà khác lúc nào cũng được, không cần làm lại từ đầu.

- [ ] **Anthropic (Claude)**: tạo API key tại https://console.anthropic.com/
- [ ] **Google Gemini**: tạo API key tại https://aistudio.google.com/apikey
- [ ] **OpenAI**: tạo API key tại https://platform.openai.com/api-keys

**Quan trọng nhất — đặt spend limit (giới hạn chi tiêu) hàng tháng ở console của nhà bạn chọn, ví dụ 50 USD.** Đây là phanh an toàn quan trọng nhất của cả dự án: nếu agent chạy lỗi vòng lặp hay bị lạm dụng, spend limit chặn hoá đơn tăng vọt ngoài kiểm soát. Đừng bỏ qua bước này dù chỉ dùng thử.

Ở bước này bạn **chưa cần dán key vào đâu cả** — chỉ cần tạo key và copy tạm ra. Việc nhập key vào hệ thống sẽ làm ở bước sau, bằng lệnh `python setup.py` (chạy trong terminal, key được nhập ẩn ký tự, không lộ ra chat hay file nào).

## Bước tiếp theo

Sau khi xong 4 bước trên:

1. Chạy `python preflight.py` để kiểm tra máy đã đủ điều kiện chưa.
2. Chạy `python setup.py` để nhập API key vào hệ thống.
