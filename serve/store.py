"""serve/store.py — state hội thoại và run, trong-process, có khóa.

Mọi truy cập đi qua một `threading.Lock` duy nhất. Không có dict/list cấp module
nào để trần: FastAPI xử lý nhiều request song song (nhiều tab, nhiều run, vừa
gửi tin nhắn vừa polling), nên state không khóa sẽ bị hai request ghi đè nhau.

State khóa theo `session_id` (hội thoại) và `run_id` (lần chạy). Không suy ra
state từ thứ tự request hay từ "run hiện tại".
"""
from __future__ import annotations

import threading
import time
from typing import Any


class Store:
    """Kho state trong bộ nhớ tiến trình. Mất khi tắt server — đúng ý đồ."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, list[dict[str, str]]] = {}
        self._runs: dict[str, dict[str, Any]] = {}

    # ----- hội thoại, khóa theo session_id -----

    def append_message(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            self._sessions.setdefault(session_id, []).append(
                {"role": role, "content": content}
            )

    def history(self, session_id: str) -> list[dict[str, str]]:
        """Trả về BẢN SAO để người gọi không sửa được state bên trong."""
        with self._lock:
            return [dict(m) for m in self._sessions.get(session_id, [])]

    def sessions(self) -> list[str]:
        with self._lock:
            return sorted(self._sessions)

    # ----- run, khóa theo run_id -----

    def create_run(self, run_id: str, flow_id: str | None, target: str) -> None:
        with self._lock:
            self._runs[run_id] = {
                "run_id": run_id,
                "flow_id": flow_id,
                "target": target,
                "status": "queued",
                "result": None,
                "error": None,
                "usage": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            }

    def set_status(self, run_id: str, status: str) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is not None:
                run["status"] = status
                run["updated_at"] = time.time()

    def finish_run(
        self,
        run_id: str,
        result: dict[str, Any] | None,
        error: str | None,
        usage: dict[str, Any] | None,
    ) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run["result"] = result
            run["error"] = error
            run["usage"] = usage
            run["status"] = "error" if error else "done"
            run["updated_at"] = time.time()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return dict(run) if run is not None else None


# Singleton cấp tiến trình. Biến này là module-level nhưng state bên trong nó
# được bảo vệ bằng lock — đây chính là điều kiện đã chốt.
STORE = Store()
