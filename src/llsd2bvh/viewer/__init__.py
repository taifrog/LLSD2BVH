# -*- coding: utf-8 -*-
"""viewer package — lazy loading to avoid runpy RuntimeWarning.

`python -m llsd2bvh.viewer.viewer_window` で親パッケージが先に import され、
__init__ が viewer_window を即時 import すると sys.modules 二重登録で
RuntimeWarning が出るため、__getattr__ で遅延解決する。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "parse_bvh",
    "BvhData",
    "BvhJoint",
    "compute_frame_positions",
    "compute_all_frames",
    "StickFigureWidget",
    "BvhViewerWindow",
]

_LAZY_MAP = {
    "parse_bvh": ("llsd2bvh.viewer.bvh_parser", "parse_bvh"),
    "BvhData": ("llsd2bvh.viewer.bvh_parser", "BvhData"),
    "BvhJoint": ("llsd2bvh.viewer.bvh_parser", "BvhJoint"),
    "compute_frame_positions": ("llsd2bvh.viewer.fk", "compute_frame_positions"),
    "compute_all_frames": ("llsd2bvh.viewer.fk", "compute_all_frames"),
    "StickFigureWidget": ("llsd2bvh.viewer.gl_widget", "StickFigureWidget"),
    "BvhViewerWindow": ("llsd2bvh.viewer.viewer_window", "BvhViewerWindow"),
}

if TYPE_CHECKING:
    # 型チェッカー用に直接 import（実行時には遅延）
    from .bvh_parser import BvhData, BvhJoint, parse_bvh  # noqa: F401
    from .fk import compute_all_frames, compute_frame_positions  # noqa: F401
    from .gl_widget import StickFigureWidget  # noqa: F401
    from .viewer_window import BvhViewerWindow  # noqa: F401


def __getattr__(name: str):
    if name in _LAZY_MAP:
        import importlib

        mod_name, attr = _LAZY_MAP[name]
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
