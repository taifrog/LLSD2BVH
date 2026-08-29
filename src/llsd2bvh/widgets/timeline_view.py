# -*- coding: utf-8 -*-
"""タイムライン横表示ウィジェット。

- 横軸が時間 (0..duration)
- ブロックをドラッグで時刻変更、ダブルクリックで数値入力
- 先頭(0s)と末尾(duration)は固定でドラッグ不可
- リストの順序と時刻は同期（時刻でソートして表示）
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PySide6.QtWidgets import QWidget, QInputDialog
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics

BLOCK_W = 96
BLOCK_H = 36
TIMELINE_H = 22
PADDING_L = 10
PADDING_R = 10
PADDING_TOP = 8
PADDING_BOTTOM = 6

_BG = QColor(245, 245, 245)
_LINE = QColor(180, 180, 180)
_TICK = QColor(150, 150, 150)
_BLOCK_FILL = QColor(100, 160, 240)
_BLOCK_FIXED = QColor(70, 130, 210)
_BLOCK_TEXT = QColor(255, 255, 255)
_BLOCK_BORDER = QColor(40, 90, 170)


class TimelineView(QWidget):
    timeChanged = Signal()  # any item time changed
    itemDoubleClicked = Signal(int)  # index in sorted order

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.setMaximumHeight(110)
        self.setMouseTracking(True)
        self._duration = 5.0
        # items: List[Tuple[Path, float]] sorted by time, but we store unsorted and sort on paint
        self._items: List[Tuple[Path, float]] = []
        self._drag_idx: int | None = None
        self._drag_offset = 0
        self._hover_idx: int | None = None
        self.setToolTip("ドラッグで時刻を移動、ダブルクリックで数値入力（先頭0s/末尾durationは固定）")

    def set_duration(self, v: float):
        self._duration = max(0.1, min(60.0, v))
        self.update()

    def duration(self) -> float:
        return self._duration

    def set_items(self, items: List[Tuple[Path, float]]):
        # items time will be clamped and sorted internally on get
        self._items = list(items)
        # enforce t0=0, t_last=D if >=1
        self._enforce_endpoints()
        self.update()

    def get_items(self) -> List[Tuple[Path, float]]:
        # return sorted by time (and path for stability)
        return sorted(self._items, key=lambda x: (x[1], str(x[0]).lower()))

    def _enforce_endpoints(self):
        if not self._items:
            return
        # sort by time to find first/last
        sorted_items = sorted(self._items, key=lambda x: x[1])
        # force first 0, last D
        # we keep original order mapping by path identity (path+original index)
        # Simpler: after sort, set times
        # But to keep correspondence, we rebuild _items sorted with enforced times
        if len(sorted_items) == 1:
            # single: keep as is (no duration logic)
            return
        # enforce
        new_sorted = []
        for i, (p, t) in enumerate(sorted_items):
            if i == 0:
                t = 0.0
            elif i == len(sorted_items) - 1:
                t = float(self._duration)
            else:
                t = max(0.0, min(float(self._duration), float(t)))
                # prevent exactly 0 or D for middle items (keep epsilon)
                if t <= 0.001:
                    t = 0.001
                if t >= self._duration - 0.001:
                    t = self._duration - 0.001
            new_sorted.append((p, t))
        # sort again after clamping (middle may have moved)
        new_sorted.sort(key=lambda x: x[1])
        # re-enforce after sort (in case middle crossed endpoints)
        if len(new_sorted) >= 2:
            new_sorted[0] = (new_sorted[0][0], 0.0)
            new_sorted[-1] = (new_sorted[-1][0], float(self._duration))
        self._items = new_sorted

    def _time_to_x(self, t: float, width: int) -> int:
        avail = width - PADDING_L - PADDING_R - BLOCK_W
        if self._duration <= 1e-9:
            return PADDING_L
        frac = max(0.0, min(1.0, t / self._duration))
        return int(PADDING_L + frac * avail + BLOCK_W // 2)

    def _x_to_time(self, x: int, width: int) -> float:
        avail = width - PADDING_L - PADDING_R - BLOCK_W
        if avail <= 0:
            return 0.0
        frac = (x - PADDING_L - BLOCK_W // 2) / avail
        frac = max(0.0, min(1.0, frac))
        return frac * self._duration

    def _hit_test(self, pos: QPoint) -> int | None:
        w = self.width()
        for idx, (p, t) in enumerate(self.get_items()):
            cx = self._time_to_x(t, w)
            rect = QRect(cx - BLOCK_W // 2, PADDING_TOP + TIMELINE_H + 6, BLOCK_W, BLOCK_H)
            if rect.contains(pos):
                return idx
        return None

    # painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = self.width()
        h = self.height()
        # background
        painter.fillRect(self.rect(), _BG)

        # timeline line
        y_line = PADDING_TOP + TIMELINE_H // 2 + 4
        painter.setPen(QPen(_LINE, 2))
        painter.drawLine(PADDING_L + BLOCK_W // 2, y_line, w - PADDING_R - BLOCK_W // 2, y_line)

        # ticks
        painter.setPen(QPen(_TICK, 1))
        # tick step: 1 sec if duration<=10 else 5 sec, but at least 5 ticks
        if self._duration <= 10:
            step = 1.0
        elif self._duration <= 30:
            step = 5.0
        else:
            step = 10.0
        fm = QFontMetrics(self.font())
        t = 0.0
        while t <= self._duration + 1e-9:
            x = self._time_to_x(t, w)
            painter.drawLine(x, y_line - 6, x, y_line + 6)
            label = f"{t:.1f}s" if t != 0 else "0s"
            lw = fm.horizontalAdvance(label)
            painter.setPen(QColor(60, 60, 60))
            painter.drawText(x - lw // 2, PADDING_TOP + TIMELINE_H + 2, label)
            painter.setPen(QPen(_TICK, 1))
            t += step
        # ensure last tick drawn
        if abs(t - step - self._duration) > 1e-6:
            x = self._time_to_x(self._duration, w)
            painter.drawLine(x, y_line - 6, x, y_line + 6)
            label = f"{self._duration:.1f}s"
            lw = fm.horizontalAdvance(label)
            painter.setPen(QColor(60, 60, 60))
            painter.drawText(x - lw // 2, PADDING_TOP + TIMELINE_H + 2, label)

        # blocks
        items = self.get_items()
        for idx, (p, t) in enumerate(items):
            cx = self._time_to_x(t, w)
            rect_x = cx - BLOCK_W // 2
            rect_y = PADDING_TOP + TIMELINE_H + 6
            rect = QRect(rect_x, rect_y, BLOCK_W, BLOCK_H)
            is_fixed = (idx == 0 or idx == len(items) - 1) and len(items) >= 2
            is_hover = (idx == self._hover_idx)
            is_drag = (idx == self._drag_idx)
            fill = _BLOCK_FIXED if is_fixed else _BLOCK_FILL
            if is_hover:
                fill = QColor(min(255, fill.red() + 20), min(255, fill.green() + 20), min(255, fill.blue() + 20))
            if is_drag:
                fill = QColor(255, 200, 80)
            painter.setPen(QPen(_BLOCK_BORDER, 1.5))
            painter.setBrush(QBrush(fill))
            # rounded
            painter.drawRoundedRect(rect_x, rect_y, BLOCK_W, BLOCK_H, 6, 6)
            # text: filename
            painter.setPen(_BLOCK_TEXT)
            font = QFont(self.font())
            font.setPointSize(7)
            painter.setFont(font)
            name = p.name
            if len(name) > 14:
                name = name[:13] + "…"
            # centered
            tw = fm.horizontalAdvance(name)
            # use smaller fm for 7pt?
            fm2 = QFontMetrics(font)
            tw = fm2.horizontalAdvance(name)
            painter.drawText(rect_x + (BLOCK_W - tw) // 2, rect_y + 14, name)
            # time label
            t_label = f"{t:.2f}s"
            tw2 = fm2.horizontalAdvance(t_label)
            painter.drawText(rect_x + (BLOCK_W - tw2) // 2, rect_y + 27, t_label)
            # fixed indicator
            if is_fixed:
                painter.setPen(QColor(255, 255, 255, 180))
                small = QFont(font)
                small.setPointSize(6)
                painter.setFont(small)
                painter.drawText(rect_x + 4, rect_y + BLOCK_H - 4, "固定")

    # mouse
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            idx = self._hit_test(event.pos())
            if idx is not None:
                # fixed endpoints not draggable
                if len(self.get_items()) >= 2 and (idx == 0 or idx == len(self.get_items()) - 1):
                    return
                self._drag_idx = idx
                # offset within block
                w = self.width()
                p, t = self.get_items()[idx]
                cx = self._time_to_x(t, w)
                self._drag_offset = event.pos().x() - cx
                self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        w = self.width()
        # hover
        h_idx = self._hit_test(event.pos())
        if h_idx != self._hover_idx:
            self._hover_idx = h_idx
            self.update()
        if self._drag_idx is not None and event.buttons() & Qt.LeftButton:
            new_x = event.pos().x() - self._drag_offset
            new_t = self._x_to_time(new_x, w)
            # clamp
            items = self.get_items()
            # prevent crossing neighbors with epsilon
            eps = 0.05
            if self._drag_idx > 0:
                prev_t = items[self._drag_idx - 1][1]
                new_t = max(new_t, prev_t + eps)
            if self._drag_idx < len(items) - 1:
                next_t = items[self._drag_idx + 1][1]
                new_t = min(new_t, next_t - eps)
            new_t = max(0.0, min(self._duration, new_t))
            # update in _items (sorted order). Need to map sorted idx to _items index.
            # Since _items is kept sorted, we can update directly
            sorted_items = self.get_items()
            p, _ = sorted_items[self._drag_idx]
            # find in _items
            for i, (pp, _) in enumerate(self._items):
                if pp == p:
                    self._items[i] = (pp, new_t)
                    break
            # keep sorted
            self._items.sort(key=lambda x: x[1])
            # find new drag idx after sort (may have moved)
            # stay on same path
            for i, (pp, _) in enumerate(self.get_items()):
                if pp == p:
                    self._drag_idx = i
                    break
            self.timeChanged.emit()
            self.update()
        else:
            if self._drag_idx is None and h_idx is not None:
                # check fixed
                if len(self.get_items()) >= 2 and (h_idx == 0 or h_idx == len(self.get_items()) - 1):
                    self.setCursor(Qt.ArrowCursor)
                else:
                    self.setCursor(Qt.OpenHandCursor)
            elif self._drag_idx is None:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self._drag_idx is not None:
            self._drag_idx = None
            self.setCursor(Qt.ArrowCursor)
            self._enforce_endpoints()
            self.timeChanged.emit()
            self.update()

    def mouseDoubleClickEvent(self, event):
        idx = self._hit_test(event.pos())
        if idx is None:
            return
        items = self.get_items()
        if len(items) >= 2 and (idx == 0 or idx == len(items) - 1):
            return
        p, t = items[idx]
        val, ok = QInputDialog.getDouble(self, "時刻を入力", f"{p.name} の時刻 (0〜{self._duration:.2f}s):", t, 0.0, self._duration, 2)
        if ok:
            # clamp and enforce neighbor
            eps = 0.05
            if idx > 0:
                prev_t = items[idx - 1][1]
                val = max(val, prev_t + eps)
            if idx < len(items) - 1:
                next_t = items[idx + 1][1]
                val = min(val, next_t - eps)
            for i, (pp, _) in enumerate(self._items):
                if pp == p:
                    self._items[i] = (pp, float(val))
                    break
            self._items.sort(key=lambda x: x[1])
            self._enforce_endpoints()
            self.timeChanged.emit()
            self.update()

    def leaveEvent(self, event):
        self._hover_idx = None
        self.update()
