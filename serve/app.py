"""serve/app.py — seam HTTP DUY NHẤT của nền tảng.

Web UI và Telegram sau này chỉ là adapter gọi vào contract dưới đây; chúng
KHÔNG được import orchestrators/ hay agents/.

Auth: header `Authorization: Bearer <API_BEARER_TOKEN>` cho mọi endpoint trừ
`/v1/health`.

Không chặn event loop: việc chọn thành phần (gọi LLM) chạy trong threadpool,
việc chạy flow đẩy sang BackgroundTasks.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from orchestrators import chat
from orchestrators.registry import load_registry
from serve.store import STORE

app = FastAPI(title="agent-platform", version="1")

_registry = None


def registry():
    """Nạp catalog một lần cho cả tiến trình."""
    global _registry
    if _registry is None:
        _registry = load_registry()
    return _registry


def require_bearer(authorization: str | None = Header(default=None)) -> None:
    """Xác thực bearer token. Đọc settings LAZY để /v1/health chạy không cần .env."""
    import settings

    # Kiểm tra header TRƯỚC: người gọi không có token thì nhận 401, không được
    # biết gì về tình trạng cấu hình của server.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Thiếu bearer token.")

    try:
        expected = settings.API_BEARER_TOKEN
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="API_BEARER_TOKEN chưa được cấu hình. Chạy `python setup.py`.",
        )
    if not secrets.compare_digest(authorization[len("Bearer "):], expected):
        raise HTTPException(status_code=401, detail="Bearer token không đúng.")


class MessageRequest(BaseModel):
    session_id: str
    text: str


@app.get("/v1/health")
def health() -> dict[str, str]:
    """Không cần auth — dùng để kiểm tra server sống."""
    return {"status": "ok"}


@app.get("/v1/catalog", dependencies=[Depends(require_bearer)])
def catalog() -> list[dict[str, Any]]:
    """Liệt kê tool + agent + flow, hiện rõ `type` và `tier` (tier=null với tool)."""
    return registry().catalog()


@app.post("/v1/messages", dependencies=[Depends(require_bearer)])
async def post_message(
    body: MessageRequest, background: BackgroundTasks
) -> dict[str, Any]:
    """Một lượt hội thoại. Lịch sử giữ theo session_id nên lượt sau nhớ lượt trước."""
    STORE.append_message(body.session_id, "user", body.text)
    history = STORE.history(body.session_id)

    reg = registry()
    # Bước chọn có gọi LLM (network I/O) -> chạy ngoài event loop.
    result = await run_in_threadpool(chat.handle_message, history, reg)
    STORE.append_message(body.session_id, "assistant", result.reply)

    if result.run_id:
        STORE.create_run(result.run_id, result.flow_id, result.target or "")
        background.add_task(_execute, result, reg)

    return {
        "session_id": body.session_id,
        "reply": result.reply,
        "run_id": result.run_id,
        "target": result.target,
        "target_kind": result.target_kind,
    }


def _execute(result: chat.ChatResult, reg) -> None:
    """Chạy nền: cập nhật status queued -> running -> done/error vào store."""
    run_id = result.run_id or ""

    def on_status(status: str) -> None:
        STORE.set_status(run_id, status)

    def on_finish(payload, error, usage) -> None:
        STORE.finish_run(run_id, payload, error, usage.to_index_record(
            "error" if error else "done", error
        ))

    chat.execute_run(result, reg, on_status=on_status, on_finish=on_finish)


@app.get("/v1/runs/{run_id}", dependencies=[Depends(require_bearer)])
def get_run(run_id: str) -> dict[str, Any]:
    """Trạng thái + kết quả + usage tách theo tier của một run."""
    run = STORE.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Không có run {run_id!r}.")
    return run
