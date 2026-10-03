# -*- coding: utf-8 -*-
"""TimelineViewレーン化のテスト(Qt offscreen)."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from llsd2bvh.widgets.timeline_view import LANE_H, TimelineView  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _view(n: int, duration: float = 150.0) -> TimelineView:
    v = TimelineView()
    v.resize(900, 600)
    v.set_duration(duration)
    v.set_items([(Path(f"pose{i:02d}.llsd"), float(i)) for i in range(n)])
    v.show()
    _app.processEvents()
    v.grab()
    _app.processEvents()
    return v


def test_lane_count_matches_items():
    v = _view(4)
    # 4レーン分の高さが確保される（1レーン約44px）
    assert v.minimumHeight() >= 4 * LANE_H


def test_hundred_lanes_no_collapse():
    v = _view(100, duration=600.0)
    assert v.minimumHeight() >= 100 * LANE_H
    assert v.maximumHeight() >= v.minimumHeight()


def test_set_duration_600():
    v = TimelineView()
    v.set_duration(600.0)
    assert v.duration() == 600.0
    v.set_duration(601.0)
    assert v.duration() == 600.0


def test_split_markers():
    v = TimelineView()
    v.set_duration(150.0)
    assert v.split_markers() == [60.0, 120.0]
    v.set_duration(60.0)
    assert v.split_markers() == []
    assert v.overlap_sec() == 2.0
    v.set_overlap_sec(5.0)
    assert v.overlap_sec() == 5.0
    v.set_overlap_sec(-1.0)
    assert v.overlap_sec() == 0.0


def test_hit_and_paint_smoke():
    # 描画・ヒットテストが例外なく動くこと
    v = _view(3, duration=5.0)
    assert v._hit_test(v.rect().center()) in (None, 0, 1, 2)
