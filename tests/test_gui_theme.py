# -*- coding: utf-8 -*-
"""ダークテーマQSSのテスト(Qt offscreen)."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from llsd2bvh.gui import load_dark_stylesheet  # noqa: E402
from llsd2bvh.viewer.preview_panel import PreviewPanel  # noqa: E402

_app = QApplication.instance() or QApplication([])

QSS = Path(__file__).resolve().parents[1] / "src" / "llsd2bvh" / "dark.qss"


def test_qss_exists_and_loads():
    assert QSS.exists()
    assert QSS.stat().st_size > 0
    assert load_dark_stylesheet() is True
    assert "#1e1e1e" in (_app.styleSheet() or "")


def test_qss_missing_ignored():
    assert load_dark_stylesheet(base_dir=Path("Z:/no/such/dir")) is False


def test_panel_constructs_with_theme():
    load_dark_stylesheet()
    p = PreviewPanel()
    p.show()
    _app.processEvents()
    assert p.viewer is not None
    p.close()
