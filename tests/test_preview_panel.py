# -*- coding: utf-8 -*-
"""PreviewPanel抽出のテスト(Qt offscreen。GL実描画は対象外)."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from llsd2bvh.viewer import preview_panel as pp_mod  # noqa: E402
from llsd2bvh.viewer.preview_panel import PreviewPanel  # noqa: E402
from llsd2bvh.viewer.viewer_window import BvhViewerWindow  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _panel(**kw):
    p = PreviewPanel(**kw)
    p.show()
    _app.processEvents()
    return p


def test_api_exists():
    p = _panel()
    assert callable(p.set_part_paths)
    assert callable(p.load_bvh)
    assert callable(p.set_language)
    assert p._gl_ok is True
    p.close()


def test_empty_parts_disable_transport():
    p = _panel()
    p.set_part_paths([])
    assert p._part_paths == []
    assert p.bvh is None
    assert p.btn_play.isEnabled() is False
    assert p.slider.isEnabled() is False
    p.close()


def test_set_language():
    p = _panel()
    p.set_language("en")
    assert p.lang == "en"
    assert "Front" in p.btn_front.text()
    p.set_language("xx")
    assert p.lang == "en"
    p.set_language("ja")
    assert "正面" in p.btn_front.text()
    p.close()


def test_gl_failure_placeholder(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("no GL")

    monkeypatch.setattr(pp_mod, "StickFigureWidget", _boom)
    p = _panel()
    assert p._gl_ok is False
    assert isinstance(p.viewer, QLabel)
    assert "利用不可" in p.viewer.text()
    # 空状態にすれば再生系disable（初期既定値は既存仕様どおりenabledのまま）
    p.set_part_paths([])
    assert p.btn_play.isEnabled() is False
    p.set_language("en")
    assert "unavailable" in p.viewer.text().lower()
    p.close()


def test_load_real_bvh(tmp_path):
    from llsd2bvh.cli import main as cli_main
    s = Path(__file__).parent / "samples"
    out = tmp_path / "one.bvh"
    assert cli_main([str(s / "testChange03.xml"), "-o", str(out)]) == 0
    p = _panel()
    assert p.load_bvh(out) is True
    assert p.bvh is not None
    assert p.btn_play.isEnabled() is True
    p.set_part_paths([out])
    assert p._part_paths == [out]
    p.close()


def test_wrapper_hosts_panel(tmp_path, monkeypatch):
    from llsd2bvh.cli import main as cli_main
    s = Path(__file__).parent / "samples"
    out = tmp_path / "one.bvh"
    assert cli_main([str(s / "testChange03.xml"), "-o", str(out)]) == 0
    w = BvhViewerWindow(initial_path=out)
    w.show()
    _app.processEvents()
    assert w.panel.bvh is not None
    assert w.windowTitle().endswith("one.bvh")

    class _Box:
        @staticmethod
        def warning(*a, **k):
            return None

        @staticmethod
        def critical(*a, **k):
            return None

    monkeypatch.setattr(pp_mod, "QMessageBox", _Box)
    assert w.load_bvh(tmp_path / "missing.bvh") is False
    w.close()
