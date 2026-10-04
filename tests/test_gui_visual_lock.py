# -*- coding: utf-8 -*-
"""目視FB再現の固定テスト(Qt offscreen): 左幅・中央幅・背景暗色."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QEvent, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from llsd2bvh.gui import MainWindow  # noqa: E402
from llsd2bvh.widgets import timeline_view as tv_mod  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _win():
    w = MainWindow()
    w.show()
    _app.processEvents()
    _app.processEvents()
    return w


def _drag_middle_block(w):
    tv = w.timeline_view
    items = tv.get_items()
    assert len(items) >= 3
    x = tv._time_to_x(items[1][1], tv.width())
    y = tv._lane_y(1) + 20

    def _ev(t, px, py, btn, btns):
        return QMouseEvent(t, QPointF(px, py), QPointF(900 + px, 900 + py), btn, btns, Qt.NoModifier)

    tv.mousePressEvent(_ev(QEvent.Type.MouseButtonPress, x, y, Qt.LeftButton, Qt.LeftButton))
    tv.mouseMoveEvent(_ev(QEvent.Type.MouseMove, x + 120, y, Qt.LeftButton, Qt.LeftButton))
    tv.mouseReleaseEvent(_ev(QEvent.Type.MouseButtonRelease, x + 120, y, Qt.LeftButton, Qt.NoButton))
    _app.processEvents()


def test_left_pane_width_stable_on_add():
    # 200字パス×4追加でも左ペイン幅が延びない
    w = _win()
    w0 = w.pane_left.width()
    w.add_files([f"C:/x/{'b' * 200}{i}.xml" for i in range(4)])
    _app.processEvents()
    assert w.pane_left.width() == w0
    assert w.list_widget.maximumWidth() == 250
    w.close()


def test_center_width_stable_on_drag():
    # ポーズ枠ドラッグ前後でタイムライン枠の幅同一
    w = _win()
    s = Path(__file__).parent / "samples"
    w.add_files([str(s / "testChange01.xml"), str(s / "testChange02.xml"), str(s / "testChange03.xml")])
    _app.processEvents()
    tv = w.timeline_view
    w0, mw0 = tv.width(), tv.minimumWidth()
    _drag_middle_block(w)
    assert tv.minimumWidth() == mw0
    assert tv.width() == w0
    w.close()


def test_timeline_dark_defaults():
    assert tv_mod._BG == QColor(30, 30, 30)
    assert tv_mod._TEXT.lightness() > 180
    assert tv_mod._LANE_TEXT.lightness() > 100
    # 暗背景で描画例外なし
    from llsd2bvh.widgets.timeline_view import TimelineView
    v = TimelineView()
    v.set_items([(Path(f"p{i}.llsd"), float(i)) for i in range(3)])
    v.resize(800, 200)
    v.show()
    _app.processEvents()
    v.grab()
    _app.processEvents()
    v.close()
