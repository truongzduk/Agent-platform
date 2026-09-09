"""orchestrators/chat.py — orchestrator hội thoại.

Vai trò duy nhất: đọc lịch sử hội thoại và CHỌN một thành phần trong catalog
(flow / agent / tool) kèm input cho nó. Chọn xong thì bàn giao cho flow_runner
và flow chạy XÁC ĐỊNH theo khai báo — LLM không ứng biến từng bước.

Ghi chú thiết kế (khác native tool-calling của từng SDK):
Catalog được nạp vào system prompt dưới dạng JSON schema do
`Registry.llm_tool_schemas()` sinh ra, và model trả lời bằng đúng một JSON
object. Cấu trúc y hệt tool-calling (tên thành phần + input schema + đối số),
nhưng đi qua `llm/client.complete()` nên chạy được trên cả ba provider mà
llm/client không phải phơi ra API riêng của từng SDK.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from harness.limits import RunLimits
from harness.run_context import RunContext
from harness.usage import RunUsage
from orchestrators import flow_runner
from orchestrators.registry import Registry

SELECTION_TIER = "standard"

SYSTEM_PROMPT = """Bạn là bộ điều phối của một nền tảng agent.

Bạn KHÔNG tự làm việc của người dùng. Việc duy nhất của bạn là chọn đúng MỘT
thành phần trong catalog dưới đây để chạy, hoặc trả lời trực tiếp nếu không
thành phần nào phù hợp.

Trả lời bằng ĐÚNG một JSON object, không kèm chữ nào khác, theo một trong hai
dạng:

{"action": "run", "target": "<id trong catalog>", "inputs": {...}}
{"action": "reply", "message": "<câu trả lời cho người dùng>"}

Quy tắc:
- "target" phải là một "name" có trong catalog. Không bịa id.
- "inputs" phải khớp input_schema của thành phần đó, đủ mọi trường required.
- Ưu tiên flow nếu có flow bao trọn được yêu cầu; nếu không thì chọn agent hoặc
  tool đơn lẻ.
- Nếu không thành phần nào phù hợp, dùng action "reply".

CATALOG:
"""


@dataclass
class ChatResult:
    """Quyết định của orchestrator cho một lượt hội thoại."""

    reply: str
    run_id: str | None = None
    flow_id: str | None = None
    target: str | None = None
    target_kind: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)


def _build_system_prompt(registry: Registry) -> str:
    catalog = json.dumps(registry.llm_tool_schemas(), ensure_ascii=False, indent=1)
    return SYSTEM_PROMPT + catalog


def _parse_selection(raw: str) -> dict[str, Any]:
    """Bóc JSON object từ câu trả lời của model."""
    text = raw.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("Model không trả về JSON.")
    data = json.loads(match.group(0))
    if not isinstance(data, dict) or "action" not in data:
        raise ValueError("JSON trả về thiếu trường 'action'.")
    return data


def handle_message(
    history: list[dict[str, str]],
    registry: Registry,
    *,
    complete: Callable[..., Any] | None = None,
) -> ChatResult:
    """Nhận lịch sử hội thoại (đã gồm tin nhắn mới nhất), trả về quyết định.

    Không tự chạy flow: việc chạy do serve/ đẩy sang BackgroundTasks rồi gọi
    `execute_run()`, để endpoint không chặn event loop.
    """
    if complete is None:
        import llm.client

        complete = llm.client.complete

    try:
        completion = complete(
            SELECTION_TIER,
            [dict(m) for m in history],
            system=_build_system_prompt(registry),
        )
        selection = _parse_selection(completion.content)
    except Exception as exc:  # lớp LLM chưa cấu hình, hoặc trả về rác
        return ChatResult(reply=_fallback_reply(registry, exc))

    if selection.get("action") == "run":
        target = str(selection.get("target") or "")
        inputs = selection.get("inputs") or {}
        if target in registry.flows:
            kind = "flow"
        elif target in registry.agents or target in registry.tools:
            kind = "agent" if target in registry.agents else "tool"
        else:
            return ChatResult(
                reply=f"Không có thành phần nào tên {target!r} trong catalog."
            )
        return ChatResult(
            reply=f"Đang chạy {kind} {target!r}.",
            run_id=uuid.uuid4().hex,
            flow_id=target if kind == "flow" else None,
            target=target,
            target_kind=kind,
            inputs=dict(inputs),
        )

    return ChatResult(reply=str(selection.get("message") or ""))


def _fallback_reply(registry: Registry, exc: Exception) -> str:
    """Khi lớp LLM chưa dùng được, vẫn trả lời có ích thay vì ném 500."""
    ids = ", ".join(item["id"] for item in registry.catalog())
    return (
        "Chưa chọn được thành phần vì lớp LLM chưa dùng được: "
        f"{type(exc).__name__}: {exc}. "
        f"Catalog hiện có: {ids}. "
        "Kiểm tra provider/model trong configs/tiers.yaml."
    )


def execute_run(
    result: ChatResult,
    registry: Registry,
    *,
    on_status: Callable[[str], None] | None = None,
    on_finish: Callable[[dict[str, Any] | None, str | None, RunUsage], None] | None = None,
    complete: Callable[..., Any] | None = None,
    runs_dir=None,
) -> None:
    """Chạy thành phần đã chọn. Gọi từ BackgroundTasks của serve/app.py."""
    assert result.run_id and result.target
    ctx = RunContext.create(result.run_id, runs_dir=runs_dir)
    limits = RunLimits()
    usage = RunUsage(run_id=result.run_id, flow_id=result.target)

    try:
        if result.target_kind == "flow":
            payload = flow_runner.run_flow(
                result.target,
                result.inputs,
                registry=registry,
                ctx=ctx,
                limits=limits,
                usage=usage,
                complete=complete,
                on_status=on_status,
            )
        else:
            # Chạy một tool/agent đơn lẻ: cùng đường đo đếm với flow.
            if complete is None:
                import llm.client

                complete = llm.client.complete
            deps = flow_runner.FlowDeps(registry, ctx, limits, usage, complete)
            if on_status:
                on_status(flow_runner.STATUS_RUNNING)
            outputs = deps.run_component(result.target, result.inputs)
            payload = {"output": outputs, "steps": {result.target: outputs}}
            if on_status:
                on_status(flow_runner.STATUS_DONE)
    except Exception as exc:
        usage.write_index_line("error", f"{type(exc).__name__}: {exc}")
        if on_finish:
            on_finish(None, f"{type(exc).__name__}: {exc}", usage)
        return

    usage.write_index_line("done")
    if on_finish:
        on_finish(payload, None, usage)
