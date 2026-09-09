"""Path traversal phải raise, không được im lặng cho qua."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.run_context import RunContext  # noqa: E402


@pytest.fixture()
def ctx(tmp_path: Path) -> RunContext:
    return RunContext.create("run_test", runs_dir=tmp_path)


@pytest.mark.parametrize(
    "bad",
    [
        "../../etc/passwd",
        "..",
        "../outside.txt",
        "output/../../escape.txt",
        r"C:\Windows\System32",
        r"C:\Windows\System32\drivers\etc\hosts",
        "/etc/passwd",
        r"\\server\share\file.txt",
        "",
        "   ",
    ],
)
def test_traversal_bi_tu_choi(ctx: RunContext, bad: str) -> None:
    with pytest.raises(PermissionError):
        ctx.resolve_path(bad)


def test_duong_dan_hop_le_nam_trong_workspace(ctx: RunContext) -> None:
    path = ctx.resolve_path("output/result.json")
    assert ctx.workspace_dir in path.parents


def test_ghi_va_doc_qua_ctx(ctx: RunContext) -> None:
    ctx.write_text("output/summary.txt", "xin chào")
    assert ctx.read_text("output/summary.txt") == "xin chào"


def test_khong_ghi_duoc_ra_ngoai_workspace(ctx: RunContext, tmp_path: Path) -> None:
    with pytest.raises(PermissionError):
        ctx.write_text("../thoat.txt", "khong duoc phep")
    assert not (tmp_path / "thoat.txt").exists()


def test_symlink_tro_ra_ngoai_bi_tu_choi(ctx: RunContext, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = ctx.workspace_dir / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Máy không cho tạo symlink (Windows cần quyền Developer Mode).")
    with pytest.raises(PermissionError):
        ctx.resolve_path("link/file.txt")
