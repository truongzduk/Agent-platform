#!/usr/bin/env python3
"""Preflight check cho agent-platform.

Chạy: python preflight.py
Chỉ dùng thư viện chuẩn của Python (không phụ thuộc requirements.txt),
vì mục đích của script là kiểm tra máy TRƯỚC KHI cài bất kỳ thứ gì.

Script này:
1. Kiểm tra các điều kiện hệ thống (Python, Docker, Git...) và in bảng ✅/❌.
2. Tạo các file/thư mục cấu hình còn thiếu (không bao giờ ghi đè file đã có).

KHÔNG tự cài phần mềm, KHÔNG tự chạy lệnh git thay đổi trạng thái repo.
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Console mặc định trên Windows (cp1252) không encode được tiếng Việt có dấu
# và emoji (✅❌➖) -> ép stdout/stderr sang UTF-8 để chạy được trên cả Windows và macOS.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

ROOT = Path(__file__).resolve().parent

OK = "✅"
FAIL = "❌"
SKIP = "➖"

# Thư mục Python (được import như package) -> có __init__.py rỗng.
# configs/ chỉ chứa file YAML, không phải package Python nên không cần __init__.py.
PACKAGE_DIRS = ["agents", "llm", "harness", "orchestrators", "serve", "evals"]
DATA_ONLY_DIRS = ["configs"]

ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "DEFAULT_PROVIDER",
    "DEFAULT_MODEL",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "API_BEARER_TOKEN",
]

DIR_DESCRIPTIONS = {
    "agents": "Chứa code của từng task agent (agent làm một việc cụ thể).",
    "llm": "Lớp gọi LLM duy nhất — mọi lời gọi tới Anthropic/Gemini/OpenAI đều đi qua đây.",
    "harness": "Bọc và kiểm soát mọi lời gọi của agent (logging, giới hạn, an toàn).",
    "orchestrators": "Chứa agent tổng điều phối, gọi các task agent theo từng project.",
    "serve": "Code phục vụ API/HTTP để chạy agent qua web.",
    "configs": "Chứa file YAML cấu hình provider/model/project — đổi ở đây, không sửa code.",
    "evals": "Chứa script đánh giá chất lượng agent.",
}


def run(cmd):
    """Chạy lệnh, không bao giờ raise — trả về (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        return 1, "", str(e)


# ---------------------------------------------------------------------------
# Các hàm kiểm tra. Mỗi hàm trả về (status, chi_tiet, huong_dan_khac_phuc)
# status: True = đạt, False = không đạt, None = không xác định được (bỏ qua mềm)
# ---------------------------------------------------------------------------

def check_python():
    ok = sys.version_info >= (3, 11)
    detail = f"phiên bản {platform.python_version()}"
    fix = "Cài Python >= 3.11 từ https://www.python.org/downloads/ rồi chạy lại preflight.py."
    return ok, detail, fix


def check_git_installed():
    path = shutil.which("git")
    ok = path is not None
    detail = path or "không tìm thấy lệnh git"
    fix = "Cài Git từ https://git-scm.com/downloads rồi mở terminal mới và chạy lại."
    return ok, detail, fix


def check_docker_installed_and_running():
    path = shutil.which("docker")
    if not path:
        fix = (
            "Cài Docker Desktop từ https://www.docker.com/products/docker-desktop/, "
            "mở ứng dụng lên rồi chạy lại preflight.py."
        )
        return False, "không tìm thấy lệnh docker", fix
    code, _out, _err = run(["docker", "info"])
    if code != 0:
        fix = "Mở ứng dụng Docker Desktop lên và đợi nó khởi động xong rồi chạy lại preflight.py."
        return False, "đã cài nhưng daemon chưa chạy", fix
    return True, "đã cài và daemon đang chạy", ""


def check_docker_compose_v2():
    if not shutil.which("docker"):
        fix = "Cài Docker Desktop trước (Docker Compose v2 đi kèm sẵn trong đó)."
        return False, "chưa có lệnh docker", fix
    code, out, _err = run(["docker", "compose", "version"])
    if code != 0:
        fix = (
            "Cập nhật Docker Desktop lên bản mới nhất — Docker Compose v2 (lệnh "
            "'docker compose') đi kèm sẵn trong Docker Desktop."
        )
        return False, "không dùng được lệnh 'docker compose'", fix
    detail = out.splitlines()[0] if out else "ok"
    return True, detail, ""


def check_in_git_repo():
    code, out, _err = run(["git", "rev-parse", "--is-inside-work-tree"])
    ok = code == 0 and out.strip() == "true"
    fix = (
        "Bạn chưa đứng trong một thư mục git repo. Tự chạy tay lệnh 'git init' "
        "trong thư mục dự án (script này sẽ không tự chạy git cho bạn)."
    )
    return ok, ("có" if ok else "không"), fix


def check_remote_private():
    code, out, _err = run(["git", "remote", "get-url", "origin"])
    if code != 0 or not out:
        fix = (
            "Chưa có remote 'origin' để kiểm tra. Tạo repo private tên agent-platform "
            "trên GitHub rồi chạy 'git remote add origin <url>'."
        )
        return None, "chưa có remote origin", fix

    url = out.strip()
    gh_path = shutil.which("gh")
    if not gh_path:
        fix = (
            f"Có remote ({url}) nhưng máy chưa cài GitHub CLI (gh) nên không tự kiểm "
            "tra được private/public. Tự vào trang repo trên GitHub, mục Settings, "
            "xem Visibility có đang là Private không."
        )
        return None, f"có remote ({url}), không kiểm tra được vì thiếu lệnh 'gh'", fix

    code2, out2, _err2 = run(["gh", "repo", "view", "--json", "isPrivate", "-q", ".isPrivate"])
    if code2 != 0:
        fix = (
            "Không xác định được vì 'gh' chưa đăng nhập hoặc repo chưa có trên GitHub. "
            "Chạy 'gh auth login', hoặc tự vào GitHub kiểm tra Visibility của repo."
        )
        return None, "không xác định được (gh chưa đăng nhập?)", fix

    is_private = out2.strip().lower() == "true"
    if is_private:
        return True, "private", ""
    fix = "Vào Settings của repo trên GitHub, đổi Visibility sang Private."
    return False, "đang là public", fix


CHECKS = [
    ("Python >= 3.11", check_python),
    ("Git đã cài", check_git_installed),
    ("Docker đã cài & daemon đang chạy", check_docker_installed_and_running),
    ("Docker Compose v2", check_docker_compose_v2),
    ("Đang đứng trong một git repo", check_in_git_repo),
    ("Remote origin là private", check_remote_private),
]


def print_check_table():
    print("=" * 70)
    print("KIỂM TRA ĐIỀU KIỆN MÁY")
    print("=" * 70)

    fixes = []
    for name, fn in CHECKS:
        status, detail, fix = fn()
        if status is True:
            mark = OK
        elif status is False:
            mark = FAIL
            fixes.append((name, fix))
        else:
            mark = SKIP
        print(f"{mark}  {name:<32} {detail}")

    if fixes:
        print()
        print("Hướng dẫn khắc phục (script KHÔNG tự cài đặt gì cả):")
        for name, fix in fixes:
            print(f"  - [{name}] {fix}")

    print()
    return fixes


# ---------------------------------------------------------------------------
# Tự tạo file/thư mục cấu hình còn thiếu
# ---------------------------------------------------------------------------

def ensure_gitignore(created, verbose=True):
    path = ROOT / ".gitignore"
    if path.exists():
        if verbose:
            print(f"{OK}  .gitignore đã có sẵn — không đụng vào.")
        return
    content = ".env\n__pycache__/\n*.pyc\n.venv/\ndata/\n*.log\n"
    path.write_text(content, encoding="utf-8")
    created.append((
        ".gitignore", path,
        "Danh sách file/thư mục Git sẽ bỏ qua, không đưa lên GitHub (quan trọng nhất: .env chứa API key).",
    ))


def ensure_env_example(created, verbose=True):
    path = ROOT / ".env.example"
    if path.exists():
        if verbose:
            print(f"{OK}  .env.example đã có sẵn — không đụng vào.")
        return
    content = "\n".join(f"{name}=" for name in ENV_VARS) + "\n"
    path.write_text(content, encoding="utf-8")
    created.append((
        ".env.example", path,
        "File mẫu liệt kê TÊN các biến môi trường cần có, giá trị để trống — dùng làm khuôn để tạo .env.",
    ))


def ensure_env(created, verbose=True):
    path = ROOT / ".env"
    if path.exists():
        if verbose:
            print(f"{OK}  .env đã có sẵn — không đụng vào.")
        return
    content = "\n".join(f"{name}=" for name in ENV_VARS) + "\n"
    path.write_text(content, encoding="utf-8")
    created.append((
        ".env", path,
        "API key của bạn sẽ được lưu tại <PATH>. File này đã được .gitignore loại trừ, không bao giờ lên GitHub.",
    ))


def ensure_dirs(created, verbose=True):
    for name in PACKAGE_DIRS + DATA_ONLY_DIRS:
        path = ROOT / name
        if path.exists():
            if verbose:
                print(f"{OK}  {name}/ đã có sẵn — không đụng vào.")
            continue
        path.mkdir(parents=True)
        if name in PACKAGE_DIRS:
            (path / "__init__.py").write_text("", encoding="utf-8")
        created.append((f"{name}/", path, DIR_DESCRIPTIONS[name]))


def print_created_table(created):
    print("=" * 70)
    print("FILE VỪA TẠO")
    print("=" * 70)
    if not created:
        print("(Không có gì để tạo — mọi file/thư mục cấu hình đã có sẵn từ trước.)")
        print()
        return

    for name, path, desc in created:
        if name == ".env":
            desc = desc.replace("<PATH>", str(path))
        print(f"- {name}")
        print(f"    Đường dẫn: {path}")
        print(f"    {desc}")
    print()


def main():
    print_check_table()

    created = []
    print("=" * 70)
    print("KIỂM TRA / TẠO FILE CẤU HÌNH CÒN THIẾU")
    print("=" * 70)
    ensure_gitignore(created)
    ensure_env_example(created)
    ensure_env(created)
    ensure_dirs(created)
    print()

    print_created_table(created)

    print("Bước tiếp theo: chạy `python setup.py` để nhập API key.")


if __name__ == "__main__":
    main()
