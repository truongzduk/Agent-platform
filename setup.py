#!/usr/bin/env python3
"""setup.py — cách DUY NHẤT để nạp API key vào agent-platform.

Chạy:
    python setup.py                        nhập key lần đầu (menu chọn nhà cung cấp)
    python setup.py --add-provider gemini   thêm một nhà cung cấp mới, không đụng key cũ
    python setup.py --show                  xem nhà nào đã có key (dạng che)
    python setup.py --check                 gọi thử API từng nhà đã cấu hình

Người dùng không cần biết biến môi trường là gì — script tự hỏi, tự ghi
đúng định dạng vào file .env. Key luôn nhập bằng getpass (ẩn ký tự), không
bao giờ được in ra màn hình hay ghi vào log.
"""
import argparse
import getpass
import os
import platform
import sys
from pathlib import Path

# Console mặc định trên Windows (cp1252) không encode được tiếng Việt có dấu
# và emoji -> ép stdout/stderr sang UTF-8 để chạy được trên cả Windows và macOS.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from dotenv import dotenv_values  # noqa: E402

import preflight  # noqa: E402 — dùng lại các hàm tạo file/thư mục còn thiếu

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

OK = "✅"
FAIL = "❌"

PROVIDER_ORDER = ["anthropic", "gemini", "openai"]
PROVIDER_INFO = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "hint": "key bắt đầu bằng 'sk-ant-'",
        "validate": lambda k: k.startswith("sk-ant-") and len(k) >= 20,
    },
    "gemini": {
        "label": "Google Gemini",
        "env_key": "GEMINI_API_KEY",
        "hint": "key bắt đầu bằng 'AIza'",
        "validate": lambda k: k.startswith("AIza") and len(k) >= 30,
    },
    "openai": {
        "label": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "hint": "key bắt đầu bằng 'sk-'",
        "validate": lambda k: k.startswith("sk-") and len(k) >= 20,
    },
}


# ---------------------------------------------------------------------------
# Đọc / ghi .env
# ---------------------------------------------------------------------------

def ensure_skeleton():
    """Bổ sung file/thư mục cấu hình còn thiếu — không bao giờ ghi đè cái đã có."""
    created = []
    preflight.ensure_gitignore(created, verbose=False)
    preflight.ensure_env_example(created, verbose=False)
    preflight.ensure_env(created, verbose=False)
    preflight.ensure_dirs(created, verbose=False)
    if created:
        print("Đã bổ sung file/thư mục cấu hình còn thiếu:")
        for name, path, _desc in created:
            print(f"  - {name} -> {path}")
        print()


def load_env_dict():
    if not ENV_PATH.exists():
        return {}
    return dict(dotenv_values(ENV_PATH))


def save_env_dict(env_dict):
    lines = [f"{name}={env_dict.get(name, '') or ''}" for name in preflight.ENV_VARS]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if platform.system() == "Windows":
        print("⚠️  Windows không hỗ trợ chmod kiểu Unix — bỏ qua bước giới hạn quyền file .env.")
    else:
        try:
            os.chmod(ENV_PATH, 0o600)
        except OSError:
            pass

    print(f"Đã ghi API key vào: {ENV_PATH}")


def mask_key(key: str) -> str:
    if len(key) <= 4:
        return "*" * len(key)
    return "****" + key[-4:]


# ---------------------------------------------------------------------------
# Nhập key cho một nhà cung cấp
# ---------------------------------------------------------------------------

def prompt_provider_key(provider: str, env_dict: dict) -> str:
    info = PROVIDER_INFO[provider]
    existing = (env_dict.get(info["env_key"]) or "").strip()

    if existing:
        print(f"{info['label']}: đã có key {mask_key(existing)}")
        choice = input("Giữ nguyên hay thay mới? [G]iữ / [T]hay (mặc định G): ").strip().lower()
        if choice not in ("t", "thay"):
            print("-> Giữ nguyên key cũ.")
            return existing

    while True:
        raw = getpass.getpass(f"Nhập {info['label']} API key ({info['hint']}): ").strip()
        if not raw:
            print("Key không được để trống. Thử lại.")
            continue
        if not info["validate"](raw):
            print(f"Sai định dạng — {info['hint']}. Thử lại.")
            continue
        return raw


