# -*- coding: utf-8 -*-
"""BVHビューアウィンドウ（3D棒人間 + 再生）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QFileDialog, QSlider, QCheckBox, QComboBox, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QSettings

from .bvh_parser import parse_bvh, BvhData
from .fk import compute_frame_positions
from .gl_widget import StickFigureWidget
from ..i18n import tr

class BvhViewerWindow(QMainWindow):
    def __init__(self, initial_path: str | Path | None = None, lang: str = "ja", parent=None):
        super().__init__(parent)
        self.lang = lang if lang in ("ja", "en") else "ja"
        self.settings = QSettings("TAIFROG", "LLSD2BVH")
        self.bvh: BvhData | None = None
        self._path: Path | None = None
        self._frame_idx = 0
        self._is_playing = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._speed = 1.0
        self.setWindowTitle("BVH Viewer - Stick Figure")
        self.resize(900, 640)
        self._build_ui()
        self.retranslateUi()
        if initial_path and Path(initial_path).exists():
            self.load_bvh(initial_path)
        self.setAcceptDrops(True)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ファイル行
        file_row = QHBoxLayout()
        self.lbl_file = QLabel()
        file_row.addWidget(self.lbl_file)
        self.edit_path = QLineEdit()
        self.edit_path.setReadOnly(True)
        self.edit_path.setPlaceholderText("BVHファイルを選択...")
        file_row.addWidget(self.edit_path, stretch=1)
        self.btn_open = QPushButton()
        file_row.addWidget(self.btn_open)
        root.addLayout(file_row)

        # 3Dビュー
        self.viewer = StickFigureWidget()
        root.addWidget(self.viewer, stretch=1)

        # 情報行
        info_row = QHBoxLayout()
        self.lbl_info = QLabel("No BVH loaded")
        self.lbl_info.setStyleSheet("color: #aaa; font-size: 11px;")
        info_row.addWidget(self.lbl_info, stretch=1)
        self.lbl_frame = QLabel("- / -")
        self.lbl_frame.setStyleSheet("color: #fff; font-weight: bold;")
        info_row.addWidget(self.lbl_frame)
        root.addLayout(info_row)

        # スライダー
        slider_row = QHBoxLayout()
        self.lbl_slider_min = QLabel("0")
        self.lbl_slider_min.setStyleSheet("color: #777;")
        slider_row.addWidget(self.lbl_slider_min)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self._on_slider)
        slider_row.addWidget(self.slider, stretch=1)
        self.lbl_slider_max = QLabel("0")
        self.lbl_slider_max.setStyleSheet("color: #777;")
        slider_row.addWidget(self.lbl_slider_max)
        root.addLayout(slider_row)

        # 再生コントロール
        ctrl = QHBoxLayout()
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedWidth(36)
        self.btn_prev.clicked.connect(self._on_prev)
        ctrl.addWidget(self.btn_prev)
        self.btn_play = QPushButton("▶ 再生")
        self.btn_play.setFixedWidth(84)
        self.btn_play.clicked.connect(self._on_play)
        ctrl.addWidget(self.btn_play)
        self.chk_loop = QCheckBox("ループ")
        self.chk_loop.setChecked(True)
        self.chk_loop.setToolTip("ONで末尾まで再生後に先頭へ戻ってループ")
        ctrl.addWidget(self.chk_loop)
        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedWidth(36)
        self.btn_next.clicked.connect(self._on_next)
        ctrl.addWidget(self.btn_next)
        ctrl.addSpacing(8)
        self.lbl_speed = QLabel("速度:")
        ctrl.addWidget(self.lbl_speed)
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.25x", "0.5x", "1x", "2x"])
        self.combo_speed.setCurrentIndex(2)
        self.combo_speed.currentIndexChanged.connect(self._on_speed)
        ctrl.addWidget(self.combo_speed)
        ctrl.addSpacing(8)
        self.chk_skip = QCheckBox("Tpose先頭をスキップ")
        self.chk_skip.setChecked(True)
        self.chk_skip.toggled.connect(self._on_skip_toggle)
        ctrl.addWidget(self.chk_skip)
        ctrl.addSpacing(8)
        self.lbl_rot = QLabel("回転:")
        ctrl.addWidget(self.lbl_rot)
        self.combo_rot = QComboBox()
        self.combo_rot.addItems(["SL互換", "BVH標準"])
        self.combo_rot.setCurrentIndex(0)
        self.combo_rot.setToolTip("SL互換: Y値→Z軸で直立 (本ツール出力用) / BVH標準: ラベル通り")
        self.combo_rot.currentIndexChanged.connect(self._on_rot_changed)
        ctrl.addWidget(self.combo_rot)
        ctrl.addStretch()
        # 視点
        self.btn_front = QPushButton("正面")
        self.btn_front.clicked.connect(lambda: self.viewer.reset_view(yaw=180, pitch=0))
        ctrl.addWidget(self.btn_front)
        self.btn_side = QPushButton("側面")
        self.btn_side.clicked.connect(lambda: self.viewer.reset_view(yaw=90, pitch=0))
        ctrl.addWidget(self.btn_side)
        self.btn_top = QPushButton("上面")
        self.btn_top.clicked.connect(lambda: self.viewer.reset_view(yaw=0, pitch=85))
        ctrl.addWidget(self.btn_top)
        self.btn_reset_view = QPushButton("リセット")
        self.btn_reset_view.clicked.connect(lambda: self.viewer.reset_view())
        ctrl.addWidget(self.btn_reset_view)
        root.addLayout(ctrl)

        # 信号
        self.btn_open.clicked.connect(self.on_open)

    def retranslateUi(self):
        # 簡易日英切替（本ウィンドウ単独でもGUI設定を尊重）
        try:
            lang = self.settings.value("lang", "ja")
            if lang in ("ja", "en"):
                self.lang = lang
        except Exception:
            pass
        self.lbl_file.setText(tr("viewer_file", self.lang) if "viewer_file" in self._tr_keys() else ("BVH:" if self.lang=="en" else "BVH:"))
        self.btn_open.setText(tr("btn_browse", self.lang))
        self.lbl_speed.setText("Speed:" if self.lang=="en" else "速度:")
        self.chk_skip.setText("Skip Tpose" if self.lang=="en" else "Tpose先頭をスキップ")
        if hasattr(self, "chk_loop"):
            self.chk_loop.setText("Loop" if self.lang=="en" else "ループ")
        self.btn_front.setText("Front" if self.lang=="en" else "正面")
        self.btn_side.setText("Side" if self.lang=="en" else "側面")
        self.btn_top.setText("Top" if self.lang=="en" else "上面")
        self.btn_reset_view.setText("Reset" if self.lang=="en" else "リセット")
        # play label
        self._update_play_label()

    def _tr_keys(self):
        try:
            from ..i18n import TRANSLATIONS
            return TRANSLATIONS.get(self.lang, {}).keys()
        except Exception:
            return []

    def _update_play_label(self):
        if self._is_playing:
            self.btn_play.setText("⏸ " + ("Pause" if self.lang=="en" else "停止"))
        else:
            self.btn_play.setText("▶ " + ("Play" if self.lang=="en" else "再生"))

    # ---- ファイル ----
    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "BVHを選択" if self.lang=="ja" else "Select BVH", "", "BVH (*.bvh);;All (*.*)")
        if path:
            self.load_bvh(path)

    def load_bvh(self, path: str | Path):
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "Error", f"File not found:\n{p}")
            return
        try:
            bvh = parse_bvh(p)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"BVH parse failed:\n{e}")
            return
        self.bvh = bvh
        self._path = p
        self.edit_path.setText(str(p))
        self.setWindowTitle(f"BVH Viewer - {p.name}")
        # スライダー
        self.slider.setEnabled(True)
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(0, bvh.num_frames - 1))
        self.lbl_slider_min.setText("0")
        self.lbl_slider_max.setText(str(bvh.num_frames - 1))
        # 情報
        ch = bvh.num_channels
        self.lbl_info.setText(f"{p.name}  Frames:{bvh.num_frames}  FrameTime:{bvh.frame_time:.5f}s  Channels:{ch}  Joints:{len(bvh.joints)}")
        # 初期フレーム: skipなら1
        start = 1 if self.chk_skip.isChecked() and bvh.num_frames > 1 else 0
        self._frame_idx = start
        self.slider.setValue(start)
        self._show_frame(start)
        self._update_controls()
        # タイマー速度
        self._on_speed()

    def _rotation_mode(self) -> str:
        return "sl_compat" if self.combo_rot.currentIndex() == 0 else "standard"

    def _show_frame(self, idx: int):
        if self.bvh is None:
            return
        idx = max(0, min(idx, self.bvh.num_frames - 1))
        self._frame_idx = idx
        try:
            positions, bones = compute_frame_positions(self.bvh, idx, rotation_mode=self._rotation_mode())
        except Exception as e:
            print(f"FK failed frame {idx}: {e}")
            return
        self.viewer.set_frame(bones, positions)
        # フレーム表示
        t = idx * self.bvh.frame_time
        total_t = (self.bvh.num_frames - 1) * self.bvh.frame_time
        skip_note = " (skip Tpose)" if self.chk_skip.isChecked() and idx == 0 and self.bvh.num_frames > 1 else ""
        if self.chk_skip.isChecked() and self.bvh.num_frames > 1:
            # 表示は skip込みで 1-index?  keep raw
            pass
        self.lbl_frame.setText(f"{idx}/{self.bvh.num_frames-1}  t={t:.3f}s / {total_t:.3f}s  dt={self.bvh.frame_time:.4f}s{skip_note}")

    def _update_controls(self):
        has = self.bvh is not None and self.bvh.num_frames > 0
        self.btn_play.setEnabled(has and self.bvh.num_frames > 1)
        self.btn_prev.setEnabled(has)
        self.btn_next.setEnabled(has)
        self.slider.setEnabled(has)

    # ---- 操作 ----
    def _on_slider(self, val: int):
        self._show_frame(val)

    def _on_prev(self):
        if self.bvh is None:
            return
        nxt = self._frame_idx - 1
        if self.chk_skip.isChecked():
            nxt = max(1, nxt)
        else:
            nxt = max(0, nxt)
        self.slider.setValue(nxt)

    def _on_next(self):
        if self.bvh is None:
            return
        nxt = self._frame_idx + 1
        nxt = min(self.bvh.num_frames - 1, nxt)
        self.slider.setValue(nxt)

    def _on_play(self):
        if self.bvh is None or self.bvh.num_frames <= 1:
            return
        self._is_playing = not self._is_playing
        self._update_play_label()
        if self._is_playing:
            # 末尾なら先頭（skip考慮）へ
            if self._frame_idx >= self.bvh.num_frames - 1:
                start = 1 if self.chk_skip.isChecked() and self.bvh.num_frames > 1 else 0
                self.slider.setValue(start)
            interval = max(10, int(self.bvh.frame_time * 1000 / self._speed))
            self._timer.start(interval)
        else:
            self._timer.stop()

    def _on_timer(self):
        if self.bvh is None:
            self._timer.stop()
            return
        nxt = self._frame_idx + 1
        if nxt >= self.bvh.num_frames:
            if self.chk_loop.isChecked():
                start = 1 if self.chk_skip.isChecked() and self.bvh.num_frames > 1 else 0
                self.slider.setValue(start)
                return
            self._timer.stop()
            self._is_playing = False
            self._update_play_label()
            return
        self.slider.setValue(nxt)

    def _on_speed(self):
        txt = self.combo_speed.currentText()
        try:
            self._speed = float(txt.replace("x", ""))
        except Exception:
            self._speed = 1.0
        if self._is_playing and self.bvh:
            interval = max(10, int(self.bvh.frame_time * 1000 / self._speed))
            self._timer.start(interval)

    def _on_skip_toggle(self, checked: bool):
        # 現在表示が0でskip有効になったら1へ
        if self.bvh and checked and self._frame_idx == 0 and self.bvh.num_frames > 1:
            self.slider.setValue(1)
        self._show_frame(self.slider.value())

    def _on_rot_changed(self, _idx: int):
        # 回転モード切替で再描画
        if self.bvh:
            self._show_frame(self._frame_idx)

    # ---- DnD ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for u in urls:
                p = Path(u.toLocalFile())
                if p.suffix.lower() == ".bvh":
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for u in urls:
            p = Path(u.toLocalFile())
            if p.suffix.lower() == ".bvh" and p.exists():
                self.load_bvh(p)
                event.acceptProposedAction()
                return

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


def main(argv=None):
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv if argv is None else [sys.argv[0]] + (argv or []))
    initial = None
    if argv:
        # 引数がBVHパスなら初期読込
        for a in argv:
            if Path(a).suffix.lower() == ".bvh" and Path(a).exists():
                initial = a
                break
        if initial is None and len(argv) == 1 and Path(argv[0]).suffix.lower() == ".bvh":
            initial = argv[0]
    w = BvhViewerWindow(initial_path=initial)
    w.show()
    return app.exec()
