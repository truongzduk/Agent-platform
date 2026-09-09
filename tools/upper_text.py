"""tools/upper_text.py — TOOL mẫu: thuần Python, không gọi LLM, không tốn token.

Khai báo: configs/tools/upper_text.yaml (type: tool, không có tier/model).

Chữ ký chuẩn của MỌI tool:
    run(inputs: dict, ctx: RunContext) -> dict
Tool không nhận hàm `complete`, nên về mặt cấu trúc nó không thể gọi LLM.
"""
from __future__ import annotations

from typing import Any

from harness.run_context import RunContext


def run(inputs: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Trả về đúng chuỗi đầu vào ở dạng chữ hoa. Kết quả xác định."""
    return {"text": str(inputs["text"]).upper()}