# ---------------------------------------------------------------------------
# Chế độ: setup lần đầu (interactive, không tham số)
# ---------------------------------------------------------------------------

def ask_provider_menu():
    print("Chọn nhà cung cấp muốn cấu hình (chỉ cần ít nhất 1 là đủ chạy toàn hệ thống):")
    for i, p in enumerate(PROVIDER_ORDER, 1):
        print(f"  {i}. {PROVIDER_INFO[p]['label']}")
    while True:
        raw = input("Nhập số lựa chọn, cách nhau bằng dấu phẩy (vd: 1,3): ").strip()
        parts = [x.strip() for x in raw.split(",") if x.strip()]
        chosen = []
        valid = True
        for x in parts:
            if not x.isdigit() or not (1 <= int(x) <= len(PROVIDER_ORDER)):
                valid = False
                break
            chosen.append(PROVIDER_ORDER[int(x) - 1])
        chosen = list(dict.fromkeys(chosen))  # bỏ trùng, giữ thứ tự
        if valid and chosen:
            return chosen
        print(f"Lựa chọn không hợp lệ. Nhập ít nhất một số từ 1 đến {len(PROVIDER_ORDER)}.")


def ask_langfuse(env_dict):
    print()
    print("Cấu hình Langfuse (theo dõi log LLM) — có thể bỏ qua, Enter để điền sau.")
    pub = getpass.getpass("LANGFUSE_PUBLIC_KEY (Enter để bỏ trống): ").strip()
    if pub:
        env_dict["LANGFUSE_PUBLIC_KEY"] = pub
    sec = getpass.getpass("LANGFUSE_SECRET_KEY (Enter để bỏ trống): ").strip()
    if sec:
        env_dict["LANGFUSE_SECRET_KEY"] = sec
    host = input("LANGFUSE_HOST (vd: https://cloud.langfuse.com, Enter để bỏ trống): ").strip()
    if host:
        env_dict["LANGFUSE_HOST"] = host


