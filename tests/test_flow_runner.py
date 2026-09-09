"""Flow 2 bước chạy đúng thứ tự, nối được output->input, KHÔNG gọi API thật."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.limits import LimitExceeded, RunLimits  # noqa: E402
from harness.run_context import RunContext  # noqa: E402
from harness.usage import RunUsage  # noqa: E402
from llm.client import Completion  # noqa: E402
from orchestrators import flow_runner  # noqa: E402
from orchestrators.registry import load_registry  # noqa: E402


class FakeLLM:
    """LLM giả. Ghi lại mọi lời gọi để test kiểm chứng, không chạm mạng."""

    def __init__(self, reply: str = "Ban tom tat gia.") -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def __call__(self, tier, messages, *, system=None, max_tokens=None):
        self.calls.append(
            {"tier": tier, "messages": [dict(m) for m in messages], "system": system}
        )
        return Completion(
            content=self.reply,
            input_tokens=11,
            output_tokens=7,
            tier=tier,
            model="model-gia-trong-test",
        )


@pytest.fixture()
def registry():
    return load_registry()


@pytest.fixture()
def ctx(tmp_path: Path) -> RunContext:
    return RunContext.create("run_flow_test", runs_dir=tmp_path)


def test_flow_hai_buoc_chay_dung_thu_tu_va_noi_du_lieu(registry, ctx) -> None:
    llm = FakeLLM()
    statuses: list[str] = []
    usage = RunUsage(run_id=ctx.run_id, flow_id="demo_two_step")

    result = flow_runner.run_flow(
        "demo_two_step",
        {"text": "xin chao cac ban"},
        registry=registry,
        ctx=ctx,
        usage=usage,
        complete=llm,
        on_status=statuses.append,
    )

    # Bước 1 là tool: viết hoa. Bước 2 là agent: nhận đúng chuỗi đã viết hoa.
    assert result["steps"]["upper"]["text"] == "XIN CHAO CAC BAN"
    assert len(llm.calls) == 1
    assert llm.calls[0]["messages"][0]["content"] == "XIN CHAO CAC BAN"
    assert result["output"] == "Ban tom tat gia."
    assert statuses == ["running", "done"]


def test_agent_nhan_tier_tu_config_khong_tu_chon(registry, ctx) -> None:
    """Tier truyền vào LLM lấy từ configs/agents/summarize_text.yaml."""
    llm = FakeLLM()
    flow_runner.run_flow(
        "demo_two_step", {"text": "abc"}, registry=registry, ctx=ctx, complete=llm
    )
    assert llm.calls[0]["tier"] == registry.agents["summarize_text"].tier == "fast"


def test_system_prompt_lay_tu_yaml(registry, ctx) -> None:
    llm = FakeLLM()
    flow_runner.run_flow(
        "demo_two_step", {"text": "abc"}, registry=registry, ctx=ctx, complete=llm
    )
    assert llm.calls[0]["system"] == registry.agents["summarize_text"].system_prompt


def test_thieu_input_bat_buoc_la_loi(registry, ctx) -> None:
    with pytest.raises(flow_runner.FlowError, match="thiếu input"):
        flow_runner.run_flow(
            "demo_two_step", {}, registry=registry, ctx=ctx, complete=FakeLLM()
        )


def test_status_chuyen_sang_error_khi_flow_hong(registry, ctx) -> None:
    def no_ranh(*_args, **_kwargs):
        raise RuntimeError("provider chet")

    statuses: list[str] = []
    with pytest.raises(RuntimeError):
        flow_runner.run_flow(
            "demo_two_step",
            {"text": "abc"},
            registry=registry,
            ctx=ctx,
            complete=no_ranh,
            on_status=statuses.append,
        )
    assert statuses == ["running", "error"]


def test_tran_so_loi_goi_llm_lam_run_dung_lai(registry, ctx) -> None:
    limits = RunLimits(max_llm_calls=0)
    with pytest.raises(LimitExceeded):
        flow_runner.run_flow(
            "demo_two_step",
            {"text": "abc"},
            registry=registry,
            ctx=ctx,
            limits=limits,
            complete=FakeLLM(),
        )


def test_agent_ghi_ket_qua_trong_workspace_cua_run(registry, ctx) -> None:
    flow_runner.run_flow(
        "demo_two_step", {"text": "abc"}, registry=registry, ctx=ctx, complete=FakeLLM()
    )
    assert (ctx.workspace_dir / "output" / "summary.txt").exists()
