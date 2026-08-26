# -*- coding: utf-8 -*-
"""GUI版 LLSD→BVH 変換ツール (PySide6)。

- 入力最大20件、ドラッグ＆ドロップ＋順序入替可
- 各オプションはCLIと同等、1 BVHへ全フレーム連結出力
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
        self.resize(820, 620)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Input list
        layout.addWidget(QLabel("入力LLSDファイル（最大20件、ドラッグ＆ドロップ可、順序がフレーム順）:"))
        self.list_widget = FileListWidget()
        layout.addWidget(self.list_widget, stretch=3)

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

    # helpers
    def log_msg(self, msg: str):
        self.log.append(msg)

    def add_files(self, files):
        existing = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        for f in files:
            if len(existing) + self.list_widget.count() >= MAX_FILES:
                # count already includes existing + added in this call? Simplify: check current count
                pass
            if f in existing:
                continue
            if self.list_widget.count() >= MAX_FILES:
                QMessageBox.warning(self, "上限", f"最大{MAX_FILES}件までです。")
                break
            self.list_widget.addItem(f)
            existing.append(f)

    def on_add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "LLSD XMLを選択", "", "LLSD XML (*.xml);;All (*.*)")
        if files:
            self.add_files(files)

    def on_remove(self):
        rows = sorted([i.row() for i in self.list_widget.selectedIndexes()], reverse=True)
        for r in rows:
            self.list_widget.takeItem(r)

    def on_clear(self):
        self.list_widget.clear()

    def move_selected(self, delta: int):
        # move each selected item up/down preserving order
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        # get rows
        rows = sorted([self.list_widget.row(i) for i in selected])
        if delta < 0:
            # up: iterate top to bottom
            for r in rows:
                if r == 0:
                    continue
                item = self.list_widget.takeItem(r)
                self.list_widget.insertItem(r - 1, item)
                item.setSelected(True)
        else:
            # down: iterate bottom to top
            for r in reversed(rows):
                if r >= self.list_widget.count() - 1:
                    continue
                item = self.list_widget.takeItem(r)
                self.list_widget.insertItem(r + 1, item)
                item.setSelected(True)

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
        inputs = [Path(self.list_widget.item(i).text()) for i in range(count)]
        # validate exists
        missing = [str(p) for p in inputs if not p.exists()]
        if missing:
            QMessageBox.warning(self, "エラー", "存在しないファイル:\n" + "\n".join(missing))
            return
        out_text = self.edit_output.text().strip()
        if out_text:
            out_path = Path(out_text)
        else:
            # default: first input stem.bvh in its dir
            out_path = inputs[0].with_suffix(".bvh")
            if count > 1:
                # for multi, put in first input's dir as concatenated.bvh if name collision?
                out_path = inputs[0].parent / (inputs[0].stem + "_concatenated.bvh")

        # skeleton
        skel_path_text = self.edit_skeleton.text().strip()
        if skel_path_text:
            skel_path = Path(skel_path_text)
        else:
            candidates = [
                Path(__file__).parent.parent.parent / "avatar_skeleton.xml",
                Path.cwd() / "avatar_skeleton.xml",
                Path(r"C:\Program Files\SecondLifeViewer\character\avatar_skeleton.xml"),
            ]
            skel_path = None
            for c in candidates:
                if c.exists():
                    skel_path = c
                    break
            if skel_path is None:
                QMessageBox.warning(self, "エラー", "avatar_skeleton.xml が見つかりません。--skeleton で指定してください。")
                return
        # options
        units_map = {"自動": None, "meter": "meter", "inch": "inch"}
        units = units_map[self.combo_units.currentText()]
        sl_map = {"自動": None, "2フレーム": True, "1フレーム": False}
        sl_compat = sl_map[self.combo_sl.currentText()]
        frame_time = float(self.spin_frame.value())
        include_face = self.chk_face.isChecked()
        include_tail = self.chk_tail.isChecked()
        include_hands = not self.chk_no_hands.isChecked()

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