def ask_defaults(env_dict):
    available = [p for p in PROVIDER_ORDER if (env_dict.get(PROVIDER_INFO[p]["env_key"]) or "").strip()]

    print()
    print("Chọn nhà cung cấp mặc định (DEFAULT_PROVIDER):")
    for i, p in enumerate(available, 1):
        print(f"  {i}. {PROVIDER_INFO[p]['label']}")
    while True:
        raw = input(f"Nhập số (1-{len(available)}): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(available):
            default_provider = available[int(raw) - 1]
            break
        print("Lựa chọn không hợp lệ.")
    env_dict["DEFAULT_PROVIDER"] = default_provider

    model = input(f"Nhập DEFAULT_MODEL cho {PROVIDER_INFO[default_provider]['label']}: ").strip()
    while not model:
        model = input("DEFAULT_MODEL không được để trống, nhập lại: ").strip()
    env_dict["DEFAULT_MODEL"] = model


def run_interactive_setup():
    ensure_skeleton()
    print("=" * 70)
    print("NẠP API KEY CHO AGENT-PLATFORM")
    print("=" * 70)

    env_dict = load_env_dict()

    selected = ask_provider_menu()
    print()
    for provider in selected:
        key = prompt_provider_key(provider, env_dict)
        env_dict[PROVIDER_INFO[provider]["env_key"]] = key

    ask_langfuse(env_dict)
    ask_defaults(env_dict)

    print()
    save_env_dict(env_dict)
    print()
    print("Xong. Chạy `python setup.py --show` để xem lại, hoặc `python setup.py --check` để test API key.")


# ---------------------------------------------------------------------------
# Chế độ: --add-provider
# ---------------------------------------------------------------------------

def run_add_provider(provider: str):
    ensure_skeleton()
    env_dict = load_env_dict()
    key = prompt_provider_key(provider, env_dict)
    env_dict[PROVIDER_INFO[provider]["env_key"]] = key
    save_env_dict(env_dict)


# ---------------------------------------------------------------------------
# Chế độ: --show
# ---------------------------------------------------------------------------

def run_show():
    env_dict = load_env_dict()
    print("Trạng thái API key theo từng nhà cung cấp:")
    for p in PROVIDER_ORDER:
        key = (env_dict.get(PROVIDER_INFO[p]["env_key"]) or "").strip()
        if key:
            print(f"  {OK} {PROVIDER_INFO[p]['label']}: {mask_key(key)}")
        else:
            print(f"  {FAIL} {PROVIDER_INFO[p]['label']}: chưa có key")

    print()
    print(f"DEFAULT_PROVIDER: {env_dict.get('DEFAULT_PROVIDER') or '(chưa đặt)'}")
    print(f"DEFAULT_MODEL: {env_dict.get('DEFAULT_MODEL') or '(chưa đặt)'}")


# ---------------------------------------------------------------------------
# Chế độ: --check — gọi thử API mỗi nhà, max_tokens nhỏ nhất, không log key
# ---------------------------------------------------------------------------

def _describe_error(e: Exception) -> str:
    status = getattr(e, "status_code", None) or getattr(e, "code", None)
    if status:
        return f"{status} {type(e).__name__}"
    return type(e).__name__


def check_anthropic(key: str):
    try:
        import anthropic
    except ImportError:
        return False, "chưa cài thư viện 'anthropic' — chạy pip install -r requirements.txt"
    client = anthropic.Anthropic(api_key=key)
    try:
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True, "ok"
    except anthropic.AuthenticationError:
        return False, "401 sai API key"
    except anthropic.PermissionDeniedError:
        return False, "403 key không đủ quyền"
    except anthropic.NotFoundError:
        return False, "404 model/endpoint không tồn tại"
    except anthropic.RateLimitError:
        return False, "429 rate limit"
    except anthropic.APIStatusError as e:
        return False, f"{e.status_code} lỗi API"
    except anthropic.APIConnectionError:
        return False, "lỗi kết nối mạng"
    except Exception as e:  # phòng trường hợp SDK đổi exception ở version khác
        return False, _describe_error(e)


def check_gemini(key: str):
    try:
        import google.generativeai as genai
    except ImportError:
        return False, "chưa cài thư viện 'google-generativeai' — chạy pip install -r requirements.txt"
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-flash-latest")
        model.generate_content("ping", generation_config={"max_output_tokens": 16})
        return True, "ok"
    except Exception as e:
        return False, _describe_error(e)


def check_openai(key: str):
    try:
        import openai
    except ImportError:
        return False, "chưa cài thư viện 'openai' — chạy pip install -r requirements.txt"
    try:
        client = openai.OpenAI(api_key=key)
        client.responses.create(model="gpt-5.6-luna", input="ping", max_output_tokens=16)
        return True, "ok"
    except Exception as e:
        return False, _describe_error(e)


CHECKERS = {
    "anthropic": check_anthropic,
    "gemini": check_gemini,
    "openai": check_openai,
}


def run_check():
    env_dict = load_env_dict()
    configured = [p for p in PROVIDER_ORDER if (env_dict.get(PROVIDER_INFO[p]["env_key"]) or "").strip()]
    if not configured:
        print("Chưa có nhà cung cấp nào được cấu hình key. Chạy `python setup.py` trước.")
        return

    print("Đang gọi thử API của từng nhà cung cấp đã cấu hình (không in key)...")
    for p in configured:
        key = env_dict[PROVIDER_INFO[p]["env_key"]]
        ok, detail = CHECKERS[p](key)
        mark = OK if ok else FAIL
        print(f"  {mark} {PROVIDER_INFO[p]['label']}: {detail}")


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Nạp và quản lý API key cho agent-platform.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--add-provider", choices=PROVIDER_ORDER, help="Thêm key cho một nhà cung cấp, không đụng key khác.")
    group.add_argument("--show", action="store_true", help="Liệt kê nhà nào đã có key (dạng che).")
    group.add_argument("--check", action="store_true", help="Gọi thử API của các nhà đã cấu hình.")
    args = parser.parse_args()

    try:
        if args.add_provider:
            run_add_provider(args.add_provider)
        elif args.show:
            run_show()
        elif args.check:
            run_check()
        else:
            run_interactive_setup()
    except KeyboardInterrupt:
        print("\nĐã huỷ.")
        sys.exit(1)


if __name__ == "__main__":
    main()
