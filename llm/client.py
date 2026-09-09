"""llm/client.py — lớp DUY NHẤT trong repo được phép import SDK của provider.

Hai bất biến của file này:

1. Hàm `complete()` nhận **tier**, không nhận tên model. Ánh xạ
   tier -> provider + model đọc từ configs/tiers.yaml, là nơi duy nhất chứa
   tên model. Không có tham số nào cho phép người gọi chỉ định model.
2. Mọi `import` SDK nằm BÊN TRONG nhánh provider tương ứng (lazy). Nhờ vậy
   máy chưa cài `anthropic`/`openai` vẫn import được module này, chạy được
   test và khởi động được serve/; chỉ khi thật sự gọi tới provider đó mới lỗi.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

import settings

ROOT_DIR = Path(__file__).resolve().parents[1]
TIERS_PATH = ROOT_DIR / "configs" / "tiers.yaml"
PROVIDERS_PATH = ROOT_DIR / "configs" / "providers.yaml"


class LLMError(RuntimeError):
    """Lỗi gốc của lớp LLM."""


class UnknownTierError(LLMError):
    """Tier không có trong configs/tiers.yaml."""


class TierNotConfiguredError(LLMError):
    """Tier tồn tại nhưng provider/model còn để trống — owner chưa điền."""


class ProviderUnavailableError(LLMError):
    """Provider bị tắt trong configs, hoặc không có API key trên máy này."""


@dataclass(frozen=True)
class TierConfig:
    name: str
    provider: str
    model: str
    max_tokens: int
    cost_per_1m_input_usd: float | None
    cost_per_1m_output_usd: float | None

    @property
    def configured(self) -> bool:
        return bool(self.provider) and bool(self.model)


@dataclass(frozen=True)
class Completion:
    """Kết quả một lời gọi LLM: nội dung + usage để harness cộng dồn."""

    content: str
    input_tokens: int
    output_tokens: int
    tier: str
    model: str


_lock = threading.Lock()
_tiers_cache: dict[str, TierConfig] | None = None
_providers_cache: dict[str, dict[str, Any]] | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise LLMError(f"Không tìm thấy file cấu hình: {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_tiers(*, force: bool = False) -> dict[str, TierConfig]:
    """Nạp configs/tiers.yaml (có cache). force=True để nạp lại sau khi sửa file."""
    global _tiers_cache
    with _lock:
        if _tiers_cache is not None and not force:
            return _tiers_cache
        raw = _read_yaml(TIERS_PATH).get("tiers") or {}
        tiers: dict[str, TierConfig] = {}
        for name, spec in raw.items():
            tiers[name] = TierConfig(
                name=name,
                provider=(spec.get("provider") or "").strip(),
                model=(spec.get("model") or "").strip(),
                max_tokens=int(spec.get("max_tokens") or 0),
                cost_per_1m_input_usd=spec.get("cost_per_1m_input_usd"),
                cost_per_1m_output_usd=spec.get("cost_per_1m_output_usd"),
            )
        _tiers_cache = tiers
        return tiers


def load_providers(*, force: bool = False) -> dict[str, dict[str, Any]]:
    """Nạp configs/providers.yaml (có cache), key là provider id."""
    global _providers_cache
    with _lock:
        if _providers_cache is not None and not force:
            return _providers_cache
        raw = _read_yaml(PROVIDERS_PATH).get("providers") or []
        _providers_cache = {p["id"]: p for p in raw}
        return _providers_cache


def tier_names() -> set[str]:
    """Tên các tier hợp lệ — registry dùng để validate trường `tier` của agent."""
    return set(load_tiers())


def resolve_tier(tier: str) -> TierConfig:
    """tier -> TierConfig. Raise nếu tier lạ hoặc owner chưa điền provider/model."""
    tiers = load_tiers()
    if tier not in tiers:
        raise UnknownTierError(
            f"Tier {tier!r} không có trong {TIERS_PATH}. "
            f"Tier hợp lệ: {sorted(tiers)}."
        )
    cfg = tiers[tier]
    if not cfg.configured:
        raise TierNotConfiguredError(
            f"Tier {tier!r} chưa được cấu hình: provider={cfg.provider!r}, "
            f"model={cfg.model!r}. Owner cần điền hai trường này trong {TIERS_PATH}. "
            "Hệ thống không tự đoán model."
        )
    return cfg


def _api_key(provider: str) -> str:
    """Lấy API key của provider, sau khi kiểm tra provider được phép dùng."""
    providers = load_providers()
    declared = providers.get(provider)
    if declared is None:
        raise ProviderUnavailableError(
            f"Provider {provider!r} không có trong {PROVIDERS_PATH}."
        )
    if not declared.get("enabled", False):
        raise ProviderUnavailableError(
            f"Provider {provider!r} đang enabled: false trong {PROVIDERS_PATH}."
        )

    available = settings.AVAILABLE_PROVIDERS
    if provider not in available:
        raise ProviderUnavailableError(
            f"Provider {provider!r} chưa có API key trên máy này "
            f"(settings.AVAILABLE_PROVIDERS = {available}). "
            "Chạy `python setup.py` để nạp key. Hệ thống không tự đổi sang "
            "provider khác."
        )

    key = {
        "anthropic": lambda: settings.ANTHROPIC_API_KEY,
        "gemini": lambda: settings.GEMINI_API_KEY,
        "openai": lambda: settings.OPENAI_API_KEY,
    }[provider]()
    if not key:
        raise ProviderUnavailableError(f"Provider {provider!r} không có API key.")
    return key


def complete(
    tier: str,
    messages: Sequence[dict[str, str]],
    *,
    system: str | None = None,
    max_tokens: int | None = None,
) -> Completion:
    """Gọi LLM theo TIER.

    tier      : "fast" | "standard" | "deep" — khớp configs/tiers.yaml.
    messages  : [{"role": "user"|"assistant", "content": "..."}, ...]
    system    : system prompt tĩnh (lấy từ configs/agents/<id>.yaml).
    max_tokens: trần output; mặc định và trần trên là tiers.<tier>.max_tokens.

    Trả về Completion gồm cả nội dung lẫn usage để harness cộng dồn.
    """
    cfg = resolve_tier(tier)
    key = _api_key(cfg.provider)
    cap = cfg.max_tokens if max_tokens is None else min(max_tokens, cfg.max_tokens)

    if cfg.provider == "anthropic":
        return _complete_anthropic(cfg, key, messages, system, cap)
    if cfg.provider == "openai":
        return _complete_openai(cfg, key, messages, system, cap)
    if cfg.provider == "gemini":
        return _complete_gemini(cfg, key, messages, system, cap)
    raise ProviderUnavailableError(f"Provider {cfg.provider!r} chưa được hỗ trợ.")


def _complete_anthropic(cfg, key, messages, system, cap) -> Completion:
    import anthropic  # lazy: chỉ import khi thật sự dùng provider này

    client = anthropic.Anthropic(api_key=key)
    kwargs: dict[str, Any] = {
        "model": cfg.model,
        "max_tokens": cap,
        "messages": [dict(m) for m in messages],
    }
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    text = "".join(getattr(b, "text", "") for b in resp.content)
    return Completion(
        content=text,
        input_tokens=int(resp.usage.input_tokens),
        output_tokens=int(resp.usage.output_tokens),
        tier=cfg.name,
        model=cfg.model,
    )


def _complete_openai(cfg, key, messages, system, cap) -> Completion:
    import openai  # lazy

    client = openai.OpenAI(api_key=key)
    payload = ([{"role": "system", "content": system}] if system else []) + [
        dict(m) for m in messages
    ]
    resp = client.chat.completions.create(
        model=cfg.model, max_tokens=cap, messages=payload
    )
    usage = resp.usage
    return Completion(
        content=resp.choices[0].message.content or "",
        input_tokens=int(getattr(usage, "prompt_tokens", 0)),
        output_tokens=int(getattr(usage, "completion_tokens", 0)),
        tier=cfg.name,
        model=cfg.model,
    )


def _complete_gemini(cfg, key, messages, system, cap) -> Completion:
    import google.generativeai as genai  # lazy

    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        model_name=cfg.model,
        system_instruction=system or None,
    )
    contents = [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [m["content"]],
        }
        for m in messages
    ]
    resp = model.generate_content(
        contents,
        generation_config=genai.types.GenerationConfig(max_output_tokens=cap),
    )
    meta = resp.usage_metadata
    return Completion(
        content=resp.text,
        input_tokens=int(getattr(meta, "prompt_token_count", 0)),
        output_tokens=int(getattr(meta, "candidates_token_count", 0)),
        tier=cfg.name,
        model=cfg.model,
    )
