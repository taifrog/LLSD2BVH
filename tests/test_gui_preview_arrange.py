# -*- coding: utf-8 -*-
"""プレビューボタン削除＋part選択移動のテスト(Qt offscreen)."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QHBoxLayout  # noqa: E402

from llsd2bvh.gui import MainWindow  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _win():
    w = MainWindow()
    w.show()
    _app.processEvents()
    _app.processEvents()
    return w


def test_no_preview_button():
    w = _win()
    assert not hasattr(w, "btn_preview")
    assert not hasattr(w, "on_preview")
    assert not hasattr(w, "_update_preview_button")
    assert w.btn_viewer is not None
    assert w.btn_convert is not None
    assert w.btn_close is not None
    assert w.btn_viewer.text() != ""
    w.close()


def test_part_selector_on_panel_top():
    w = _win()
    # Panel先頭行にpart選択があること
    first = w.preview_panel.layout().itemAt(0)
    assert first is not None
    row = first.layout()
    assert isinstance(row, QHBoxLayout)
    widgets = [row.itemAt(i).widget() for i in range(row.count())]
    assert w.lbl_part in widgets
    assert w.combo_part in widgets
    # Panelの子として再親付けされていること
    assert w.combo_part.parent() is w.preview_panel
    w.close()


def test_part_wiring_and_empty_disable(tmp_path, monkeypatch):
    import llsd2bvh.gui as gui_mod
    from llsd2bvh.cli import main as cli_main
    s = Path(__file__).parent / "samples"
    out = tmp_path / "one.bvh"
    assert cli_main([str(s / "testChange03.xml"), "-o", str(out)]) == 0

    class _Box:
        @staticmethod
        def warning(*a, **k):
            return None

        @staticmethod
        def critical(*a, **k):
            return None

        @staticmethod
        def information(*a, **k):
            return None

    monkeypatch.setattr(gui_mod, "QMessageBox", _Box)
    w = _win()
    assert w.combo_part.isEnabled() is False
    w._last_part_paths = [out]
    w.combo_part.blockSignals(True)
    w.combo_part.clear()
    w.combo_part.addItems([out.name])
    w.combo_part.blockSignals(False)
    w.combo_part.setCurrentIndex(-1)
    w.combo_part.setCurrentIndex(0)
    _app.processEvents()
    assert w.preview_panel.bvh is not None
    w.close()
