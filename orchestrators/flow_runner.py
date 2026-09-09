"""orchestrators/flow_runner.py — chạy flow một cách XÁC ĐỊNH.

Sau khi orchestrator hội thoại đã CHỌN được flow, LLM không còn ứng biến từng
bước nữa: các bước chạy đúng theo khai báo trong YAML (kind: sequential) hoặc
đúng theo hàm Python đã đăng ký (kind: python).

Phân nhánh thực thi dựa trên `type` của thành phần được `ref` trỏ tới:
  - type: tool  -> gọi thẳng hàm Python, KHÔNG đụng tới LLM, KHÔNG tính token.
  - type: agent -> gọi hàm agent, và truyền cho nó một hàm `complete` đã bị
    KẸP SẴN tier lấy từ config. Agent không tự chọn tier, không thấy tên model,
    và không thể lách qua bộ đếm limits/usage vì đó là đường duy nhất nó có.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Protocol

from harness.limits import RunLimits
from harness.run_context import RunContext
from harness.usage import RunUsage
from orchestrators.registry import AgentSpec, FlowSpec, Registry, Source, ToolSpec

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"


class FlowError(RuntimeError):
    """Flow chạy lỗi."""


class StatusSink(Protocol):
    def __call__(self, status: str) -> None: ...


def _import_entrypoint(entrypoint: str) -> Callable[..., Any]:
    """"module:function" -> callable."""
    if ":" not in entrypoint:
        raise FlowError(f"entrypoint {entrypoint!r} phải có dạng 'module:function'.")
    module_name, func_name = entrypoint.split(":", 1)
    module = importlib.import_module(module_name)
    try:
        return getattr(module, func_name)
    except AttributeError as exc:
        raise FlowError(f"{entrypoint!r}: module không có hàm {func_name!r}.") from exc


class FlowDeps:
    """Những gì một flow (YAML hay Python) được phép dùng để chạy một bước.

    Flow Python nhận đúng object này; nhờ vậy vòng lặp/fan-out/retry viết bằng
    Python vẫn đi qua cùng một đường đo đếm limits + usage như flow YAML.
    """

    def __init__(
        self,
        registry: Registry,
        ctx: RunContext,
        limits: RunLimits,
        usage: RunUsage,
        complete: Callable[..., Any],
    ) -> None:
        self.registry = registry
        self.ctx = ctx
        self.limits = limits
        self.usage = usage
        self._complete = complete

    def run_component(self, component_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Chạy một tool hoặc agent theo id, trả về dict output."""
        spec = self.registry.component(component_id)
        self.limits.check_deadline()
        if isinstance(spec, ToolSpec):
            return self._run_tool(spec, inputs)
        return self._run_agent(spec, inputs)

    def _run_tool(self, spec: ToolSpec, inputs: dict[str, Any]) -> dict[str, Any]:
        func = _import_entrypoint(spec.entrypoint)
        result = func(inputs, self.ctx)
        self.usage.record_tool_step()  # chỉ đếm bước, không có token
        return _check_outputs(spec, result)

    def _run_agent(self, spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
        func = _import_entrypoint(spec.entrypoint)
        metered = self._metered_complete(spec.tier)
        result = func(inputs, self.ctx, spec, metered)
        self.usage.record_agent_step()
        return _check_outputs(spec, result)

    def _metered_complete(self, tier: str) -> Callable[..., Any]:
        """Kẹp tier vào complete(), và bọc limits + usage quanh mỗi lời gọi."""

        def call(messages, *, system=None, max_tokens=None):
            self.limits.check_before_llm_call()
            completion = self._complete(
                tier, messages, system=system, max_tokens=max_tokens
            )
            self.limits.record_llm_call(
                completion.input_tokens, completion.output_tokens
            )
            self.usage.record_llm(
                completion.tier,
                completion.model,
                completion.input_tokens,
                completion.output_tokens,
            )
            return completion

        return call


def _check_outputs(spec: ToolSpec | AgentSpec, result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise FlowError(
            f"{spec.id!r} phải trả về dict, nhận được {type(result).__name__}."
        )
    missing = {f.name for f in spec.outputs} - set(result)
    if missing:
        raise FlowError(f"{spec.id!r} thiếu output {sorted(missing)} theo khai báo.")
    return result


def _resolve_source(
    source: Source,
    flow_inputs: dict[str, Any],
    step_outputs: dict[str, dict[str, Any]],
) -> Any:
    if source.from_ == "flow_input":
        return flow_inputs[source.name]
    return step_outputs[source.step][source.output]


def run_flow(
    flow_id: str,
    inputs: dict[str, Any],
    *,
    registry: Registry,
    ctx: RunContext,
    limits: RunLimits | None = None,
    usage: RunUsage | None = None,
    complete: Callable[..., Any] | None = None,
    on_status: StatusSink | None = None,
) -> dict[str, Any]:
    """Chạy một flow. Trả về {"output": ..., "steps": {...}}.

    complete: hàm gọi LLM. Mặc định là llm.client.complete; test truyền hàm giả
    vào đây để không chạm mạng.
    """
    flow = registry.flows.get(flow_id)
    if flow is None:
        raise FlowError(f"Không có flow nào tên {flow_id!r}.")

    limits = limits or RunLimits()
    usage = usage or RunUsage(run_id=ctx.run_id, flow_id=flow_id)
    if complete is None:
        import llm.client  # import ở đây để test không cần chạm tới lớp LLM

        complete = llm.client.complete

    missing = {f.name for f in flow.inputs if f.required} - set(inputs)
    if missing:
        raise FlowError(f"flow {flow_id!r} thiếu input bắt buộc {sorted(missing)}.")

    deps = FlowDeps(registry, ctx, limits, usage, complete)
    _emit(on_status, STATUS_RUNNING)
    try:
        if flow.kind == "python":
            result = _run_python_flow(flow, inputs, deps)
        else:
            result = _run_sequential_flow(flow, inputs, deps)
    except Exception:
        _emit(on_status, STATUS_ERROR)
        raise
    _emit(on_status, STATUS_DONE)
    return result


def _run_sequential_flow(
    flow: FlowSpec, inputs: dict[str, Any], deps: FlowDeps
) -> dict[str, Any]:
    """Chạy các bước đúng thứ tự khai báo, nối output bước trước vào bước sau."""
    step_outputs: dict[str, dict[str, Any]] = {}
    for step in flow.steps or []:
        deps.limits.check_deadline()
        step_inputs = {
            key: _resolve_source(source, inputs, step_outputs)
            for key, source in step.input.items()
        }
        step_outputs[step.id] = deps.run_component(step.ref, step_inputs)
    output = _resolve_source(flow.output, inputs, step_outputs)  # type: ignore[arg-type]
    return {"output": output, "steps": step_outputs}


def _run_python_flow(
    flow: FlowSpec, inputs: dict[str, Any], deps: FlowDeps
) -> dict[str, Any]:
    """Flow có vòng lặp/rẽ nhánh/retry/fan-out: logic nằm trong hàm Python."""
    func = _import_entrypoint(flow.entrypoint or "")
    output = func(inputs, deps.ctx, deps)
    return {"output": output, "steps": {}}


def _emit(sink: StatusSink | None, status: str) -> None:
    if sink is not None:
        sink(status)
