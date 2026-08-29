# -*- coding: utf-8 -*-
"""GUI版 LLSD→BVH 変換ツール (PySide6)。

- 入力最大20件、ドラッグ＆ドロップ＋順序入替可
- タイムライン（横）で各ポーズの実行タイミングを指定、durationからFrameTimeを算出
- 変換核は bvh_writer/euler_math を共用
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
        QComboBox, QDoubleSpinBox, QCheckBox, QFileDialog, QMessageBox,
        QProgressBar, QTextEdit
    )
    from PySide6.QtCore import Qt, QMimeData, QUrl
except ImportError as e:
    print("PySide6 is required for GUI: pip install PySide6", file=sys.stderr)
    raise

from .llsd_parser import parse_llsd_xml
from .skeleton import load_skeleton, filter_skeleton
from .bvh_writer import write_bvh_frames
from .timeline import compute_timeline_frames, MIN_FRAME_TIME, MAX_DURATION
from .widgets.timeline_view import TimelineView


MAX_FILES = 20


class FileListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            paths = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
            # filter xml
            xmls = [str(p) for p in paths if p.suffix.lower() == ".xml" and p.exists()]
            # add via parent window method if available
            win = self.window()
            if hasattr(win, "add_files"):
                win.add_files(xmls)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
            # after internal move, parent can verify count
            # no limit check needed for internal reorder


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLSD → BVH 変換 (GUI)")
        self.resize(860, 760)
        self._build_ui()
        self._update_timeline_state()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Input list
        layout.addWidget(QLabel("入力LLSDファイル（最大20件、ドラッグ＆ドロップ可）:"))
        self.list_widget = FileListWidget()
        layout.addWidget(self.list_widget, stretch=2)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("追加…")
        self.btn_remove = QPushButton("削除")
        self.btn_up = QPushButton("↑")
        self.btn_down = QPushButton("↓")
        self.btn_clear = QPushButton("クリア")
        for b in [self.btn_add, self.btn_remove, self.btn_up, self.btn_down, self.btn_clear]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Timeline
        layout.addWidget(QLabel("タイムライン（1件は無効、2件以上で有効。ドラッグで移動、ダブルクリックで時刻入力。先頭0s/末尾は固定）:"))
        self.timeline_view = TimelineView()
        layout.addWidget(self.timeline_view)
        # duration row
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("アニメーション時間:"))
        self.spin_duration = QDoubleSpinBox()
        self.spin_duration.setDecimals(2)
        self.spin_duration.setSingleStep(0.5)
        self.spin_duration.setRange(0.1, MAX_DURATION)
        self.spin_duration.setValue(5.0)
        self.spin_duration.setSuffix(" 秒")
        dur_row.addWidget(self.spin_duration)
        dur_row.addWidget(QLabel(f"（最大{int(MAX_DURATION)}秒）"))
        dur_row.addSpacing(12)
        self.label_computed = QLabel("算出: -")
        self.label_computed.setStyleSheet("color: #333; font-weight: bold;")
        dur_row.addWidget(self.label_computed)
        dur_row.addStretch()
        layout.addLayout(dur_row)

        # Output
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("出力BVH:"))
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("未指定なら入力先頭と同名.bvh（複数時は連結1ファイル）")
        self.btn_browse_out = QPushButton("参照…")
        out_row.addWidget(self.edit_output, stretch=1)
        out_row.addWidget(self.btn_browse_out)
        layout.addLayout(out_row)

        # Options grid
        opt_row1 = QHBoxLayout()
        opt_row1.addWidget(QLabel("Skeleton:"))
        self.edit_skeleton = QLineEdit()
        self.edit_skeleton.setPlaceholderText("未指定なら同梱 avatar_skeleton.xml")
        self.btn_browse_skel = QPushButton("参照…")
        opt_row1.addWidget(self.edit_skeleton, stretch=1)
        opt_row1.addWidget(self.btn_browse_skel)
        layout.addLayout(opt_row1)

        opt_row2 = QHBoxLayout()
        opt_row2.addWidget(QLabel("Units:"))
        self.combo_units = QComboBox()
        self.combo_units.addItems(["自動", "meter", "inch"])
        opt_row2.addWidget(self.combo_units)
        opt_row2.addWidget(QLabel("SL互換:"))
        self.combo_sl = QComboBox()
        self.combo_sl.addItems(["自動", "2フレーム", "1フレーム"])
        opt_row2.addWidget(self.combo_sl)
        opt_row2.addWidget(QLabel("Frame Time:"))
        self.spin_frame = QDoubleSpinBox()
        self.spin_frame.setDecimals(7)
        self.spin_frame.setSingleStep(0.001)
        self.spin_frame.setRange(0.001, 1.0)
        self.spin_frame.setValue(0.0333333)
        opt_row2.addWidget(self.spin_frame)
        opt_row2.addWidget(QLabel("(1件時のみ手動、2件以上は自動算出)"))
        opt_row2.addStretch()
        layout.addLayout(opt_row2)

        opt_row3 = QHBoxLayout()
        self.chk_face = QCheckBox("顔を含める")
        self.chk_tail = QCheckBox("尻尾を含める")
        self.chk_no_hands = QCheckBox("手を除外")
        for c in [self.chk_face, self.chk_tail, self.chk_no_hands]:
            opt_row3.addWidget(c)
        opt_row3.addStretch()
        layout.addLayout(opt_row3)

        # Progress & log
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        layout.addWidget(self.log)

        # Convert / Close
        bottom = QHBoxLayout()
        bottom.addStretch()
        self.btn_convert = QPushButton("変換")
        self.btn_convert.setDefault(True)
        self.btn_close = QPushButton("閉じる")
        bottom.addWidget(self.btn_convert)
        bottom.addWidget(self.btn_close)
        layout.addLayout(bottom)

        # connections
        self.btn_add.clicked.connect(self.on_add)
        self.btn_remove.clicked.connect(self.on_remove)
        self.btn_up.clicked.connect(lambda: self.move_selected(-1))
        self.btn_down.clicked.connect(lambda: self.move_selected(1))
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_browse_out.clicked.connect(self.on_browse_out)
        self.btn_browse_skel.clicked.connect(self.on_browse_skel)
        self.btn_convert.clicked.connect(self.on_convert)
        self.btn_close.clicked.connect(self.close)
        self.spin_duration.valueChanged.connect(self._on_duration_changed)
        self.timeline_view.timeChanged.connect(self._on_timeline_changed)

    # helpers
    def log_msg(self, msg: str):
        self.log.append(msg)

    # --- timeline helpers ---
    def _update_timeline_state(self):
        count = self.list_widget.count()
        has_timeline = count >= 2
        self.timeline_view.setEnabled(has_timeline)
        self.spin_duration.setEnabled(has_timeline)
        # Frame Time: 1件のみ手動、2件以上は自動
        self.spin_frame.setEnabled(not has_timeline)
        if has_timeline:
            self._sync_timeline()
            self._update_computed_label()
        else:
            self.label_computed.setText("算出: -（1件のためタイムライン無効、Frame Timeを直接指定）")
            if count == 1:
                self.spin_frame.setEnabled(True)

    def _on_duration_changed(self, _val):
        new_dur = float(self.spin_duration.value())
        old_dur = float(self.timeline_view.duration())
        self.timeline_view.set_duration(new_dur)
        items = self.timeline_view.get_items()
        if items:
            # scale intermediate times proportionally to keep relative positions
            scaled = []
            for idx, (p, t) in enumerate(items):
                if idx == 0:
                    scaled.append((p, 0.0))
                elif idx == len(items) - 1:
                    scaled.append((p, new_dur))
                else:
                    if old_dur > 1e-9:
                        nt = t / old_dur * new_dur
                    else:
                        nt = t
                    scaled.append((p, float(nt)))
            self.timeline_view.set_items(scaled)
        self._update_computed_label()

    def _on_timeline_changed(self):
        self._update_computed_label()

    def _sync_timeline(self):
        """list_widget の内容を timeline_view に同期"""
        count = self.list_widget.count()
        if count < 2:
            if count == 0:
                self.timeline_view.set_items([])
            return
        dur = float(self.spin_duration.value())
        self.timeline_view.set_duration(dur)
        list_paths = [Path(self.list_widget.item(i).text()) for i in range(count)]
        existing = {str(p): t for p, t in self.timeline_view.get_items()}
        # 既存が全て新か、既存が均一かを判定
        existing_times = sorted(existing.values()) if existing else []
        is_uniform = False
        if len(existing_times) >= 2:
            gaps = [existing_times[i + 1] - existing_times[i] for i in range(len(existing_times) - 1)]
            if gaps and max(gaps) - min(gaps) <= 1e-4:
                is_uniform = True
        # 全て新規 or 既存が均一なら均一再配置、そうでなければ保持＋最大ギャップに挿入
        if not existing or is_uniform:
            # 均一再配置
            new_items: list[tuple[Path, float]] = []
            for i, p in enumerate(list_paths):
                t = (i * dur / (count - 1)) if count > 1 else 0.0
                new_items.append((p, float(t)))
            self.timeline_view.set_items(new_items)
            self._update_computed_label()
            return
        # 非均一保持: 既存は保持、新規は最大ギャップの中央へ
        new_items: list[tuple[Path, float]] = []
        for p in list_paths:
            key = str(p)
            if key in existing:
                new_items.append((p, existing[key]))
            else:
                assigned_times = []
                for pp, tt in new_items:
                    assigned_times.append(tt)
                for pp, tt in self.timeline_view.get_items():
                    if str(pp) in [str(x) for x in list_paths] and str(pp) not in [str(x[0]) for x in new_items]:
                        assigned_times.append(tt)
                assigned_times.sort()
                if len(assigned_times) < 1:
                    t_new = dur / 2
                elif len(assigned_times) == 1:
                    if assigned_times[0] < dur / 2:
                        t_new = (assigned_times[0] + dur) / 2
                    else:
                        t_new = assigned_times[0] / 2
                else:
                    max_gap = -1
                    gap_mid = dur / 2
                    for i in range(len(assigned_times) - 1):
                        gap = assigned_times[i + 1] - assigned_times[i]
                        if gap > max_gap:
                            max_gap = gap
                            gap_mid = (assigned_times[i] + assigned_times[i + 1]) / 2
                    # also check edges 0..first and last..D
                        edge0_gap = assigned_times[0] - 0.0
                        if edge0_gap > max_gap:
                            max_gap = edge0_gap
                            gap_mid = edge0_gap / 2
                        edge1_gap = dur - assigned_times[-1]
                        if edge1_gap > max_gap:
                            gap_mid = assigned_times[-1] + edge1_gap / 2
                        t_new = gap_mid
                    new_items.append((p, float(t_new)))
        self.timeline_view.set_items(new_items)
        self._update_computed_label()

    def _update_computed_label(self):
        count = self.list_widget.count()
        if count < 2:
            return
        try:
            items = self.timeline_view.get_items()
            if len(items) != count:
                self.label_computed.setText("算出: -（同期中）")
                return
            # quick compute without parsing files (use dummy data for dt only)
            # we need key_times for dt calc; use timeline times directly
            key_times = [t for _, t in items]
            # use dummy keyframes_data length to compute dt
            dummy = [{} for _ in range(count)]
            from .timeline import compute_timeline_frames
            dt, _, inserted = compute_timeline_frames(float(self.spin_duration.value()), dummy, key_times)
            # total frames after interpolation
            # estimate total frames: if uniform -> count, else computed inside
            # we already have dt, compute F
            if count == 2:
                total = 2
            else:
                # recompute with real logic: if uniform, total=count else F
                # compute_timeline_frames returns inserted, so total = count + inserted
                # we have dummy, so inserted is accurate
                total = count + inserted
                # if non-uniform, total from dt
                # verify: total = round(duration/dt)+1
                import math
                if inserted > 0:
                    total = int(round(float(self.spin_duration.value()) / dt)) + 1
            msg = f"算出 Frame Time: {dt:.4f}  総フレーム: {total}"
            if inserted > 0:
                msg += f"（+{inserted}補間）"
            if dt < MIN_FRAME_TIME + 1e-9:
                msg += "  ※最小0.01でクランプ"
            self.label_computed.setText(msg)
        except Exception as e:
            self.label_computed.setText(f"算出エラー: {e}")

    def add_files(self, files):
        existing = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        added = False
        for f in files:
            if len(existing) + self.list_widget.count() >= MAX_FILES:
                pass
            if f in existing:
                continue
            if self.list_widget.count() >= MAX_FILES:
                QMessageBox.warning(self, "上限", f"最大{MAX_FILES}件までです。")
                break
            self.list_widget.addItem(f)
            existing.append(f)
            added = True
        if added:
            self._update_timeline_state()

    def on_add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "LLSD XMLを選択", "", "LLSD XML (*.xml);;All (*.*)")
        if files:
            self.add_files(files)

    def on_remove(self):
        rows = sorted([i.row() for i in self.list_widget.selectedIndexes()], reverse=True)
        for r in rows:
            self.list_widget.takeItem(r)
        self._update_timeline_state()

    def on_clear(self):
        self.list_widget.clear()
        self.timeline_view.set_items([])
        self._update_timeline_state()

    def move_selected(self, delta: int):
        # move each selected item up/down preserving order
        # タイムライン有効時はリスト順は出力に影響しないが、ユーザーの直感のため同期はしない
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        rows = sorted([self.list_widget.row(i) for i in selected])
        if delta < 0:
            for r in rows:
                if r == 0:
                    continue
                item = self.list_widget.takeItem(r)
                self.list_widget.insertItem(r - 1, item)
                item.setSelected(True)
        else:
            for r in reversed(rows):
                if r >= self.list_widget.count() - 1:
                    continue
                item = self.list_widget.takeItem(r)
                self.list_widget.insertItem(r + 1, item)
                item.setSelected(True)
        # リスト順変更はタイムラインの時刻には反映しない（タイムラインが正）
        # 必要なら _sync_timeline() を呼ばずに維持

    def on_browse_out(self):
        path, _ = QFileDialog.getSaveFileName(self, "出力BVH", "", "BVH (*.bvh)")
        if path:
            self.edit_output.setText(path)

    def on_browse_skel(self):
        path, _ = QFileDialog.getOpenFileName(self, "avatar_skeleton.xml", "", "XML (*.xml)")
        if path:
            self.edit_skeleton.setText(path)

    def on_convert(self):
        count = self.list_widget.count()
        if count == 0:
            QMessageBox.warning(self, "エラー", "入力ファイルがありません。")
            return
        if count > MAX_FILES:
            QMessageBox.warning(self, "エラー", f"入力は最大{MAX_FILES}件までです。")
            return
        # validate exists for all list items
        all_inputs = [Path(self.list_widget.item(i).text()) for i in range(count)]
        missing = [str(p) for p in all_inputs if not p.exists()]
        if missing:
            QMessageBox.warning(self, "エラー", "存在しないファイル:\n" + "\n".join(missing))
            return
        out_text = self.edit_output.text().strip()
        # out_path決定は後で（timeline順の先頭を使うため）
        # skeleton解決は共通
        skel_path_text = self.edit_skeleton.text().strip()
        if skel_path_text:
            skel_path = Path(skel_path_text)
        else:
            if getattr(sys, 'frozen', False):
                exe_dir = Path(sys.executable).parent
                meipass = Path(getattr(sys, '_MEIPASS', exe_dir))
                candidates = [
                    exe_dir / "avatar_skeleton.xml",
                    exe_dir / "_internal" / "avatar_skeleton.xml",
                    meipass / "avatar_skeleton.xml",
                    meipass / "_internal" / "avatar_skeleton.xml",
                    Path.cwd() / "avatar_skeleton.xml",
                    Path(__file__).parent.parent.parent / "avatar_skeleton.xml",
                ]
            else:
                candidates = [
                    Path(__file__).parent.parent.parent / "avatar_skeleton.xml",
                    Path.cwd() / "avatar_skeleton.xml",
                ]
            candidates.append(Path(r"C:\Program Files\SecondLifeViewer\character\avatar_skeleton.xml"))
            skel_path = None
            for c in candidates:
                if c.exists():
                    skel_path = c
                    break
            if skel_path is None:
                QMessageBox.warning(self, "エラー", "avatar_skeleton.xml が見つかりません。--skeleton で指定するか、exeと同じフォルダに配置してください。")
                return
        units_map = {"自動": None, "meter": "meter", "inch": "inch"}
        units = units_map[self.combo_units.currentText()]
        sl_map = {"自動": None, "2フレーム": True, "1フレーム": False}
        sl_compat = sl_map[self.combo_sl.currentText()]
        include_face = self.chk_face.isChecked()
        include_tail = self.chk_tail.isChecked()
        include_hands = not self.chk_no_hands.isChecked()

        # timeline分岐
        use_timeline = count >= 2
        if use_timeline:
            # timeline順にソートされた Path, time
            timeline_items = self.timeline_view.get_items()
            # listとtimelineの整合性チェック
            if len(timeline_items) != count:
                QMessageBox.warning(self, "エラー", "タイムラインと入力リストが不一致です。ファイルを再追加してください。")
                return
            # duration
            duration = float(self.spin_duration.value())
            # inputs は timeline順
            inputs = [p for p, _ in timeline_items]
            key_times = [float(t) for _, t in timeline_items]
            # enforce 0 and D (should already)
            key_times[0] = 0.0
            key_times[-1] = duration
            # out_path
            if out_text:
                out_path = Path(out_text)
            else:
                out_path = inputs[0].parent / (inputs[0].stem + "_concatenated.bvh")
            self.progress.setVisible(True)
            self.progress.setMaximum(count + 2)
            self.progress.setValue(0)
            self.log_msg(f"変換開始(タイムライン): {count}件, duration={duration}s → {out_path}")
            try:
                bones = load_skeleton(skel_path)
                bones = filter_skeleton(bones, include_face=include_face, include_tail=include_tail, include_hands=include_hands)
                # parse all
                keyframes_data: list[dict] = []
                for idx, inp in enumerate(inputs):
                    self.log_msg(f"  [{idx+1}/{count}] {inp.name} 解析中... t={key_times[idx]:.2f}s")
                    QApplication.processEvents()
                    data = parse_llsd_xml(inp)
                    keyframes_data.append(data)
                    self.progress.setValue(idx + 1)
                # compute uniform frames
                frame_time, frames, inserted = compute_timeline_frames(duration, keyframes_data, key_times)
                if frame_time < MIN_FRAME_TIME:
                    frame_time = MIN_FRAME_TIME
                self.log_msg(f"  タイムライン解析: duration={duration}s, dt={frame_time:.5f}, 総フレーム={len(frames)} (補間+{inserted})")
                self.log_msg(f"HIERARCHY 構築: {len(bones)} bones")
                write_bvh_frames(frames, bones, out_path, frame_time=frame_time, units=units, sl_compat=sl_compat, include_face=include_face, include_tail=include_tail)
                self.log_msg(f"書き出し完了: {out_path} ({len(frames)}フレーム, dt={frame_time:.5f})")
                QMessageBox.information(self, "完了", f"変換が完了しました:\n{out_path}\n{len(frames)}フレーム (dt={frame_time:.5f}, 補間+{inserted})")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.log_msg(f"エラー: {e}")
                QMessageBox.critical(self, "エラー", f"変換に失敗しました:\n{e}")
            finally:
                self.progress.setVisible(False)
            return
        else:
            # 1件: 従来通り Frame Time 手動
            inputs = all_inputs
            frame_time = float(self.spin_frame.value())
            if out_text:
                out_path = Path(out_text)
            else:
                out_path = inputs[0].with_suffix(".bvh")
            self.progress.setVisible(True)
            self.progress.setMaximum(count)
            self.progress.setValue(0)
            self.log_msg(f"変換開始: {count}件 → {out_path}")
            try:
                bones = load_skeleton(skel_path)
                bones = filter_skeleton(bones, include_face=include_face, include_tail=include_tail, include_hands=include_hands)
                frames = []
                for idx, inp in enumerate(inputs):
                    self.log_msg(f"  [{idx+1}/{count}] {inp.name} 解析中...")
                    QApplication.processEvents()
                    data = parse_llsd_xml(inp)
                    frames.append(data)
                    self.progress.setValue(idx + 1)
                self.log_msg(f"HIERARCHY 構築: {len(bones)} bones")
                write_bvh_frames(frames, bones, out_path, frame_time=frame_time, units=units, sl_compat=sl_compat, include_face=include_face, include_tail=include_tail)
                self.log_msg(f"書き出し完了: {out_path} ({len(frames)}フレーム)")
                QMessageBox.information(self, "完了", f"変換が完了しました:\n{out_path}\n{len(frames)}フレーム")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.log_msg(f"エラー: {e}")
                QMessageBox.critical(self, "エラー", f"変換に失敗しました:\n{e}")
            finally:
                self.progress.setVisible(False)


def main(argv=None):
    app = QApplication(sys.argv if argv is None else [sys.argv[0]] + (argv or []))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
