# -*- coding: utf-8 -*-
"""タイムライン横表示ウィジェット（左端ピン＋縦ずらし＋番号）."""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Dict

from PySide6.QtWidgets import QWidget, QInputDialog
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QPolygon

BLOCK_W = 96
BLOCK_H = 36
TIMELINE_H = 22
PADDING_L = 10
PADDING_R = 10
PADDING_TOP = 8
PADDING_BOTTOM = 6
ROW_GAP = 8
PIN_W = 10
PIN_H = 7
GAP_X = 6  # 重なり判定の余白

_BG = QColor(245, 245, 245)
_LINE = QColor(180, 180, 180)
_TICK = QColor(150, 150, 150)
_BLOCK_FILL = QColor(100, 160, 240)
_BLOCK_FIXED = QColor(70, 130, 210)
_BLOCK_TEXT = QColor(255, 255, 255)
_BLOCK_BORDER = QColor(40, 90, 170)


class TimelineView(QWidget):
    timeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.setMaximumHeight(150)
        self.setMouseTracking(True)
        self._duration = 5.0
        self._items: List[Tuple[Path, float]] = []
        self._number_map: Dict[str, int] = {}
        self._ordered_paths: List[Path] = []
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
        self._items = list(items)
        self._enforce_endpoints()
        self.update()

    def get_items(self) -> List[Tuple[Path, float]]:
        return sorted(self._items, key=lambda x: (x[1], str(x[0]).lower()))

    def set_number_map(self, m: Dict[str, int]):
        self._number_map = dict(m)
        self.update()

    def set_ordered_paths(self, paths: List[Path]):
        """重複対応のリスト順番号（1..N）を保持。paintで優先参照。"""
        self._ordered_paths = list(paths)
        self.update()

    def _resolve_number(self, p: Path, idx: int, items: List[Tuple[Path, float]]) -> int:
        # 重複対応: 同一パスの出現回数で ordered_paths の n回目の出現位置を返す
        if self._ordered_paths:
            # idx までの同一パス出現回数（0-based）
            occ_idx = 0
            target_str = str(p)
            for j in range(idx):
                if str(items[j][0]) == target_str:
                    occ_idx += 1
            # ordered_paths 側で occ_idx 回目の出現を探す
            cur = -1
            for oi, op in enumerate(self._ordered_paths):
                if str(op) == target_str:
                    cur += 1
                    if cur == occ_idx:
                        return oi + 1
        # フォールバック: 旧 dict or idx+1
        return self._number_map.get(str(p), idx + 1)

    def _enforce_endpoints(self):
        if not self._items:
            return
        sorted_items = sorted(self._items, key=lambda x: x[1])
        if len(sorted_items) == 1:
            return
        new_sorted = []
        for i, (p, t) in enumerate(sorted_items):
            if i == 0:
                t = 0.0
            elif i == len(sorted_items) - 1:
                t = float(self._duration)
            else:
                t = max(0.0, min(float(self._duration), float(t)))
                if t <= 0.001:
                    t = 0.001
                if t >= self._duration - 0.001:
                    t = self._duration - 0.001
            new_sorted.append((p, t))
        new_sorted.sort(key=lambda x: x[1])
        if len(new_sorted) >= 2:
            new_sorted[0] = (new_sorted[0][0], 0.0)
            new_sorted[-1] = (new_sorted[-1][0], float(self._duration))
        self._items = new_sorted

    def _time_to_x(self, t: float, width: int) -> int:
        avail = width - PADDING_L - PADDING_R - BLOCK_W
        if self._duration <= 1e-9 or avail <= 0:
            return PADDING_L
        frac = max(0.0, min(1.0, t / self._duration))
        return int(PADDING_L + frac * avail)

    def _x_to_time(self, x: int, width: int) -> float:
        avail = width - PADDING_L - PADDING_R - BLOCK_W
        if avail <= 0:
            return 0.0
        frac = (x - PADDING_L) / avail
        frac = max(0.0, min(1.0, frac))
        return frac * self._duration

    def _compute_rows(self, items: List[Tuple[Path, float]], width: int) -> List[int]:
        """重なりを縦ずらし: 同一行でXが重なる場合は別行へ。2段のみ。"""
        rows: List[int] = []
        xs: List[int] = [self._time_to_x(t, width) for _, t in items]
        for i, x in enumerate(xs):
            # 試す行: 0→1
            chosen = 0
            for try_row in (0, 1):
                overlap = False
                for j in range(i):
                    if rows[j] == try_row and x < xs[j] + BLOCK_W + GAP_X and xs[j] < x + BLOCK_W + GAP_X:
                        overlap = True
                        break
                if not overlap:
                    chosen = try_row
                    break
                # 両行とも重なる場合ははみ出しを許容（要件4: はみ出し表示不可でOK）
                chosen = try_row
            rows.append(chosen)
        return rows

    def _hit_test(self, pos: QPoint) -> int | None:
        w = self.width()
        items = self.get_items()
        if not items:
            return None
        rows = self._compute_rows(items, w)
        for idx, (p, t) in enumerate(items):
            x = self._time_to_x(t, w)
            row = rows[idx]
            y = PADDING_TOP + TIMELINE_H + 6 + row * (BLOCK_H + ROW_GAP)
            rect = QRect(x, y, BLOCK_W, BLOCK_H)
            if rect.contains(pos):
                return idx
            # ピン部分もヒット
            y_line = PADDING_TOP + TIMELINE_H // 2 + 4
            pin_rect = QRect(x - PIN_W, y_line, PIN_W * 2, y - y_line)
            if pin_rect.contains(pos):
                return idx
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = self.width()
        painter.fillRect(self.rect(), _BG)

        y_line = PADDING_TOP + TIMELINE_H // 2 + 4
        painter.setPen(QPen(_LINE, 2))
        # 左端基準のため線は PADDING_L から w-PADDING_R-BLOCK_W まで
        painter.drawLine(PADDING_L, y_line, w - PADDING_R - BLOCK_W, y_line)

        # ticks
        painter.setPen(QPen(_TICK, 1))
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
            # 左端基準なのでラベルはxを中央寄せ
            painter.drawText(x - lw // 2, PADDING_TOP + TIMELINE_H + 2, label)
            painter.setPen(QPen(_TICK, 1))
            t += step
        if abs(t - step - self._duration) > 1e-6:
            x = self._time_to_x(self._duration, w)
            painter.drawLine(x, y_line - 6, x, y_line + 6)
            label = f"{self._duration:.1f}s"
            lw = fm.horizontalAdvance(label)
            painter.setPen(QColor(60, 60, 60))
            painter.drawText(x - lw // 2, PADDING_TOP + TIMELINE_H + 2, label)

        items = self.get_items()
        if not items:
            return
        rows = self._compute_rows(items, w)
        # 必要高さを動的に反映（2段時は高く）
        max_row = max(rows) if rows else 0
        needed_h = PADDING_TOP + TIMELINE_H + 6 + (max_row + 1) * (BLOCK_H + ROW_GAP) + PADDING_BOTTOM
        if needed_h != self.minimumHeight():
            self.setMinimumHeight(max(110, needed_h))
            self.setMaximumHeight(max(150, needed_h))

        for idx, (p, t) in enumerate(items):
            x = self._time_to_x(t, w)
            row = rows[idx]
            rect_x = x
            rect_y = PADDING_TOP + TIMELINE_H + 6 + row * (BLOCK_H + ROW_GAP)
            is_fixed = (idx == 0 or idx == len(items) - 1) and len(items) >= 2
            is_hover = (idx == self._hover_idx)
            is_drag = (idx == self._drag_idx)
            fill = _BLOCK_FIXED if is_fixed else _BLOCK_FILL
            if is_hover:
                fill = QColor(min(255, fill.red() + 20), min(255, fill.green() + 20), min(255, fill.blue() + 20))
            if is_drag:
                fill = QColor(255, 200, 80)

            # ピン（同色）: 左端からタイムラインへ垂直線＋三角
            painter.setPen(QPen(fill.darker(120), 1.5))
            painter.setBrush(QBrush(fill))
            # 垂直線（左端）
            painter.drawLine(x, y_line, x, rect_y)
            # 三角ピン（タイムライン上に下向き）
            poly = QPolygon([QPoint(x, y_line), QPoint(x - PIN_W // 2, y_line + PIN_H), QPoint(x + PIN_W // 2, y_line + PIN_H)])
            painter.drawPolygon(poly)

            # ブロック本体
            painter.setPen(QPen(_BLOCK_BORDER, 1.5))
            painter.setBrush(QBrush(fill))
            painter.drawRoundedRect(rect_x, rect_y, BLOCK_W, BLOCK_H, 6, 6)

            # 番号＋ファイル名（番号は必須、重複対応）
            num = self._resolve_number(p, idx, items)
            painter.setPen(_BLOCK_TEXT)
            font = QFont(self.font())
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            fm2 = QFontMetrics(font)
            # 1行目: "#n 名前"
            short = p.name
            # 番号込みで省略
            prefix = f"#{num} "
            # 残り幅で省略
            avail_w = BLOCK_W - 8
            full_label = prefix + short
            # 省略処理
            while fm2.horizontalAdvance(full_label) > avail_w and len(short) > 4:
                short = short[:-5] + "…"
                full_label = prefix + short
            tw = fm2.horizontalAdvance(full_label)
            painter.drawText(rect_x + (BLOCK_W - tw) // 2, rect_y + 14, full_label)

            # 2行目: 時刻
            font2 = QFont(self.font())
            font2.setPointSize(7)
            font2.setBold(False)
            painter.setFont(font2)
            fm3 = QFontMetrics(font2)
            t_label = f"{t:.2f}s"
            tw2 = fm3.horizontalAdvance(t_label)
            painter.drawText(rect_x + (BLOCK_W - tw2) // 2, rect_y + 27, t_label)

            if is_fixed:
                painter.setPen(QColor(255, 255, 255, 180))
                small = QFont(font2)
                small.setPointSize(6)
                painter.setFont(small)
                painter.drawText(rect_x + 4, rect_y + BLOCK_H - 4, "固定")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            idx = self._hit_test(event.pos())
            if idx is not None:
                if len(self.get_items()) >= 2 and (idx == 0 or idx == len(self.get_items()) - 1):
                    return
                self._drag_idx = idx
                w = self.width()
                p, t = self.get_items()[idx]
                x = self._time_to_x(t, w)
                self._drag_offset = event.pos().x() - x
                self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        w = self.width()
        h_idx = self._hit_test(event.pos())
        if h_idx != self._hover_idx:
            self._hover_idx = h_idx
            self.update()
        if self._drag_idx is not None and event.buttons() & Qt.LeftButton:
            new_x = event.pos().x() - self._drag_offset
            new_t = self._x_to_time(new_x, w)
            items = self.get_items()
            eps = 0.05
            if self._drag_idx > 0:
                prev_t = items[self._drag_idx - 1][1]
                new_t = max(new_t, prev_t + eps)
            if self._drag_idx < len(items) - 1:
                next_t = items[self._drag_idx + 1][1]
                new_t = min(new_t, next_t - eps)
            new_t = max(0.0, min(self._duration, new_t))
            sorted_items = self.get_items()
            p, _ = sorted_items[self._drag_idx]
            # 重複対応: drag対象の出現回数で特定
            target_str = str(p)
            occ = sum(1 for j in range(self._drag_idx + 1) if str(sorted_items[j][0]) == target_str)
            cur = 0
            for i, (pp, _) in enumerate(self._items):
                if str(pp) == target_str:
                    cur += 1
                    if cur == occ:
                        self._items[i] = (pp, new_t)
                        break
            self._items.sort(key=lambda x: x[1])
            # 新しい drag_idx を同一出現回数で再特定
            new_sorted = self.get_items()
            cur = 0
            for i, (pp, _) in enumerate(new_sorted):
                if str(pp) == target_str:
                    cur += 1
                    if cur == occ:
                        self._drag_idx = i
                        break
            self.timeChanged.emit()
            self.update()
        else:
            if self._drag_idx is None and h_idx is not None:
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
        val, ok = QInputDialog.getDouble(self, "時刻を入力", f"{p.name} の時刻 (0～{self._duration:.2f}s):", t, 0.0, self._duration, 2)
        if ok:
            eps = 0.05
            if idx > 0:
                prev_t = items[idx - 1][1]
                val = max(val, prev_t + eps)
            if idx < len(items) - 1:
                next_t = items[idx + 1][1]
                val = min(val, next_t - eps)
            # 重複対応で出現回数で特定
            target_str = str(p)
            occ = sum(1 for j in range(idx + 1) if str(items[j][0]) == target_str)
            cur = 0
            for i, (pp, _) in enumerate(self._items):
                if str(pp) == target_str:
                    cur += 1
                    if cur == occ:
                        self._items[i] = (pp, float(val))
                        break
            self._items.sort(key=lambda x: x[1])
            self._enforce_endpoints()
            self.timeChanged.emit()
            self.update()

    def leaveEvent(self, event):
        self._hover_idx = None
        self.update()
