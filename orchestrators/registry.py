"""orchestrators/registry.py — nạp và validate catalog trong configs/.

Schema của tool và agent là HAI schema KHÁC NHAU (xem docs/SCHEMA.md §0):
  - agent thiếu `tier`                      -> lỗi
  - agent có `tier` không có trong tiers.yaml -> lỗi
  - tool có `tier`/`model`/`provider`/`system_prompt` -> lỗi

Ngoài ra registry sinh JSON schema cho LLM tool-calling từ chính catalog, để
orchestrator hội thoại chọn thành phần mà không cần khai báo trùng lặp.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT_DIR / "configs"

# Trường chỉ dành cho agent — xuất hiện trong file tool là lỗi.
AGENT_ONLY_FIELDS = ("tier", "system_prompt")
# Trường không file catalog nào được có: tên model chỉ nằm ở configs/tiers.yaml.
FORBIDDEN_EVERYWHERE = ("model", "provider")

FIELD_TYPES = ("string", "integer", "number", "boolean", "object", "array")
_JSON_TYPES = {t: t for t in FIELD_TYPES}


class RegistryError(ValueError):
    """Catalog không hợp lệ. Nạp catalog phải thất bại, không chạy tiếp."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputField(_Strict):
    name: str
    type: Literal[FIELD_TYPES]  # type: ignore[valid-type]
    description: str
    required: bool = True


class OutputField(_Strict):
    name: str
    type: Literal[FIELD_TYPES]  # type: ignore[valid-type]
    description: str


class ToolSpec(_Strict):
    """type: tool — code xác định, không gọi LLM, không tính token."""

    id: str
    type: Literal["tool"]
    name: str
    description: str
    entrypoint: str
    inputs: list[InputField]
    outputs: list[OutputField]


class AgentSpec(_Strict):
    """type: agent — có gọi LLM, bắt buộc khai báo tier, không được biết model."""

    id: str
    type: Literal["agent"]
    name: str
    description: str
    tier: str
    entrypoint: str
    inputs: list[InputField]
    outputs: list[OutputField]
    system_prompt: str | None = None


class Source(_Strict):
    """Nguồn dữ liệu khai báo cho input của một bước. Không biểu thức, không template."""

    from_: Literal["flow_input", "step"] = Field(alias="from")
    name: str | None = None
    step: str | None = None
    output: str | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> "Source":
        if self.from_ == "flow_input":
            if not self.name or self.step or self.output:
                raise ValueError(
                    "from: flow_input chỉ được đi kèm đúng trường `name`."
                )
        else:
            if not self.step or not self.output or self.name:
                raise ValueError(
                    "from: step phải đi kèm đúng hai trường `step` và `output`."
                )
        return self


class FlowStep(_Strict):
    id: str
    ref: str
    input: dict[str, Source]


class FlowSpec(_Strict):
    id: str
    type: Literal["flow"]
    kind: Literal["sequential", "python"]
    name: str
    description: str
    inputs: list[InputField]
    steps: list[FlowStep] | None = None
    entrypoint: str | None = None
    output: Source | None = None

    @model_validator(mode="after")
    def _check_kind(self) -> "FlowSpec":
        if self.kind == "sequential":
            if self.entrypoint is not None:
                raise ValueError("kind: sequential không được có `entrypoint`.")
            if not self.steps:
                raise ValueError("kind: sequential phải có `steps` không rỗng.")
            if self.output is None:
                raise ValueError("kind: sequential phải có `output`.")
            if self.output.from_ != "step":
                raise ValueError("`output` của flow phải là from: step.")
        else:
            if self.steps is not None:
                raise ValueError(
                    "kind: python không được có `steps` — logic nằm trong hàm "
                    "Python ở orchestrators/flows/."
                )
            if self.output is not None:
                raise ValueError("kind: python không được có `output`.")
            if not self.entrypoint:
                raise ValueError("kind: python phải có `entrypoint`.")
        return self


