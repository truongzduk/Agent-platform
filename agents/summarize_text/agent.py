"""agents/summarize_text/agent.py — AGENT mẫu: có gọi LLM.

Khai báo: configs/agents/summarize_text.yaml (type: agent, tier: fast).

Chữ ký chuẩn của MỌI agent:
    run(inputs: dict, ctx: RunContext, spec: AgentSpec, complete) -> dict

Ba ràng buộc mà file này minh hoạ, áp dụng cho mọi agent về sau:
  1. KHÔNG import SDK provider, KHÔNG biết tên model. `complete` do flow_runner
     truyền vào đã kẹp sẵn tier lấy từ YAML, nên đổi tier = sửa YAML, không sửa
     dòng code nào ở đây.
  2. system prompt lấy từ `spec.system_prompt` (YAML), không hardcode.
  3. Mọi thao tác đĩa đi qua ctx.resolve_path()/ctx.write_text(), không dùng
     open() với đường dẫn tự ghép.
"""
from __future__ import annotations

from typing import Any, Callable

from harness.run_context import RunContext


def run(
    inputs: dict[str, Any],
    ctx: RunContext,
    spec: Any,
    complete: Callable[..., Any],
) -> dict[str, Any]:
    """Tóm tắt `text` thành một câu."""
    text = str(inputs["text"])

    completion = complete(
        [{"role": "user", "content": text}],
        system=spec.system_prompt,
    )
    summary = completion.content.strip()

    # Ghi lại kết quả trong workspace của run — chỉ qua ctx, không tự ghép path.
    ctx.write_text("output/summary.txt", summary)

    return {"summary": summary}
