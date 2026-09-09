"""harness/limits.py — trần CỨNG cho mỗi run.

Vượt trần thì raise `LimitExceeded` và run dừng ngay. Không cảnh báo suông,
không tự cắt bớt rồi chạy tiếp.

Bước `type: tool` KHÔNG tính vào trần ở đây: tool không gọi LLM nên không tiêu
token. Tool chỉ được đếm số bước trong harness/usage.py.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# Trần mặc định cho một run. Đây là logic, không phải catalog, nên nằm trong
# code chứ không nằm trong configs/.
MAX_LLM_CALLS = 20
MAX_TOTAL_TOKENS = 200_000
MAX_DURATION_S = 300.0


class LimitExceeded(RuntimeError):
    """Run chạm trần cứng: số lời gọi LLM, tổng token, hoặc thời gian."""


@dataclass
class RunLimits:
    """Bộ đếm có khóa cho một run. Chỉ đếm hoạt động LLM."""

    max_llm_calls: int = MAX_LLM_CALLS
    max_total_tokens: int = MAX_TOTAL_TOKENS
    max_duration_s: float = MAX_DURATION_S

    llm_calls: int = 0
    total_tokens: int = 0
    started_at: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at

    def check_deadline(self) -> None:
        """Gọi TRƯỚC mỗi bước của flow, kể cả bước tool."""
        if self.elapsed_s > self.max_duration_s:
            raise LimitExceeded(
                f"Run vượt thời gian tối đa {self.max_duration_s}s "
                f"(đã chạy {self.elapsed_s:.1f}s)."
            )

    def check_before_llm_call(self) -> None:
        """Gọi TRƯỚC mỗi lời gọi LLM. Bước tool không gọi hàm này."""
        self.check_deadline()
        with self._lock:
            if self.llm_calls >= self.max_llm_calls:
                raise LimitExceeded(
                    f"Run vượt trần {self.max_llm_calls} lời gọi LLM."
                )
            if self.total_tokens >= self.max_total_tokens:
                raise LimitExceeded(
                    f"Run vượt trần {self.max_total_tokens} token "
                    f"(đã dùng {self.total_tokens})."
                )

    def record_llm_call(self, input_tokens: int, output_tokens: int) -> None:
        """Gọi SAU mỗi lời gọi LLM. Raise nếu lời gọi vừa rồi làm vượt trần."""
        with self._lock:
            self.llm_calls += 1
            self.total_tokens += int(input_tokens) + int(output_tokens)
            calls, tokens = self.llm_calls, self.total_tokens
        if tokens > self.max_total_tokens:
            raise LimitExceeded(
                f"Run vượt trần {self.max_total_tokens} token sau lời gọi thứ "
                f"{calls} (tổng {tokens})."
            )
