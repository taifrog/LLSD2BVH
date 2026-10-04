# -*- coding: utf-8 -*-
"""縦パン＋最小幅上限のテスト(Qt offscreen)."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QEvent, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from llsd2bvh.widgets.timeline_view import TimelineView, ZOOM_WIDTH_MAX  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _press(view, x, y):
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(1000 + x, 1000 + y),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    view.mousePressEvent(ev)


def _move(view, x, y):
    ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(x, y), QPointF(1000 + x, 1000 + y),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    view.mouseMoveEvent(ev)


def _release(view, x, y):
    ev = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(x, y), QPointF(1000 + x, 1000 + y),
                     Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    view.mouseReleaseEvent(ev)


def _view_in_area(n, area_w=400, area_h=300, view_w=None):
    from llsd2bvh.widgets.timeline_view import LANE_H
    view = TimelineView()
    view.set_items([(Path(f"p{i}.llsd"), float(i)) for i in range(n)])
    need_h = 8 + 22 + 6 + n * LANE_H + 6
    view.resize(view_w or area_w, need_h)
    sa = QScrollArea()
    sa.setWidgetResizable(False)
    sa.setWidget(view)
    sa.resize(area_w, area_h)
    sa.show()
    _app.processEvents()
    _app.processEvents()
    return sa, view


def test_vertical_pan_moves_vscroll():
    sa, view = _view_in_area(30)
    vs = sa.verticalScrollBar()
    assert vs.maximum() > 0
    hs0 = sa.horizontalScrollBar().value()
    vs.setValue(100)
    _app.processEvents()
    _press(view, 5, 5)
    assert view._panning is True
    _move(view, 5, 35)
    assert vs.value() == 70
    assert sa.horizontalScrollBar().value() == hs0
    _release(view, 5, 35)
    assert view._panning is False
    sa.close()


def test_horizontal_pan_regression():
    sa, view = _view_in_area(3, view_w=2000)
    hs = sa.horizontalScrollBar()
    assert hs.maximum() > 0
    hs.setValue(100)
    _app.processEvents()
    _press(view, 5, 5)
    assert view._panning is True
    _move(view, 55, 5)
    assert hs.value() == 50
    _release(view, 55, 5)
    sa.close()


def test_zoom_width_cap():
    assert ZOOM_WIDTH_MAX == 1200
    view = TimelineView()
    view.set_zoom_width(5000)
    assert view.minimumWidth() == 1200
    assert view.maximumWidth() == 1200
    # 上限内は従来どおり（ズームも効く）
    view.set_zoom_width(700)
    assert view.minimumWidth() == 700
    view.setZoom(2.0)
    view.set_zoom_width(500)
    assert view.minimumWidth() == 1000
