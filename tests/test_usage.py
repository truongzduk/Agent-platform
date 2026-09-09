"""Sau 1 run gồm 1 tool + 1 agent: token chỉ tính cho agent, tool đếm riêng."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.run_context import RunContext  # noqa: E402
from harness.usage import RunUsage  # noqa: E402
from llm.client import Completion  # noqa: E402
from orchestrators import flow_runner  # noqa: E402
from orchestrators.registry import load_registry  # noqa: E402

INPUT_TOKENS = 11
OUTPUT_TOKENS = 7


def fake_complete(tier, messages, *, system=None, max_tokens=None):
    return Completion(
        content="Ban tom tat gia.",
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
        tier=tier,
        model="model-gia-trong-test",
    )


@pytest.fixture()
def run_result(tmp_path: Path):
    registry = load_registry()
    ctx = RunContext.create("run_usage_test", runs_dir=tmp_path)
    usage = RunUsage(run_id=ctx.run_id, flow_id="demo_two_step")
    flow_runner.run_flow(
        "demo_two_step",
        {"text": "xin chao"},
        registry=registry,
        ctx=ctx,
        usage=usage,
        complete=fake_complete,
    )
    return usage, tmp_path


def test_chi_agent_duoc_tinh_token(run_result) -> None:
    usage, _ = run_result
    # Flow có đúng 2 bước: 1 tool + 1 agent. Chỉ tier của agent xuất hiện.
    assert set(usage.by_tier) == {"fast"}
    assert usage.by_tier["fast"].calls == 1
    assert usage.by_tier["fast"].input_tokens == INPUT_TOKENS
    assert usage.by_tier["fast"].output_tokens == OUTPUT_TOKENS
    assert usage.total_tokens == INPUT_TOKENS + OUTPUT_TOKENS


def test_buoc_tool_duoc_dem_rieng_khong_sinh_token(run_result) -> None:
    usage, _ = run_result
    assert usage.tool_steps == 1
    assert usage.agent_steps == 1
    # Không có mục usage nào phát sinh từ bước tool.
    assert sum(u.calls for u in usage.by_tier.values()) == usage.agent_steps


def test_ghi_dung_mot_dong_vao_index_jsonl(run_result, tmp_path: Path) -> None:
    usage, _ = run_result
    index = tmp_path / "index.jsonl"
    usage.write_index_line("done", index_path=index)

    lines = index.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["run_id"] == "run_usage_test"
    assert record["flow_id"] == "demo_two_step"
    assert record["status"] == "done"
    assert record["tool_steps"] == 1
    assert record["total_tokens"] == INPUT_TOKENS + OUTPUT_TOKENS
    assert record["tiers"]["fast"]["input_tokens"] == INPUT_TOKENS
    assert record["tiers"]["fast"]["output_tokens"] == OUTPUT_TOKENS
    assert "duration_s" in record


def test_chi_phi_la_null_khi_tiers_yaml_chua_dien_don_gia(run_result) -> None:
    """Chưa biết giá thì để null, không đoán."""
    usage, _ = run_result
    from llm.client import load_tiers

    cfg = load_tiers()["fast"]
    record = usage.to_index_record("done")
    if cfg.cost_per_1m_input_usd is None or cfg.cost_per_1m_output_usd is None:
        assert record["tiers"]["fast"]["estimated_cost_usd"] is None
        assert record["estimated_cost_usd"] is None
    else:
        assert record["tiers"]["fast"]["estimated_cost_usd"] >= 0


def test_run_loi_van_ghi_duoc_dong_index(tmp_path: Path) -> None:
    usage = RunUsage(run_id="run_loi", flow_id="demo_two_step")
    usage.record_tool_step()
    index = tmp_path / "index.jsonl"
    usage.write_index_line("error", "RuntimeError: provider chet", index_path=index)

    record = json.loads(index.read_text(encoding="utf-8").strip())
    assert record["status"] == "error"
    assert record["tool_steps"] == 1
    assert record["total_tokens"] == 0
    assert record["error"] == "RuntimeError: provider chet"
