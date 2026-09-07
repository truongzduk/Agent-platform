"""settings.py — điểm DUY NHẤT đọc file .env trong toàn bộ dự án.

Mọi module khác (agents/, llm/, harness/, orchestrators/, serve/) PHẢI
import biến/hàm từ đây, KHÔNG được gọi os.getenv() trực tiếp — như vậy
đổi cách nạp cấu hình sau này chỉ cần sửa một file.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Console mặc định trên Windows (cp1252) không encode được tiếng Việt có dấu
# trong thông báo lỗi bên dưới -> ép stdout/stderr sang UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"

if not ENV_PATH.exists():
    raise RuntimeError(
        f"Không tìm thấy file .env tại {ENV_PATH}. "
        "Chạy `python setup.py` để nạp API key."
    )

load_dotenv(ENV_PATH, override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or None
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or None

DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER") or None
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL") or None

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY") or None
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY") or None
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST") or None

API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN") or None

# Chỉ liệt kê nhà cung cấp nào THỰC SỰ có key — llm/ sẽ chỉ được phép
# dùng những nhà trong danh sách này.
_PROVIDER_KEYS = {
    "anthropic": ANTHROPIC_API_KEY,
    "gemini": GEMINI_API_KEY,
    "openai": OPENAI_API_KEY,
}
AVAILABLE_PROVIDERS = [name for name, key in _PROVIDER_KEYS.items() if key]

if not AVAILABLE_PROVIDERS:
    raise RuntimeError(
        "Chưa có nhà cung cấp LLM nào được cấu hình API key. "
        "Chạy `python setup.py` để nạp API key."
    )
