"""harness/run_context.py — workspace riêng của từng run + chặn path traversal.

Mọi thao tác file của tool/agent PHẢI đi qua `RunContext.resolve_path()`.
Không có đường nào khác được phép chạm tới đĩa.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT_DIR = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT_DIR / "runs"

DEFAULT_TIMEOUT_S = 300.0


@dataclass
class RunContext:
    """Bối cảnh một lần chạy. workspace_dir là ranh giới cứng của run đó."""

    run_id: str
    workspace_dir: Path
    timeout_s: float = DEFAULT_TIMEOUT_S
    started_at: float = field(default_factory=time.monotonic)

    @classmethod
    def create(
        cls,
        run_id: str,
        *,
        runs_dir: Path | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> "RunContext":
        """Tạo runs/{run_id}/{input,output}/ rồi trả về context trỏ vào đó."""
        base = (runs_dir or RUNS_DIR) / run_id
        ctx = cls(run_id=run_id, workspace_dir=base.resolve(), timeout_s=timeout_s)
        ctx.workspace_dir.mkdir(parents=True, exist_ok=True)
        (ctx.workspace_dir / "input").mkdir(exist_ok=True)
        (ctx.workspace_dir / "output").mkdir(exist_ok=True)
        return ctx

    @property
    def output_dir(self) -> Path:
        return self.workspace_dir / "output"

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at

    def resolve_path(self, relative: str | Path) -> Path:
        """Ghép đường dẫn tương đối vào workspace, từ chối mọi thứ thoát ra ngoài.

        Từ chối (PermissionError):
          - đường dẫn tuyệt đối, kiểu POSIX lẫn kiểu Windows ("/etc", "C:\\...")
          - đường dẫn có ổ đĩa hoặc UNC ("\\\\server\\share")
          - bất kỳ thành phần ".." nào
          - symlink/junction trỏ ra ngoài workspace (kiểm tra sau khi resolve)
        """
        text = str(relative)
        if not text or not text.strip():
            raise PermissionError("Đường dẫn rỗng không hợp lệ.")

        posix = PurePosixPath(text)
        windows = PureWindowsPath(text)

        if posix.is_absolute() or windows.is_absolute() or windows.drive:
            raise PermissionError(
                f"Từ chối đường dẫn tuyệt đối {text!r}: agent chỉ được đọc/ghi "
                f"trong workspace của run {self.run_id}."
            )
        if ".." in posix.parts or ".." in windows.parts:
            raise PermissionError(
                f"Từ chối đường dẫn có '..' ({text!r}): không được thoát khỏi "
                f"workspace của run {self.run_id}."
            )

        base = self.workspace_dir.resolve()
        candidate = (base / Path(text)).resolve()
        # So sánh SAU khi resolve để bắt cả symlink/junction trỏ ra ngoài.
        if candidate != base and base not in candidate.parents:
            raise PermissionError(
                f"Từ chối {text!r}: đường dẫn sau khi resolve ({candidate}) nằm "
                f"ngoài workspace {base}."
            )
        return candidate

    def write_text(self, relative: str | Path, content: str) -> Path:
        """Ghi text vào workspace, tạo thư mục cha nếu cần."""
        path = self.resolve_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_text(self, relative: str | Path) -> str:
        return self.resolve_path(relative).read_text(encoding="utf-8")
