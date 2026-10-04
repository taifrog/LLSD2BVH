# -*- coding: utf-8 -*-
"""タイムライン横表示ウィジェット（ファイル毎1レーン＋分割線＋重なり帯）."""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Dict

from PySide6.QtWidgets import QWidget, QInputDialog
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QPolygon

BLOCK_W = 96
BLOCK_H = 36
LANE_H = 44
HEADER_W = 132
TIMELINE_H = 22
# ズーム幅の上限。超過分は横スクロールで吸収し、ペイン全体の最小幅を押し上げない。
ZOOM_WIDTH_MAX = 1200
PADDING_L = 10
PADDING_R = 10
PADDING_TOP = 8
PADDING_BOTTOM = 6
PIN_W = 10
PIN_H = 7

# Zoom: 100%〜400%、±50%刻み
ZOOM_MIN = 1.0
ZOOM_MAX = 4.0
ZOOM_STEP = 0.5

_BG = QColor(30, 30, 30)
_LINE = QColor(154, 154, 154)
_TICK = QColor(154, 154, 154)
_TEXT = QColor(224, 224, 224)
_LANE_TEXT = QColor(206, 145, 120)
_BLOCK_FILL = QColor(100, 160, 240)
_BLOCK_FIXED = QColor(70, 130, 210)
_BLOCK_TEXT = QColor(255, 255, 255)
_BLOCK_BORDER = QColor(40, 90, 170)
_SPLIT_LINE = QColor(220, 60, 60)
_OVERLAP_BAND = QColor(240, 200, 60, 90)

_DEFAULT_TOOLTIP = "ドラッグで時刻を移動、ダブルクリックで数値入力（先頭0s/末尾durationは固定）／空所をドラッグで左右スクロール／ホイールで拡大縮小"


def elide_middle_label(prefix: str, name: str, avail_w: float, advance) -> str:
    """ブロック内ラベルを中間省略で詰める。末尾（識別数字・拡張子）を残す。

    args:
        prefix: "#n " 等の接頭辞（省略しない）
        name: ファイル名
        avail_w: 使用可能な幅 (px)
        advance: 文字列 -> 幅 (px) の計測関数（QFontMetrics.horizontalAdvance 等）

    96px固定幅でも `MuMuDance01〜08` が `#n MuMuDa…` で全滅する問題を避け、
    `#3 MuMu…e03.xml` のように末尾を残す。
    """
    full = prefix + name
    try:
        if advance(full) <= avail_w:
            return full
    except Exception:
        return full
    if "." in name:
        stem, dot, ext = name.rpartition(".")
        ext_part = dot + ext
    else:
        stem, ext_part = name, ""
    tail_core = stem[-4:] if len(stem) > 4 else stem
    head = stem[:-4] if len(stem) > 4 else ""
    tail = tail_core + ext_part
    try:
        while head and advance(prefix + head + "…" + tail) > avail_w:
            head = head[:-1]
        while not head and len(tail) > 1 and advance(prefix + "…" + tail) > avail_w:
            tail = tail[1:]
    except Exception:
        return full
    return prefix + head + "…" + tail


