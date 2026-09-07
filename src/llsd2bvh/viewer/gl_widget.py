# -*- coding: utf-8 -*-
"""3D 棒人間ビュー（QWidget + QPainter 透視投影）。OpenGL不要で3D回転/ズーム/パンを実現。"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

try:
    from PySide6.QtWidgets import QWidget
    from PySide6.QtGui import QPainter, QPen, QColor, QBrush
    from PySide6.QtCore import Qt, QPoint, QSize
except ImportError:
    QWidget = object  # type: ignore

# 型エイリアス
Vec3 = Tuple[float, float, float]
Bone = Tuple[Vec3, Vec3]


class StickFigureWidget(QWidget):
    """簡易3D棒人間ビュー。

    透視投影 + 軌道カメラ（yaw/pitch/distance）で QPainter 描画。
    左ドラッグ回転、右ドラッグパン、ホイールズーム。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        # データ
        self._bones: List[Bone] = []
        self._positions: Dict[str, Vec3] = {}
        # カメラ（Y up に変換後のビュー座標系）
        self._yaw = 20.0  # deg, Y軸周り
        self._pitch = -12.0  # deg, X軸周り（上から見下ろし気味）
        self._distance = 2.0  # モデル中心からの距離（m単位想定、前より手前）
        self._center: Vec3 = (0.0, 0.9, 0.0)  # モデル中央（自動算出で更新）
        self._pan_x = 0.0
        self._pan_y = 0.0
        # インタラクション
        self._last_pos: QPoint | None = None
        self._drag_button: int | None = None
        # スタイル
        self.setStyleSheet("background: #1a1a1a;")
        # フォーカスポリシー
        self.setFocusPolicy(Qt.StrongFocus)

    @staticmethod
    def _map_bvh_to_viewer(p: Vec3) -> Vec3:
        """BVH座標(Z-up, Y=左右, X=前)を Y-up ビュー座標へ変換。

        SL avatar_skeleton: X=前, Y=左右(左+), Z=上。
        Viewer: Y=上, X=左右, Z=奥行。
        変換: viewer_x = bvh_y, viewer_y = bvh_z, viewer_z = -bvh_x
        で足が下・頭が上、左右が画面左右に対応。
        """
        x, y, z = p
        return (y, z, -x)

    # ---- データ投入 ----
    def set_frame(self, bones: List[Bone], positions: Dict[str, Vec3]):
        # BVH(Y-upではない)を視覚用に変換
        mapped_positions: Dict[str, Vec3] = {k: self._map_bvh_to_viewer(v) for k, v in positions.items()}
        mapped_bones: List[Bone] = [(self._map_bvh_to_viewer(a), self._map_bvh_to_viewer(b)) for a, b in bones]
        # 単位正規化: inch出力（39倍）なら meter相当へ縮小して表示を統一
        try:
            # spanや絶対値が大きい場合は inch とみなす
            all_vals = list(mapped_positions.values()) + [p for bone in mapped_bones for p in bone]
            if all_vals:
                max_abs = max(max(abs(c) for c in p) for p in all_vals)
                xs = [p[0] for p in mapped_positions.values()]
                ys = [p[1] for p in mapped_positions.values()]
                zs = [p[2] for p in mapped_positions.values()]
                span_est = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
                if max_abs > 10.0 or span_est > 10.0:
                    scale = 1.0 / 39.37008
                    mapped_positions = {k: (v[0]*scale, v[1]*scale, v[2]*scale) for k, v in mapped_positions.items()}
                    mapped_bones = [((a[0]*scale, a[1]*scale, a[2]*scale), (b[0]*scale, b[1]*scale, b[2]*scale)) for a, b in mapped_bones]
        except Exception:
            pass
        self._bones = mapped_bones
        self._positions = mapped_positions
        # 中心を再計算（全関節の平均、高さは重心付近）
        if mapped_positions:
            xs = [p[0] for p in mapped_positions.values()]
            ys = [p[1] for p in mapped_positions.values()]
            zs = [p[2] for p in mapped_positions.values()]
            # 中心は全体のバウンディング中心だが、高さは pelvis付近を優先
            cx = (min(xs) + max(xs)) * 0.5
            cy = (min(ys) + max(ys)) * 0.5
            cz = (min(zs) + max(zs)) * 0.5
            # mPelvisがあればその高さを基準に少し補正
            pelvis_y = mapped_positions.get("mPelvis", (0, cy, 0))[1]
            # 中心Yは pelvis_y と全体中心の中間
            cy = (cy + pelvis_y) * 0.5
            self._center = (cx, cy, cz)
            # 距離をバウンディングサイズから自動（より手前に）
            span = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs), 1.0)
            # 理想距離: 以前 span*1.8 で遠すぎたため 1.2 に縮小
            ideal = max(0.9, span * 1.2)
            # より広いズーム範囲に対応（近くまで寄れる）
            self._distance = max(0.35, min(8.0, ideal))
        self.update()

    def set_bones(self, bones: List[Bone]):
        self._bones = list(bones)
        self.update()

    def reset_view(self, yaw: float | None = None, pitch: float | None = None):
        if yaw is not None:
            self._yaw = yaw
        else:
            self._yaw = 20.0
        if pitch is not None:
            self._pitch = pitch
        else:
            self._pitch = -12.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

    # ---- 投影 ----
    def _rotate(self, p: Vec3) -> Vec3:
        x, y, z = p
        # Yaw (Y軸)
        yaw = math.radians(self._yaw)
        cy = math.cos(yaw); sy = math.sin(yaw)
        x1 = x * cy + z * sy
        z1 = -x * sy + z * cy
        y1 = y
        # Pitch (X軸)
        pitch = math.radians(self._pitch)
        cp = math.cos(pitch); sp = math.sin(pitch)
        y2 = y1 * cp - z1 * sp
        z2 = y1 * sp + z1 * cp
        x2 = x1
        return (x2, y2, z2)

    def _project(self, world: Vec3) -> Tuple[float, float, bool]:
        # 中心からの相対
        cx, cy, cz = self._center
        x = world[0] - cx
        y = world[1] - cy
        z = world[2] - cz
        # 回転
        rx, ry, rz = self._rotate((x, y, z))
        # カメラ距離分だけ奥へ（視点は +Z方向から見る）
        rz -= self._distance
        # クリップ（カメラより前にあるもののみ）
        if rz >= -0.05:
            return (0, 0, False)
        # 透視投影
        w = self.width()
        h = self.height()
        # focal: 視野角50deg相当
        fov = math.radians(50.0)
        # focal長を画面サイズに比例
        focal = (min(w, h) * 0.5) / math.tan(fov * 0.5)
        # さらにズーム感を distance に反比例（distance小=拡大）
        # focal は固定なので、距離が近いほど大きく見えるのは自然（rzが浅くなるため）
        scale = focal / (-rz)
        sx = w * 0.5 + rx * scale + self._pan_x
        sy = h * 0.5 - ry * scale + self._pan_y
        return (sx, sy, True)

    # ---- 描画 ----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = self.width(); h = self.height()
        # 背景
        painter.fillRect(0, 0, w, h, QColor("#1a1a1a"))
        if not self._bones:
            # ガイドテキスト
            painter.setPen(QColor("#888"))
            painter.drawText(self.rect(), Qt.AlignCenter, "BVHを読み込んでください\n(ファイル → 開く)")
            return

        # グリッド（床）
        # 床Yは最低Yより少し下
        try:
            min_y = min(p[1] for p in self._positions.values()) if self._positions else 0.0
        except Exception:
            min_y = 0.0
        floor_y = min_y - 0.02
        # XZグリッド: 中心周辺 ±2m、0.25m刻み
        grid_pen_minor = QPen(QColor("#2a2a2a"), 1)
        grid_pen_major = QPen(QColor("#333333"), 1)
        grid_pen_axis = QPen(QColor("#444444"), 1)
        cx, _, cz = self._center
        # グリッド線をワールドで生成して投影
        # X方向線（Z一定）とZ方向線（X一定）
        grid_range = 2.0
        step = 0.25
        # draw minor
        for style, pen in [(step, grid_pen_minor), (1.0, grid_pen_major)]:
            painter.setPen(pen)
            # X lines
            v = -grid_range
            while v <= grid_range + 1e-6:
                # majorのみ描く場合は stepの倍数だが minorと重複しないよう、majorは別ループでもOK
                if style == 1.0 and abs(v % 1.0) > 1e-6:
                    v += style
                    continue
                if style == step and abs(v % 1.0) < 1e-6:
                    # majorの位置は minorではスキップ（majorで描く）
                    v += style
                    continue
                p1 = (cx + v, floor_y, cz - grid_range)
                p2 = (cx + v, floor_y, cz + grid_range)
                sx1, sy1, vis1 = self._project(p1)
                sx2, sy2, vis2 = self._project(p2)
                if vis1 and vis2:
                    painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))
                v += style
            # Z lines
            v = -grid_range
            while v <= grid_range + 1e-6:
                if style == 1.0 and abs(v % 1.0) > 1e-6:
                    v += style
                    continue
                if style == step and abs(v % 1.0) < 1e-6:
                    v += style
                    continue
                p1 = (cx - grid_range, floor_y, cz + v)
                p2 = (cx + grid_range, floor_y, cz + v)
                sx1, sy1, vis1 = self._project(p1)
                sx2, sy2, vis2 = self._project(p2)
                if vis1 and vis2:
                    painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))
                v += style
        # 軸強調（中心線）
        painter.setPen(grid_pen_axis)
        for axis in ["x", "z"]:
            if axis == "x":
                p1 = (cx - grid_range, floor_y + 0.001, cz)
                p2 = (cx + grid_range, floor_y + 0.001, cz)
            else:
                p1 = (cx, floor_y + 0.001, cz - grid_range)
                p2 = (cx, floor_y + 0.001, cz + grid_range)
            sx1, sy1, vis1 = self._project(p1)
            sx2, sy2, vis2 = self._project(p2)
            if vis1 and vis2:
                painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))

        # 骨線
        bone_pen = QPen(QColor("#6ec1ff"), 2.2)
        bone_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bone_pen)
        for p1, p2 in self._bones:
            sx1, sy1, v1 = self._project(p1)
            sx2, sy2, v2 = self._project(p2)
            if v1 and v2:
                painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))

        # 関節点
        joint_brush = QBrush(QColor("#ffcc55"))
        joint_pen = QPen(QColor("#1a1a1a"), 1)
        painter.setBrush(joint_brush)
        painter.setPen(joint_pen)
        # 重要関節を少し大きく
        important = {"mPelvis", "mTorso", "mChest", "mHead", "mShoulderLeft", "mShoulderRight", "mHipLeft", "mHipRight"}
        for name, pos in self._positions.items():
            sx, sy, vis = self._project(pos)
            if not vis:
                continue
            r = 4.5 if name in important else 3.0
            # EndSiteは小さく
            if name.endswith("_EndSite"):
                r = 2.0
                painter.setBrush(QBrush(QColor("#88aacc")))
            else:
                painter.setBrush(joint_brush)
            painter.drawEllipse(int(sx - r), int(sy - r), int(r*2), int(r*2))

        # 中心点マーカー（デバッグ用に薄く）
        # painter.setPen(QPen(QColor("#ff5555"), 1, Qt.DashLine))
        # sx, sy, vis = self._project(self._center)
        # if vis:
        #     painter.drawEllipse(int(sx-3), int(sy-3), 6, 6)

        # 情報オーバーレイ（左上）
        painter.setPen(QColor("#aaaaaa"))
        painter.drawText(8, 16, f"yaw {self._yaw:.0f}°  pitch {self._pitch:.0f}°  dist {self._distance:.2f}")
        painter.drawText(8, h - 8, "左ドラッグ:回転  右ドラッグ:パン  ホイール:ズーム")

    # ---- インタラクション ----
    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            self._last_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self._drag_button = event.button()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._last_pos is None or self._drag_button is None:
            return
        cur = event.position().toPoint() if hasattr(event, "position") else event.pos()
        dx = cur.x() - self._last_pos.x()
        dy = cur.y() - self._last_pos.y()
        if self._drag_button == Qt.LeftButton:
            self._yaw += dx * 0.45
            self._pitch += dy * 0.45
            # クランプ
            self._pitch = max(-85.0, min(85.0, self._pitch))
            self.update()
        elif self._drag_button == Qt.RightButton:
            self._pan_x += dx
            self._pan_y += dy
            self.update()
        self._last_pos = cur

    def mouseReleaseEvent(self, event):
        self._last_pos = None
        self._drag_button = None
        self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
        # ズーム: distanceをスケール（より広い範囲・大きく変化）
        factor = 1.0 - delta * 0.0012  # 120 -> 0.856 / 1.144
        factor = max(0.75, min(1.35, factor))
        self._distance *= factor
        self._distance = max(0.18, min(12.0, self._distance))
        self.update()
        event.accept()

    def sizeHint(self) -> QSize:
        return QSize(640, 480)
