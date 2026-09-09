"""Schema của tool và agent phải KHÁC nhau, và validate phải chặn đúng chỗ."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrators.registry import RegistryError, load_registry  # noqa: E402

TIERS = {"fast": {}, "standard": {}, "deep": {}}

TOOL_OK = """
id: upper_text
type: tool
name: Viet hoa
description: Viet hoa van ban.
entrypoint: tools.upper_text:run
inputs:
  - name: text
    type: string
    required: true
    description: Van ban vao.
outputs:
  - name: text
    type: string
    description: Van ban hoa.
"""

AGENT_OK = """
id: summarize_text
type: agent
name: Tom tat
description: Tom tat mot cau.
tier: fast
entrypoint: agents.summarize_text.agent:run
inputs:
  - name: text
    type: string
    required: true
    description: Van ban can tom tat.
outputs:
  - name: summary
    type: string
    description: Ban tom tat.
"""


def _write(base: Path, subdir: str, name: str, body: str) -> None:
    directory = base / subdir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(textwrap.dedent(body), encoding="utf-8")


@pytest.fixture()
def configs(tmp_path: Path) -> Path:
    base = tmp_path / "configs"
    base.mkdir()
    (base / "tiers.yaml").write_text(
        yaml.safe_dump({"tiers": TIERS}), encoding="utf-8"
    )
    _write(base, "tools", "upper_text.yaml", TOOL_OK)
    _write(base, "agents", "summarize_text.yaml", AGENT_OK)
    return base


def test_catalog_hop_le_nap_duoc(configs: Path) -> None:
    reg = load_registry(configs, tier_names=set(TIERS))
    assert reg.tools["upper_text"].type == "tool"
    assert reg.agents["summarize_text"].tier == "fast"
    assert not hasattr(reg.tools["upper_text"], "tier")


def test_agent_thieu_tier_la_loi(configs: Path) -> None:
    _write(configs, "agents", "summarize_text.yaml",
           AGENT_OK.replace("tier: fast\n", ""))
    with pytest.raises(RegistryError, match="tier"):
        load_registry(configs, tier_names=set(TIERS))


def test_agent_tier_la_khong_co_trong_tiers_yaml(configs: Path) -> None:
    _write(configs, "agents", "summarize_text.yaml",
           AGENT_OK.replace("tier: fast", "tier: turbo"))
    with pytest.raises(RegistryError, match="turbo"):
        load_registry(configs, tier_names=set(TIERS))


def test_tool_co_tier_la_loi(configs: Path) -> None:
    _write(configs, "tools", "upper_text.yaml",
           TOOL_OK.replace("type: tool", "type: tool\ntier: fast"))
    with pytest.raises(RegistryError, match="agent"):
        load_registry(configs, tier_names=set(TIERS))


def test_tool_co_model_la_loi(configs: Path) -> None:
    _write(configs, "tools", "upper_text.yaml",
           TOOL_OK.replace("type: tool", "type: tool\nmodel: bat-ky-ten-nao"))
    with pytest.raises(RegistryError, match="tiers.yaml"):
        load_registry(configs, tier_names=set(TIERS))


def test_agent_co_model_la_loi(configs: Path) -> None:
    _write(configs, "agents", "summarize_text.yaml",
           AGENT_OK.replace("tier: fast", "tier: fast\nmodel: bat-ky-ten-nao"))
    with pytest.raises(RegistryError, match="tiers.yaml"):
        load_registry(configs, tier_names=set(TIERS))


def test_tool_co_system_prompt_la_loi(configs: Path) -> None:
    _write(configs, "tools", "upper_text.yaml",
           TOOL_OK.replace("type: tool", "type: tool\nsystem_prompt: xin chao"))
    with pytest.raises(RegistryError, match="agent"):
        load_registry(configs, tier_names=set(TIERS))


def test_id_trung_nhau_la_loi(configs: Path) -> None:
    _write(configs, "agents", "trung.yaml", AGENT_OK.replace(
        "id: summarize_text", "id: upper_text"))
    with pytest.raises(RegistryError, match="trùng"):
        load_registry(configs, tier_names=set(TIERS))


FLOW_OK = """
id: demo
type: flow
kind: sequential
name: Demo
description: Demo hai buoc.
inputs:
  - name: text
    type: string
    required: true
    description: Van ban vao.
steps:
  - id: upper
    ref: upper_text
    input:
      text:
        from: flow_input
        name: text
  - id: sum
    ref: summarize_text
    input:
      text:
        from: step
        step: upper
        output: text
output:
  from: step
  step: sum
  output: summary
"""


def test_flow_hop_le(configs: Path) -> None:
    _write(configs, "flows", "demo.yaml", FLOW_OK)
    reg = load_registry(configs, tier_names=set(TIERS))
    assert [s.id for s in reg.flows["demo"].steps] == ["upper", "sum"]


def test_flow_ref_khong_ton_tai_la_loi(configs: Path) -> None:
    _write(configs, "flows", "demo.yaml", FLOW_OK.replace("ref: upper_text", "ref: khong_co"))
    with pytest.raises(RegistryError, match="khong_co"):
        load_registry(configs, tier_names=set(TIERS))


def test_flow_tro_toi_buoc_chua_chay_la_loi(configs: Path) -> None:
    _write(configs, "flows", "demo.yaml", FLOW_OK.replace("step: upper", "step: sum"))
    with pytest.raises(RegistryError, match="chưa chạy"):
        load_registry(configs, tier_names=set(TIERS))


def test_flow_sequential_co_entrypoint_la_loi(configs: Path) -> None:
    _write(configs, "flows", "demo.yaml",
           FLOW_OK.replace("kind: sequential", "kind: sequential\nentrypoint: a:b"))
    with pytest.raises(RegistryError, match="entrypoint"):
        load_registry(configs, tier_names=set(TIERS))


def test_catalog_that_trong_repo_nap_duoc() -> None:
    """configs/ thật phải luôn hợp lệ: tool khong co tier, agent co tier."""
    reg = load_registry()
    items = {item["id"]: item for item in reg.catalog()}
    assert items["upper_text"]["type"] == "tool"
    assert items["upper_text"]["tier"] is None
    assert items["summarize_text"]["type"] == "agent"
    assert items["summarize_text"]["tier"] == "fast"
    assert items["demo_two_step"]["type"] == "flow"
