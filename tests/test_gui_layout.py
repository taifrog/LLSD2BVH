# -*- coding: utf-8 -*-
"""3ペインレイアウト＋内蔵プレビューのテスト(Qt offscreen)."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSplitter  # noqa: E402

from llsd2bvh.gui import MainWindow  # noqa: E402
from llsd2bvh.viewer.viewer_window import BvhViewerWindow  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _win():
    w = MainWindow()
    w.resize(1000, 700)
    w.show()
    _app.processEvents()
    _app.processEvents()
    return w


def test_three_panes():
    w = _win()
    assert isinstance(w.splitter, QSplitter)
    assert w.splitter.count() == 3
    assert w.pane_left.isWidgetType() and w.pane_mid.isWidgetType()
    assert w.preview_panel is not None
    w.close()


def test_initial_ratio_20_60_20():
    # 比率計算そのもの（レイアウト極小値はQt依存のため静的検証）
    assert MainWindow._default_sizes(1000) == [200, 600, 200]
    assert sum(MainWindow._default_sizes(999)) == 999


def test_splitter_persistence_roundtrip(monkeypatch):
    # 保存値がsetSizesにそのまま渡ること（Qt側クランプとは独立に検証）
    from PySide6.QtWidgets import QSplitter as _QS
    w = _win()
    w.settings.setValue("splitterSizes", [600, 1000, 900])
    w.settings.setValue("previewFolded", "false")
    calls = []
    orig = _QS.setSizes

    def _spy(self, sizes):
        calls.append(list(sizes))
        return orig(self, sizes)

    monkeypatch.setattr(_QS, "setSizes", _spy)
    w._apply_initial_splitter_sizes()
    assert calls and calls[-1] == [600, 1000, 900]
    assert w.pane_right.isVisible()
    # 移動記憶の書込確認
    w._on_splitter_moved()
    saved = [int(x) for x in w.settings.value("splitterSizes")]
    assert saved == list(w.splitter.sizes())
    w.close()


def test_fold_toggle():
    w = _win()
    assert w.pane_right.isVisible()
    w.btn_fold_preview.setChecked(False)
    _app.processEvents()
    assert not w.pane_right.isVisible()
    w.btn_fold_preview.setChecked(True)
    _app.processEvents()
    assert w.pane_right.isVisible()
    w.close()


def test_combo_to_panel_wiring(tmp_path):
    from llsd2bvh.cli import main as cli_main
    s = Path(__file__).parent / "samples"
    out = tmp_path / "one.bvh"
    assert cli_main([str(s / "testChange03.xml"), "-o", str(out)]) == 0
    w = _win()
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


def test_language_propagates_to_panel():
    w = _win()
    w.set_language("en")
    assert w.preview_panel.lang == "en"
    w.set_language("ja")
    assert w.preview_panel.lang == "ja"
    w.close()


def test_standalone_viewer_entry_intact():
    assert callable(BvhViewerWindow)
    assert callable(MainWindow.on_viewer)
