"""harness/usage.py — cộng dồn usage của một run, tách riêng theo tier.

Ranh giới quan trọng:
  - Bước `type: agent` -> ghi token in/out vào tier tương ứng.
  - Bước `type: tool`  -> KHÔNG ghi token, chỉ tăng bộ đếm `tool_steps`.

Kết thúc run, append đúng MỘT dòng JSON vào runs/index.jsonl. Không dùng
database (đã chốt ở Giai đoạn 1).
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT_DIR / "runs" / "index.jsonl"

_file_lock = threading.Lock()


@dataclass
class TierUsage:
    """Usage cộng dồn của một tier trong một run."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _cost_usd(tier_name: str, usage: TierUsage) -> float | None:
    """Chi phí ước tính theo đơn giá trong configs/tiers.yaml. None nếu chưa có giá."""
    from llm.client import load_tiers  # import ở đây để tránh phụ thuộc vòng

    cfg = load_tiers().get(tier_name)
    if cfg is None:
        return None
    rate_in = cfg.cost_per_1m_input_usd
    rate_out = cfg.cost_per_1m_output_usd
    if rate_in is None or rate_out is None:
        return None  # chưa biết giá thì để null, không đoán
    return round(
        usage.input_tokens / 1_000_000 * float(rate_in)
        + usage.output_tokens / 1_000_000 * float(rate_out),
        6,
    )


@dataclass
class RunUsage:
    """Sổ cái usage của một run."""

    run_id: str
    flow_id: str
    started_at: float = field(default_factory=time.time)
    _monotonic_start: float = field(default_factory=time.monotonic, repr=False)
    by_tier: dict[str, TierUsage] = field(default_factory=dict)
    tool_steps: int = 0
    agent_steps: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_llm(
        self, tier: str, model: str, input_tokens: int, output_tokens: int
    ) -> None:
        """Ghi nhận một lời gọi LLM của bước agent."""
        with self._lock:
            entry = self.by_tier.setdefault(tier, TierUsage())
            entry.calls += 1
            entry.input_tokens += int(input_tokens)
            entry.output_tokens += int(output_tokens)
            entry.model = model

    def record_tool_step(self) -> None:
        """Bước tool: đếm riêng, không đụng tới token."""
        with self._lock:
            self.tool_steps += 1

    def record_agent_step(self) -> None:
        with self._lock:
            self.agent_steps += 1

    @property
    def total_tokens(self) -> int:
        return sum(u.total_tokens for u in self.by_tier.values())

    @property
    def duration_s(self) -> float:
        return time.monotonic() - self._monotonic_start

    def to_index_record(self, status: str, error: str | None = None) -> dict:
        """Dòng sẽ được append vào runs/index.jsonl."""
        tiers: dict[str, dict] = {}
        total_cost: float | None = 0.0
        for name, usage in sorted(self.by_tier.items()):
            cost = _cost_usd(name, usage)
            tiers[name] = {
                "model": usage.model,
                "calls": usage.calls,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "estimated_cost_usd": cost,
            }
            if cost is None:
                total_cost = None
            elif total_cost is not None:
                total_cost = round(total_cost + cost, 6)
        return {
            "run_id": self.run_id,
            "flow_id": self.flow_id,
            "status": status,
            "started_at": self.started_at,
            "duration_s": round(self.duration_s, 3),
            "tool_steps": self.tool_steps,
            "agent_steps": self.agent_steps,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": total_cost,
            "tiers": tiers,
            "error": error,
        }

    def write_index_line(
        self,
        status: str,
        error: str | None = None,
        *,
        index_path: Path | None = None,
    ) -> dict:
        """Append đúng MỘT dòng vào runs/index.jsonl. Trả về dict vừa ghi."""
        record = self.to_index_record(status, error)
        path = index_path or INDEX_PATH
        with _file_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
