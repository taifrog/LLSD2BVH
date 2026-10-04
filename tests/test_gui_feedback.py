# -*- coding: utf-8 -*-
"""検証フィードバック5点のテスト(Qt offscreen)."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QEvent, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QLayout, QScrollArea  # noqa: E402

from llsd2bvh.gui import MainWindow  # noqa: E402
from llsd2bvh.viewer.preview_panel import PreviewPanel  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _layout_index_of(layout, widget):
    for i in range(layout.count()):
        item = layout.itemAt(i)
        w = item.widget()
        if w is widget:
            return i
        sub = item.layout()
        if sub is not None:
            for j in range(sub.count()):
                if sub.itemAt(j).widget() is widget:
                    return i
    return -1


def test_viewpoint_row_above_info():
    p = PreviewPanel()
    p.show()
    _app.processEvents()
    root = p.layout()
    assert isinstance(root, QLayout)
    assert _layout_index_of(root, p.btn_front) < _layout_index_of(root, p.lbl_frame)
    p.close()


def test_list_width_independent_of_path():
    w = MainWindow()
    w.show()
    _app.processEvents()
    longs = [f"C:/x/{'a' * 200}{i}.xml" for i in range(4)]
    w.add_files(longs)
    _app.processEvents()
    # 200字パス×4でもsizeHintは省略幅に収まる（フルパス展開なら1000px超）
    assert w.list_widget.sizeHint().width() <= 300
    item = w.list_widget.item(0)
    assert longs[0] not in item.text()
    assert ".xml" not in item.text()
    from pathlib import PureWindowsPath
    assert item.toolTip() == str(PureWindowsPath(longs[0]))
    w.close()


def test_drag_keeps_min_width():
    from llsd2bvh.widgets.timeline_view import TimelineView
    view = TimelineView()
    view.set_items([(Path(f"p{i}.llsd"), float(i)) for i in range(3)])
    sa = QScrollArea()
    sa.setWidgetResizable(False)
    sa.setWidget(view)
    sa.resize(900, 300)
    sa.show()
    _app.processEvents()
    _app.processEvents()
    items = view.get_items()
    x = view._time_to_x(items[1][1], view.width())
    y = view._lane_y(1) + 20
    w0 = view.minimumWidth()
    h0 = view.minimumSizeHint()
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(500 + x, 500 + y),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    view.mousePressEvent(press)
    move = QMouseEvent(QEvent.Type.MouseMove, QPointF(x + 40, y), QPointF(540 + x, 500 + y),
                       Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    view.mouseMoveEvent(move)
    rel = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(x + 40, y), QPointF(540 + x, 500 + y),
                      Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    view.mouseReleaseEvent(rel)
    assert view.minimumWidth() == w0
    assert view.minimumSizeHint() == h0
    sa.close()


def test_convert_autoloads_part01(tmp_path, monkeypatch):
    import llsd2bvh.gui as gui_mod
    s = Path(__file__).parent / "samples"

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
    w = MainWindow()
    w.show()
    _app.processEvents()
    w.add_files([str(s / "testChange03.xml"), str(s / "testChange04.xml")])
    _app.processEvents()
    w.edit_output.setText(str(tmp_path))
    w.on_convert()
    _app.processEvents()
    assert w.preview_panel.bvh is not None
    assert w.preview_panel._path is not None
    assert w.preview_panel._path.name.endswith("part01.bvh")
    w.close()


def test_info_label_fixed_wrap():
    p = PreviewPanel()
    p.show()
    _app.processEvents()
    assert p.lbl_frame.wordWrap() is True
    assert p.lbl_frame.minimumWidth() == p.lbl_frame.maximumWidth()
    w0 = p.lbl_frame.width()
    p.lbl_frame.setText("0/1 t=0.000s / 5.000s dt=5.0000s")
    _app.processEvents()
    p.lbl_frame.setText("12->13 (50%) f=12.50 t=0.375s / 3.000s dt=0.0333s [interp]")
    _app.processEvents()
    assert p.lbl_frame.width() == w0
    p.close()