class Registry:
    """Catalog đã nạp và đã validate."""

    def __init__(
        self,
        tools: dict[str, ToolSpec],
        agents: dict[str, AgentSpec],
        flows: dict[str, FlowSpec],
    ) -> None:
        self.tools = tools
        self.agents = agents
        self.flows = flows

    def component(self, component_id: str) -> ToolSpec | AgentSpec:
        """Tra một tool hoặc agent theo id. Flow không phải component."""
        if component_id in self.tools:
            return self.tools[component_id]
        if component_id in self.agents:
            return self.agents[component_id]
        raise RegistryError(f"Không có tool/agent nào tên {component_id!r}.")

    def catalog(self) -> list[dict[str, Any]]:
        """Danh sách phẳng cho GET /v1/catalog: hiện rõ type, và tier nếu là agent."""
        items: list[dict[str, Any]] = []
        for spec in self.tools.values():
            items.append(
                {
                    "id": spec.id,
                    "type": "tool",
                    "name": spec.name,
                    "description": spec.description.strip(),
                    "tier": None,
                    "inputs": [f.name for f in spec.inputs],
                    "outputs": [f.name for f in spec.outputs],
                }
            )
        for spec in self.agents.values():
            items.append(
                {
                    "id": spec.id,
                    "type": "agent",
                    "name": spec.name,
                    "description": spec.description.strip(),
                    "tier": spec.tier,
                    "inputs": [f.name for f in spec.inputs],
                    "outputs": [f.name for f in spec.outputs],
                }
            )
        for spec in self.flows.values():
            items.append(
                {
                    "id": spec.id,
                    "type": "flow",
                    "kind": spec.kind,
                    "name": spec.name,
                    "description": spec.description.strip(),
                    "tier": None,
                    "inputs": [f.name for f in spec.inputs],
                    "outputs": [],
                }
            )
        return items

    def llm_tool_schemas(self) -> list[dict[str, Any]]:
        """JSON schema cho LLM tool-calling, sinh thẳng từ catalog."""
        schemas: list[dict[str, Any]] = []
        for spec in list(self.flows.values()) + list(self.agents.values()) + list(
            self.tools.values()
        ):
            props = {
                f.name: {"type": _JSON_TYPES[f.type], "description": f.description.strip()}
                for f in spec.inputs
            }
            required = [f.name for f in spec.inputs if f.required]
            schemas.append(
                {
                    "name": spec.id,
                    "kind": spec.type,
                    "description": spec.description.strip(),
                    "input_schema": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                }
            )
        return schemas


def _load_yaml_files(directory: Path) -> list[tuple[Path, dict]]:
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.yaml")):
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise RegistryError(f"{path}: nội dung phải là mapping.")
        out.append((path, data))
    return out


def _reject_forbidden_fields(path: Path, data: dict) -> None:
    """Báo lỗi rõ nghĩa hơn thông điệp mặc định của extra=forbid."""
    for key in FORBIDDEN_EVERYWHERE:
        if key in data:
            raise RegistryError(
                f"{path}: cấm trường {key!r} trong catalog. Tên model/provider "
                "chỉ được khai báo ở configs/tiers.yaml, thành phần chỉ khai `tier`."
            )
    if data.get("type") == "tool":
        for key in AGENT_ONLY_FIELDS:
            if key in data:
                raise RegistryError(
                    f"{path}: {key!r} là trường chỉ dành cho type: agent. "
                    "Tool không gọi LLM nên không có tier/system_prompt."
                )


def _parse(model, path: Path, data: dict):
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise RegistryError(f"{path}: {exc}") from exc


