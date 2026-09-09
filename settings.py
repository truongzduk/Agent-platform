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

# Tên các hằng vẫn được export như trước; điểm khác duy nhất là chúng được nạp
# LAZY (lần đầu có ai đó đọc tới) thay vì raise ngay lúc import. Nhờ vậy test
# và `import serve.app` chạy được trên máy chưa có .env, còn code gọi LLM thật
# vẫn nhận đúng lỗi cũ vào đúng lúc nó cần key.
_cache: "dict[str, object] | None" = None


def load(*, force: bool = False) -> "dict[str, object]":
    """Đọc .env một lần rồi cache. Raise nếu thiếu .env hoặc không có key nào."""
    global _cache
    if _cache is not None and not force:
        return _cache

    if not ENV_PATH.exists():
        raise RuntimeError(
            f"Không tìm thấy file .env tại {ENV_PATH}. "
            "Chạy `python setup.py` để nạp API key."
        )

    load_dotenv(ENV_PATH, override=True)

    values: "dict[str, object]" = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY") or None,
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY") or None,
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY") or None,
        "DEFAULT_PROVIDER": os.getenv("DEFAULT_PROVIDER") or None,
        "DEFAULT_MODEL": os.getenv("DEFAULT_MODEL") or None,
        "LANGFUSE_PUBLIC_KEY": os.getenv("LANGFUSE_PUBLIC_KEY") or None,
        "LANGFUSE_SECRET_KEY": os.getenv("LANGFUSE_SECRET_KEY") or None,
        "LANGFUSE_HOST": os.getenv("LANGFUSE_HOST") or None,
        "API_BEARER_TOKEN": os.getenv("API_BEARER_TOKEN") or None,
    }

    # Chỉ liệt kê nhà cung cấp nào THỰC SỰ có key — llm/ sẽ chỉ được phép
    # dùng những nhà trong danh sách này.
    provider_keys = {
        "anthropic": values["ANTHROPIC_API_KEY"],
        "gemini": values["GEMINI_API_KEY"],
        "openai": values["OPENAI_API_KEY"],
    }
    values["AVAILABLE_PROVIDERS"] = [n for n, key in provider_keys.items() if key]

    if not values["AVAILABLE_PROVIDERS"]:
        raise RuntimeError(
            "Chưa có nhà cung cấp LLM nào được cấu hình API key. "
            "Chạy `python setup.py` để nạp API key."
        )

    _cache = values
    return _cache


_LAZY_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "DEFAULT_PROVIDER",
        "DEFAULT_MODEL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "API_BEARER_TOKEN",
        "AVAILABLE_PROVIDERS",
    }
)


def __getattr__(name: str):
    """PEP 562: `settings.API_BEARER_TOKEN` vẫn viết như cũ, nhưng nạp lazy."""
    if name in _LAZY_NAMES:
        return load()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