class TimelineView(QWidget):
    timeChanged = Signal()
    zoomChanged = Signal(float)
    zoomRequest = Signal(int)  # +1 zoomIn / -1 zoomOut via wheel

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        # 最大高さの上限は設けない（100レーン時は親QScrollAreaの縦スクロールに任せる）
        self.setMouseTracking(True)
        self._duration = 5.0
        self._split_sec = 60.0
        self._overlap_sec = 2.0
        self._items: List[Tuple[Path, float]] = []
        self._number_map: Dict[str, int] = {}
        self._ordered_paths: List[Path] = []
        self._drag_idx: int | None = None
        self._drag_offset = 0
        self._hover_idx: int | None = None
        self._zoom = 1.0
        self._panning = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._pan_start_scroll = 0
        self._pan_start_vscroll = 0
        self._default_tooltip = _DEFAULT_TOOLTIP
        self.setToolTip(self._default_tooltip)

    def set_duration(self, v: float):
        self._duration = max(0.1, min(600.0, v))
        self.update()

    def split_sec(self) -> float:
        """分割線の間隔（秒）。"""
        return self._split_sec

    def set_split_sec(self, v: float) -> None:
        """分割線の間隔を設定する。

        Args:
            v: 秒数。正でなければ無視する。
        """
        if v is None or float(v) <= 0:
            return
        self._split_sec = float(v)
        self.update()

    def overlap_sec(self) -> float:
        """重なり帯の秒数。"""
        return self._overlap_sec

    def set_overlap_sec(self, v: float) -> None:
        """重なり帯の秒数を設定する。

        Args:
            v: 秒数。負値は0扱いにする。
        """
        self._overlap_sec = max(0.0, float(v))
        self.update()

    def split_markers(self) -> List[float]:
        """分割線の時刻リスト（duration未満の split_sec 刻み）。"""
        marks: List[float] = []
        m = self._split_sec
        while m < self._duration - 1e-9:
            marks.append(m)
            m += self._split_sec
        return marks

    def duration(self) -> float:
        return self._duration

    # --- zoom API (100%..400% ±50%) ---
    def zoom(self) -> float:
        return self._zoom

    def setZoom(self, v: float) -> bool:
        nv = max(ZOOM_MIN, min(ZOOM_MAX, float(v)))
        # 0.5刻みにスナップ（浮動誤差対策）
        nv = round(nv * 2) / 2.0
        nv = max(ZOOM_MIN, min(ZOOM_MAX, nv))
        if abs(nv - self._zoom) < 1e-9:
            return False
        self._zoom = nv
        self.zoomChanged.emit(self._zoom)
        self.update()
        return True

    def zoomIn(self) -> bool:
        return self.setZoom(self._zoom + ZOOM_STEP)

    def zoomOut(self) -> bool:
        return self.setZoom(self._zoom - ZOOM_STEP)

    def resetZoom(self) -> bool:
        return self.setZoom(1.0)

    def set_items(self, items: List[Tuple[Path, float]]):
        self._items = list(items)
        self._enforce_endpoints()
        self.update()

    def get_items(self) -> List[Tuple[Path, float]]:
        # リスト順（ファイルリスト番号順）を保持。タイムライン表示もリスト順。
        return list(self._items)

    def get_items_sorted(self) -> List[Tuple[Path, float]]:
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
        if len(self._items) == 1:
            # 単独時は P1@0（TposeはBVHで0に前置、タイムラインは P1 のみを 0 に）
            p, t = self._items[0]
            self._items[0] = (p, 0.0)
            return
        # リスト順を保持しつつ先頭 0 末尾 D を強制（Tposeは非表示、P1@0）
        new_items: List[Tuple[Path, float]] = []
        for i, (p, t) in enumerate(self._items):
            if i == 0:
                t = 0.0
            elif i == len(self._items) - 1:
                t = float(self._duration)
            else:
                t = max(0.0, min(float(self._duration), float(t)))
                if t <= 0.001:
                    t = 0.001
                if t >= self._duration - 0.001:
                    t = self._duration - 0.001
            new_items.append((p, float(t)))
        # リスト順で単調増加を強制（eps 0.05）
        for i in range(1, len(new_items)):
            prev_t = new_items[i - 1][1]
            cur_p, cur_t = new_items[i]
            if cur_t <= prev_t + 0.05 - 1e-9:
                if i == len(new_items) - 1:
                    pass
                else:
                    cur_t = prev_t + 0.05
                    cur_t = min(cur_t, float(self._duration) - 0.001)
                    new_items[i] = (cur_p, float(cur_t))
        # 先頭末尾を再強制
        if len(new_items) >= 2:
            new_items[0] = (new_items[0][0], 0.0)
            new_items[-1] = (new_items[-1][0], float(self._duration))
        self._items = new_items

    def _lane_x0(self) -> int:
        return PADDING_L + HEADER_W

    def set_zoom_width(self, vp_w: int) -> None:
        """ズーム倍率に応じた表示幅を適用する。

        上限 ZOOM_WIDTH_MAX を超える分は横スクロールで吸収し、
        ペイン全体の最小幅を押し上げない。

        Args:
            vp_w: スクロール領域の表示幅 (px)。
        """
        new_w = int(vp_w * self._zoom)
        if new_w < vp_w:
            new_w = vp_w
        if new_w > ZOOM_WIDTH_MAX:
            new_w = ZOOM_WIDTH_MAX
        self.setMinimumWidth(new_w)
        self.setMaximumWidth(new_w)

    def _lane_y(self, lane: int) -> int:
        return PADDING_TOP + TIMELINE_H + 6 + lane * LANE_H

    def _time_to_x(self, t: float, width: int) -> int:
        x0 = self._lane_x0()
        avail = width - x0 - PADDING_R - BLOCK_W
        if self._duration <= 1e-9 or avail <= 0:
            return x0
        frac = max(0.0, min(1.0, t / self._duration))
        return int(x0 + frac * avail)

    def _x_to_time(self, x: int, width: int) -> float:
        x0 = self._lane_x0()
        avail = width - x0 - PADDING_R - BLOCK_W
        if avail <= 0:
            return 0.0
        frac = (x - x0) / avail
        frac = max(0.0, min(1.0, frac))
        return frac * self._duration

    @staticmethod
    def _pan_bars(sa):
        """パン対象のスクロールバー対 (horizontal, vertical) を返す。"""
        if sa is None:
            return (None, None)
        try:
            return (sa.horizontalScrollBar(), sa.verticalScrollBar())
        except Exception:
            return (None, None)

    @staticmethod
    def _ev_point(event):
        """イベント位置をQPointで返す（pos()非推奨対応）。"""
        get = getattr(event, "position", None)
        if callable(get):
            try:
                return get().toPoint()
            except Exception:
                pass
        return event.pos()

    @staticmethod
    def _ev_global(event):
        """イベント大域位置をQPointで返す（globalPos()非推奨対応）。"""
        get = getattr(event, "globalPosition", None)
        if callable(get):
            try:
                return get().toPoint()
            except Exception:
                pass
        return event.globalPos()

    @staticmethod
    def _bar_can_scroll(bar) -> bool:
        """スクロールバーがスクロール可能かを返す。"""
        try:
            return bar is not None and bar.maximum() > 0
        except Exception:
            return False

    def _hit_test(self, pos: QPoint) -> int | None:
        w = self.width()
        items = self.get_items()
        if not items:
            return None
        for idx, (p, t) in enumerate(items):
            x = self._time_to_x(t, w)
            rect = QRect(x, self._lane_y(idx) + (LANE_H - BLOCK_H) // 2, BLOCK_W, BLOCK_H)
            if rect.contains(pos):
                return idx
            # ピン部分もヒット
            y_line = PADDING_TOP + TIMELINE_H // 2 + 4
            pin_rect = QRect(x - PIN_W, y_line, PIN_W * 2, self._lane_y(idx) - y_line)
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
        # レーン見出し分を空けた範囲に軸を引く
        x0 = self._lane_x0()
        painter.drawLine(x0, y_line, w - PADDING_R - BLOCK_W, y_line)

        # ticks（600秒まで対応）
        painter.setPen(QPen(_TICK, 1))
        if self._duration <= 10:
            step = 1.0
        elif self._duration <= 30:
            step = 5.0
        elif self._duration <= 120:
            step = 10.0
        elif self._duration <= 300:
            step = 30.0
        else:
            step = 60.0
        fm = QFontMetrics(self.font())
        t = 0.0
        while t <= self._duration + 1e-9:
            x = self._time_to_x(t, w)
            painter.drawLine(x, y_line - 6, x, y_line + 6)
            label = f"{t:.1f}s" if t != 0 else "0s"
            lw = fm.horizontalAdvance(label)
            painter.setPen(_TEXT)
            # 左端基準なのでラベルはxを中央寄せ
            painter.drawText(x - lw // 2, PADDING_TOP + TIMELINE_H + 2, label)
            painter.setPen(QPen(_TICK, 1))
            t += step
        if abs(t - step - self._duration) > 1e-6:
            x = self._time_to_x(self._duration, w)
            painter.drawLine(x, y_line - 6, x, y_line + 6)
            label = f"{self._duration:.1f}s"
            lw = fm.horizontalAdvance(label)
            painter.setPen(_TEXT)
            painter.drawText(x - lw // 2, PADDING_TOP + TIMELINE_H + 2, label)

        items = self.get_items()
        if not items:
            return
        # 必要高さを動的に反映（1レーン約44px、上限なし＝親スクロールに任せる）
        needed_h = PADDING_TOP + TIMELINE_H + 6 + len(items) * LANE_H + PADDING_BOTTOM
        if needed_h != self.minimumHeight():
            self.setMinimumHeight(max(110, needed_h))
        lanes_bottom = PADDING_TOP + TIMELINE_H + 6 + len(items) * LANE_H

        # 重なり帯（黄）→分割線（赤破線）の順に描画
        for m in self.split_markers():
            if self._overlap_sec > 0:
                bx0 = self._time_to_x(max(0.0, m - self._overlap_sec), w)
                bx1 = self._time_to_x(m, w)
                painter.fillRect(QRect(bx0, y_line - 6, max(1, bx1 - bx0), lanes_bottom - (y_line - 6)), _OVERLAP_BAND)
            mx = self._time_to_x(m, w)
            painter.setPen(QPen(_SPLIT_LINE, 1, Qt.DashLine))
            painter.drawLine(mx, y_line - 6, mx, lanes_bottom)
            painter.setPen(QPen(_TICK, 1))

        for idx, (p, t) in enumerate(items):
            x = self._time_to_x(t, w)
            lane_y = self._lane_y(idx)
            rect_x = x
            rect_y = lane_y + (LANE_H - BLOCK_H) // 2
            # レーン見出し＝LLSDファイル名（A/B/C表記なし、中間省略）
            painter.setPen(_LANE_TEXT)
            hfont = QFont(self.font())
            hfont.setPointSize(8)
            painter.setFont(hfont)
            hfm = QFontMetrics(hfont)
            head_label = elide_middle_label("", p.stem, HEADER_W - 12, hfm.horizontalAdvance)
            painter.drawText(PADDING_L + 4, lane_y + (LANE_H + hfm.ascent() - hfm.descent()) // 2, head_label)
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
            # 1行目: "#n 名前"（拡張子は一律非表示＋中間省略で末尾の識別数字を残す）
            prefix = f"#{num} "
            # 残り幅で省略
            avail_w = BLOCK_W - 8
            full_label = elide_middle_label(prefix, p.stem, avail_w, fm2.horizontalAdvance)
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

    def _get_scroll_area(self):
        p = self.parent()
        while p is not None:
            try:
                from PySide6.QtWidgets import QScrollArea
                if isinstance(p, QScrollArea):
                    return p
            except Exception:
                pass
            p = p.parent() if hasattr(p, "parent") else None
        return None

    def _auto_scroll_for_drag(self, widget_pos):
        sa = self._get_scroll_area()
        if sa is None:
            return
        try:
            vp_pos = self.mapTo(sa.viewport(), widget_pos)
            vw = sa.viewport().width()
            margin = 30
            step = 18
            hs = sa.horizontalScrollBar()
            if vp_pos.x() < margin:
                hs.setValue(max(hs.minimum(), hs.value() - step))
            elif vp_pos.x() > vw - margin:
                hs.setValue(min(hs.maximum(), hs.value() + step))
        except Exception:
            pass

    def wheelEvent(self, event):
        # ホイールは常にズーム（Ctrl不要、横スクロールはドラッグで代替）
        delta = event.angleDelta().y()
        # 横ホイールが来た場合も縦に読み替え
        if delta == 0:
            delta = event.angleDelta().x()
        if delta > 0:
            self.zoomRequest.emit(1)
        elif delta < 0:
            self.zoomRequest.emit(-1)
        event.accept()
        return

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            idx = self._hit_test(self._ev_point(event))
            if idx is not None:
                if len(self.get_items()) >= 2 and (idx == 0 or idx == len(self.get_items()) - 1):
                    return
                self._drag_idx = idx
                w = self.width()
                p, t = self.get_items()[idx]
                x = self._time_to_x(t, w)
                self._drag_offset = self._ev_point(event).x() - x
                self.setCursor(Qt.ClosedHandCursor)
                return
            # 空所 左ドラッグでパン開始（縦横スクロールバーを連動）
            sa = self._get_scroll_area()
            hs, vs = self._pan_bars(sa)
            if self._bar_can_scroll(hs) or self._bar_can_scroll(vs):
                self._panning = True
                # global座標で追従（widgetがスクロールしてもズレない）
                self._pan_start_x = self._ev_global(event).x()
                self._pan_start_y = self._ev_global(event).y()
                self._pan_start_scroll = hs.value() if hs is not None else 0
                self._pan_start_vscroll = vs.value() if vs is not None else 0
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return

    def mouseMoveEvent(self, event):
        # パン中は最優先（1:1追従、加速なし。縦横とも連動）
        if self._panning and event.buttons() & Qt.LeftButton:
            gp = self._ev_global(event)
            dx = self._pan_start_x - gp.x()
            dy = self._pan_start_y - gp.y()
            sa = self._get_scroll_area()
            hs, vs = self._pan_bars(sa)
            if hs is not None:
                hs.setValue(max(hs.minimum(), min(hs.maximum(), self._pan_start_scroll + dx)))
            if vs is not None:
                vs.setValue(max(vs.minimum(), min(vs.maximum(), self._pan_start_vscroll + dy)))
            event.accept()
            return
        w = self.width()
        h_idx = self._hit_test(self._ev_point(event))
        if h_idx != self._hover_idx:
            self._hover_idx = h_idx
            # ブロック別ツールチップ: フル名＋時刻。空所では既定文言に戻す
            if h_idx is not None:
                try:
                    items_tip = self.get_items()
                    pp, tt = items_tip[h_idx]
                    nn = self._resolve_number(pp, h_idx, items_tip)
                    self.setToolTip(f"#{nn} {pp.name}\n{tt:.2f}s")
                except Exception:
                    pass
            else:
                self.setToolTip(self._default_tooltip)
            self.update()
        if self._drag_idx is not None and event.buttons() & Qt.LeftButton:
            new_x = self._ev_point(event).x() - self._drag_offset
            new_t = self._x_to_time(new_x, w)
            items = self.get_items()  # リスト順
            eps = 0.05
            if self._drag_idx > 0:
                prev_t = items[self._drag_idx - 1][1]
                new_t = max(new_t, prev_t + eps)
            if self._drag_idx < len(items) - 1:
                next_t = items[self._drag_idx + 1][1]
                new_t = min(new_t, next_t - eps)
            new_t = max(0.0, min(self._duration, new_t))
            # リスト順を保持、ソートしない（順番はファイルリスト側で制御）
            p, _ = items[self._drag_idx]
            self._items[self._drag_idx] = (p, float(new_t))
            self.timeChanged.emit()
            self.update()
            self._auto_scroll_for_drag(self._ev_point(event))
        else:
            if self._drag_idx is None and h_idx is not None:
                if len(self.get_items()) >= 2 and (h_idx == 0 or h_idx == len(self.get_items()) - 1):
                    self.setCursor(Qt.ArrowCursor)
                else:
                    self.setCursor(Qt.OpenHandCursor)
            elif self._drag_idx is None:
                if self._panning:
                    self.setCursor(Qt.ClosedHandCursor)
                else:
                    # 空所はパン可能を示す（縦横どちらかスクロール可能な時のみ）
                    sa = self._get_scroll_area()
                    hs, vs = self._pan_bars(sa)
                    if self._bar_can_scroll(hs) or self._bar_can_scroll(vs):
                        self.setCursor(Qt.OpenHandCursor)
                    else:
                        self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        if self._drag_idx is not None:
            self._drag_idx = None
            self.setCursor(Qt.ArrowCursor)
            self._enforce_endpoints()
            self.timeChanged.emit()
            self.update()

    def mouseDoubleClickEvent(self, event):
        idx = self._hit_test(self._ev_point(event))
        if idx is None:
            return
        items = self.get_items()  # リスト順
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
            self._items[idx] = (p, float(val))
            self._enforce_endpoints()
            self.timeChanged.emit()
            self.update()

    def leaveEvent(self, event):
        self._hover_idx = None
        self.setToolTip(self._default_tooltip)
        self.update()
        if not self._panning:
            self.setCursor(Qt.ArrowCursor)