def load_registry(
    configs_dir: Path | None = None,
    tier_names: set[str] | None = None,
) -> Registry:
    """Nạp configs/tools, configs/agents, configs/flows và validate chéo."""
    base = Path(configs_dir) if configs_dir else CONFIGS_DIR
    if tier_names is None:
        from llm.client import load_tiers

        tiers_path = base / "tiers.yaml"
        if tiers_path == CONFIGS_DIR / "tiers.yaml":
            tier_names = set(load_tiers())
        else:
            with tiers_path.open(encoding="utf-8") as fh:
                tier_names = set((yaml.safe_load(fh) or {}).get("tiers") or {})

    tools: dict[str, ToolSpec] = {}
    agents: dict[str, AgentSpec] = {}
    flows: dict[str, FlowSpec] = {}
    seen: dict[str, Path] = {}

    def claim(component_id: str, path: Path) -> None:
        if component_id in seen:
            raise RegistryError(
                f"id {component_id!r} bị trùng giữa {seen[component_id]} và {path}."
            )
        seen[component_id] = path

    for path, data in _load_yaml_files(base / "tools"):
        _reject_forbidden_fields(path, data)
        spec = _parse(ToolSpec, path, data)
        claim(spec.id, path)
        tools[spec.id] = spec

    for path, data in _load_yaml_files(base / "agents"):
        _reject_forbidden_fields(path, data)
        if data.get("type") == "agent" and "tier" not in data:
            raise RegistryError(
                f"{path}: agent BẮT BUỘC khai báo `tier` (fast | standard | deep). "
                "Nếu thành phần này không gọi LLM thì nó là tool, không phải agent."
            )
        spec = _parse(AgentSpec, path, data)
        if spec.tier not in tier_names:
            raise RegistryError(
                f"{path}: tier {spec.tier!r} không có trong configs/tiers.yaml "
                f"(hợp lệ: {sorted(tier_names)})."
            )
        claim(spec.id, path)
        agents[spec.id] = spec

    for path, data in _load_yaml_files(base / "flows"):
        _reject_forbidden_fields(path, data)
        spec = _parse(FlowSpec, path, data)
        claim(spec.id, path)
        flows[spec.id] = spec

    registry = Registry(tools, agents, flows)
    for spec in flows.values():
        _validate_flow_wiring(spec, registry)
    return registry


def _validate_flow_wiring(flow: FlowSpec, registry: Registry) -> None:
    """Kiểm tra ref, thứ tự bước, và tên input/output khớp nhau."""
    if flow.kind == "python":
        return

    flow_inputs = {f.name for f in flow.inputs}
    outputs_of: dict[str, set[str]] = {}
    step_ids: list[str] = []

    for step in flow.steps or []:
        if step.id in outputs_of:
            raise RegistryError(f"flow {flow.id!r}: step id {step.id!r} bị trùng.")
        if step.ref in registry.flows:
            raise RegistryError(
                f"flow {flow.id!r}: step {step.id!r} ref tới flow {step.ref!r}; "
                "bước chỉ được ref tới tool hoặc agent."
            )
        try:
            component = registry.component(step.ref)
        except RegistryError as exc:
            raise RegistryError(f"flow {flow.id!r}: step {step.id!r} — {exc}") from exc

        accepted = {f.name for f in component.inputs}
        required = {f.name for f in component.inputs if f.required}
        given = set(step.input)
        if unknown := given - accepted:
            raise RegistryError(
                f"flow {flow.id!r}: step {step.id!r} truyền input lạ {sorted(unknown)} "
                f"cho {step.ref!r} (chấp nhận: {sorted(accepted)})."
            )
        if missing := required - given:
            raise RegistryError(
                f"flow {flow.id!r}: step {step.id!r} thiếu input bắt buộc "
                f"{sorted(missing)} cho {step.ref!r}."
            )

        for key, source in step.input.items():
            _validate_source(flow, f"step {step.id!r} input {key!r}", source,
                             flow_inputs, outputs_of, step_ids)

        outputs_of[step.id] = {f.name for f in component.outputs}
        step_ids.append(step.id)

    if flow.output is not None:
        _validate_source(flow, "output", flow.output, flow_inputs, outputs_of, step_ids)


def _validate_source(
    flow: FlowSpec,
    where: str,
    source: Source,
    flow_inputs: set[str],
    outputs_of: dict[str, set[str]],
    prior_steps: list[str],
) -> None:
    if source.from_ == "flow_input":
        if source.name not in flow_inputs:
            raise RegistryError(
                f"flow {flow.id!r}: {where} lấy flow_input {source.name!r} "
                f"không có trong inputs của flow ({sorted(flow_inputs)})."
            )
        return
    if source.step not in outputs_of:
        raise RegistryError(
            f"flow {flow.id!r}: {where} trỏ tới step {source.step!r} chưa chạy "
            f"trước đó (các step đã chạy: {prior_steps})."
        )
    if source.output not in outputs_of[source.step]:
        raise RegistryError(
            f"flow {flow.id!r}: {where} lấy output {source.output!r} không có "
            f"trong outputs của step {source.step!r} "
            f"({sorted(outputs_of[source.step])})."
        )
