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
        self.btn_copy = QPushButton("コピー")
        self.btn_copy.setToolTip("選択中の1件を複製して直後に挿入（最大20件）")
        self.btn_copy.setEnabled(False)
        self.btn_up = QPushButton("↑")
        self.btn_down = QPushButton("↓")
        self.btn_clear = QPushButton("クリア")
        for b in [self.btn_add, self.btn_remove, self.btn_copy, self.btn_up, self.btn_down, self.btn_clear]:
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
        self._label_frame = QLabel("Frame Time:")
        self._label_frame.setVisible(False)
        self.spin_frame = QDoubleSpinBox()
        self.spin_frame.setDecimals(7)
        self.spin_frame.setSingleStep(0.001)
        self.spin_frame.setRange(0.001, 1.0)
        self.spin_frame.setValue(0.0333333)
        self.spin_frame.setVisible(False)
        self._label_frame_suffix = QLabel("(固定値 0.0333)")
        self._label_frame_suffix.setVisible(False)
        opt_row2.addWidget(self._label_frame)
        opt_row2.addWidget(self.spin_frame)
        opt_row2.addWidget(self._label_frame_suffix)
        opt_row2.addStretch()
        layout.addLayout(opt_row2)

        opt_row3 = QHBoxLayout()
        self.chk_no_hands = QCheckBox("手を除外")
        self.chk_no_hands.setChecked(True)
        opt_row3.addWidget(self.chk_no_hands)
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
        self.btn_copy.clicked.connect(self.on_copy)
        self.btn_up.clicked.connect(lambda: self.move_selected(-1))
        self.btn_down.clicked.connect(lambda: self.move_selected(1))
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_browse_out.clicked.connect(self.on_browse_out)
        self.btn_browse_skel.clicked.connect(self.on_browse_skel)
        self.btn_convert.clicked.connect(self.on_convert)
        self.btn_close.clicked.connect(self.close)
        self.spin_duration.valueChanged.connect(self._on_duration_changed)
        self.timeline_view.timeChanged.connect(self._on_timeline_changed)
        self.list_widget.itemSelectionChanged.connect(self._update_copy_button_state)
        # リスト内部ドラッグ並替後も番号を振り直す
        try:
            self.list_widget.model().rowsMoved.connect(self._on_list_reordered)
        except Exception:
            pass

    # helpers
    def log_msg(self, msg: str):
        self.log.append(msg)

    def _update_copy_button_state(self):
        sel = self.list_widget.selectedItems()
        self.btn_copy.setEnabled(len(sel) == 1 and self.list_widget.count() < MAX_FILES)

    def on_copy(self):
        sel = self.list_widget.selectedItems()
        if len(sel) != 1:
            QMessageBox.warning(self, "コピー", "コピーは1件選択時のみ可能です。")
            return
        if self.list_widget.count() >= MAX_FILES:
            QMessageBox.warning(self, "上限", f"最大{MAX_FILES}件までです。")
            return
        src_item = sel[0]
        src_row = self.list_widget.row(src_item)
        src_path_str = src_item.data(Qt.UserRole)
        if not src_path_str:
            # fallback
            src_path_str = src_item.text().split(". ", 1)[-1]
        src_path = Path(src_path_str)
        # リストへ挿入（重複許容 — add_filesを経由しない）
        new_item = QListWidgetItem()
        new_item.setData(Qt.UserRole, src_path_str)
        new_item.setToolTip(str(src_path_str))
        # 一時テキスト、後で _refresh_list_numbers で振り直し
        new_item.setText(Path(src_path_str).name)
        self.list_widget.insertItem(src_row + 1, new_item)
        self._refresh_list_numbers()
        self.list_widget.clearSelection()
        new_item.setSelected(True)
        # タイムラインへ挿入
        self._insert_duplicate_into_timeline(src_path, src_row)
        self._update_copy_button_state()
        self._update_computed_label()

    def _insert_duplicate_into_timeline(self, src_path: Path, src_row: int):
        count = self.list_widget.count()
        dur = float(self.spin_duration.value())
        paths = self._get_full_paths()
        # 番号マップは常にリスト順で振り直し（重複対応）
        self._sync_number_map()
        if count < 2:
            if count == 0:
                self.timeline_view.set_items([])
            elif count == 1:
                # 1件時はタイムライン無効だが番号だけ更新
                pass
            self._update_timeline_state()
            return
        # 2件以上: 既存タイムラインに複製を追加
        items = self.timeline_view.get_items()  # sorted
        # 1件からの遷移（以前 timeline が空）や不整合時は均一再配置で作成
        if len(items) != count - 1:
            self._sync_timeline()
            # _sync_timeline は均一で作成済みだが、要件の src直後配置を保証するため
            # 均一結果をそのまま使う（0 と D の2件なら src直後ではないが、1->2では許容）
            # 2件以上で既存が空だった場合は再取得して補正
            items = self.timeline_view.get_items()
            if len(items) == count:
                # 既にカウント一致（均一作成で完了）
                self._update_computed_label()
                return
            # それでも不一致なら通常追加ロジックへフォールスルー
        # 以降は items が count-1 件存在する前提で複製を追加
        # src_t をリスト行に対応する出現回数で特定
        ordered = self._get_full_paths()
        src_str = str(src_path)
        # src_row は複製元の行。挿入後の ordered では src_row が元、src_row+1 が複製
        # 元の出現回数（0-based）を求める
        occ = sum(1 for i in range(src_row + 1) if str(ordered[i]) == src_str) - 1
        # 但し ordered は挿入後のため、複製分を除けば src の occ は上記 - (複製が同パスなら1)
        # 実際には ordered[src_row] が元なので、src_row までのカウントで occ を得るのは正確
        # ただし上記は挿入後のカウントなので、複製が src と同パスなら occ が1多くなる
        # そのため occ を1減らす補正は不要（src_row までのカウントは元を含むが複製は src_row+1 なので含まない）
        # 正しくは src_row までのカウント -1 が occ
        # 上記式は既に -1 しているので正しい
        # タイムライン側で occ 回目の出現の時刻を取得
        src_t = None
        cur = -1
        for p, t in items:
            if str(p) == src_str:
                cur += 1
                if cur == occ:
                    src_t = t
                    break
        if src_t is None:
            src_candidates = [(p, t) for p, t in items if str(p) == src_str]
            if src_candidates:
                src_t = src_candidates[-1][1]
            else:
                src_t = dur / 2
        # 端点（固定）の複製は特別扱い
        is_first = abs(src_t - 0.0) < 1e-9
        is_last = abs(src_t - dur) < 1e-9
        is_last_copy = is_last and src_row == count - 2  # リストで末尾をコピーした場合
        if is_last_copy:
            prev_ts = sorted([t for _, t in items if t < src_t - 1e-9])
            prev_t = prev_ts[-1] if prev_ts else 0.0
            cand1 = dur - 0.05
            cand2 = (prev_t + dur) / 2
            t_new_for_original = max(prev_t + 0.05, min(cand1, cand2) if prev_t + 0.10 <= dur else cand1)
            t_new_for_original = max(prev_t + 0.05, min(t_new_for_original, dur - 0.05))
            # 末尾複製は新末尾を D、元末尾を t_new_for_original に
            t_new = t_new_for_original  # 一時保存、後で分岐で使用
        elif is_last:
            prev_ts = sorted([t for _, t in items if t < src_t - 1e-9])
            prev_t = prev_ts[-1] if prev_ts else 0.0
            cand1 = dur - 0.05
            cand2 = (prev_t + dur) / 2
            t_new = max(prev_t + 0.05, min(cand1, cand2) if prev_t + 0.10 <= dur else cand1)
            t_new = max(prev_t + 0.05, min(t_new, dur - 0.05))
        elif is_first:
            next_ts = sorted([t for _, t in items if t > src_t + 1e-9])
            next_t = next_ts[0] if next_ts else dur
            t_new = min(src_t + 0.05, (src_t + next_t) / 2)
            t_new = max(src_t + 0.05, min(t_new, next_t - 0.05)) if next_t - src_t >= 0.10 else src_t + 0.05
        else:
            next_ts = sorted([t for _, t in items if t > src_t + 1e-9])
            next_t = next_ts[0] if next_ts else dur
            mid = (src_t + next_t) / 2
            t_new = min(src_t + 0.05, mid)
            if next_t - src_t >= 0.10:
                t_new = max(src_t + 0.05, min(t_new, next_t - 0.05))
            else:
                t_new = src_t + 0.05
                if t_new > dur - 0.001:
                    t_new = dur - 0.001
        t_new = max(0.001, min(t_new, dur - 0.001))
        t_new = max(0.0, min(t_new, dur))
        # リスト順で src の直後に挿入（タイムライン順＝リスト順）
        insert_idx = src_row + 1
        insert_idx = max(0, min(insert_idx, len(items)))
        if is_last_copy:
            # 末尾をコピー: 元末尾を t_new (=2.5等) に、新末尾を D に
            # items の末尾が元末尾
            new_items = list(items)
            # 元末尾の時刻を t_new に更新
            last_p, _ = new_items[-1]
            new_items[-1] = (last_p, float(t_new))
            new_items.append((src_path, float(dur)))
        else:
            new_items = list(items[:insert_idx]) + [(src_path, float(t_new))] + list(items[insert_idx:])
        self.timeline_view.set_items(new_items)
        # 番号振り直し（重複対応のため ordered_paths も更新）
        self._sync_number_map()
        self._update_computed_label()

    def _sync_number_map(self):
        paths = self._get_full_paths()
        tmp = {}
        for i, p in enumerate(paths):
            tmp[str(p)] = i + 1
        self.timeline_view.set_number_map(tmp)
        try:
            self.timeline_view.set_ordered_paths(paths)
        except AttributeError:
            pass

    # --- timeline helpers ---
    def _update_timeline_state(self):
        count = self.list_widget.count()
        has_timeline = count >= 2
        self.timeline_view.setEnabled(has_timeline)
        self.spin_duration.setEnabled(has_timeline)
        # Frame Time は常時非表示（固定値 0.0333333 を使用）
        self.spin_frame.setVisible(False)
        self._label_frame.setVisible(False)
        self._label_frame_suffix.setVisible(False)
        if has_timeline:
            self._sync_timeline()
        self._update_computed_label()
        self._update_copy_button_state()

    def _get_full_paths(self) -> list[Path]:
        paths: list[Path] = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            full = item.data(Qt.UserRole)
            if full:
                paths.append(Path(full))
            else:
                # fallback: parse "N. name" or raw path
                txt = item.text()
                if ". " in txt:
                    # try to extract after ". "
                    # but fallback may be inaccurate; use txt as is
                    paths.append(Path(txt.split(". ", 1)[-1]))
                else:
                    paths.append(Path(txt))
        return paths

    def _refresh_list_numbers(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            full = item.data(Qt.UserRole)
            if not full:
                continue
            name = Path(full).name
            item.setText(f"{i+1}. {name}")
            item.setToolTip(str(full))

    def _on_duration_changed(self, _val):
        new_dur = float(self.spin_duration.value())
        old_dur = float(self.timeline_view.duration())
        self.timeline_view.set_duration(new_dur)
        items = self.timeline_view.get_items()
        if items:
            # Tposeを除いた n 点は dt..D に配置。リサイズ時は比率を保持しつつ
            # 先頭は new_dt, 末尾は new_dur に
            n = len(items)
            new_dt = new_dur / n if n > 0 else 0.0
            old_dt = old_dur / n if n > 0 else 0.0
            scaled = []
            for idx, (p, t) in enumerate(items):
                if idx == 0:
                    scaled.append((p, float(new_dt)))
                elif idx == len(items) - 1:
                    scaled.append((p, new_dur))
                else:
                    # 中間は 0..D ではなく dt..D の比率でスケール
                    if old_dur > 1e-9:
                        # t は old_dt..old_dur の範囲、比率で new_dt..new_dur へ
                        if old_dur - old_dt > 1e-9:
                            ratio = (t - old_dt) / (old_dur - old_dt)
                        else:
                            ratio = 0.0
                        nt = new_dt + ratio * (new_dur - new_dt)
                    else:
                        nt = t
                    scaled.append((p, float(nt)))
            self.timeline_view.set_items(scaled)
        self._update_computed_label()

    def _on_timeline_changed(self):
        self._update_computed_label()

    def _on_list_reordered(self, *args):
        self._refresh_list_numbers()
        # タイムラインもリスト順に追従（時刻は保持）
        # ドラッグ直後のリスト順にタイムラインを並べ替え
        # 既存タイムラインの時刻を出現回数でマッピング
        old_items = list(self.timeline_view.get_items())
        # old_items はドラッグ前のリスト順だが、ドラッグ後はリストが既に入替わっているため、
        # old_items の順序と新リストの順序を対応させる必要がある
        # 簡易: タイムラインをリスト順に再ソート（時刻は保持せず均一再配置に近いが、既存時刻を再利用）
        # ここでは _sync_timeline の非均一保持ロジックに委ねず、単に番号マップと並べ替えを行う
        # 既存時刻を保持したままリスト順に並べ替えるため、old_map を使う
        old_map: dict[tuple[str, int], float] = {}
        occ = {}
        for p, t in old_items:
            k = str(p)
            o = occ.get(k, 0)
            old_map[(k, o)] = float(t)
            occ[k] = o + 1
        new_paths = self._get_full_paths()
        new_occ = {}
        new_items: list[tuple[Path, float]] = []
        for p in new_paths:
            k = str(p)
            o = new_occ.get(k, 0)
            new_occ[k] = o + 1
            t = old_map.get((k, o))
            if t is None and old_items:
                # 新規があれば暫定
                t = 0.0
            if t is not None:
                new_items.append((p, float(t)))
        if new_items and len(new_items) == len(new_paths):
            # 単調性を _enforce で保証
            self.timeline_view.set_items(new_items)
        self._sync_number_map()
        self.timeline_view.update()
        self._update_copy_button_state()
        self._update_computed_label()

    def _sync_timeline(self):
        """list_widget の内容を timeline_view に同期"""
        count = self.list_widget.count()
        if count < 2:
            if count == 0:
                self.timeline_view.set_items([])
                self.timeline_view.set_number_map({})
                try:
                    self.timeline_view.set_ordered_paths([])
                except AttributeError:
                    pass
            else:
                # 1件でも番号マップは更新（表示用）
                self._sync_number_map()
            return
        dur = float(self.spin_duration.value())
        self.timeline_view.set_duration(dur)
        list_paths = self._get_full_paths()
        # 番号マップ（リスト順 1..N）重複対応
        self._sync_number_map()
        existing_items = self.timeline_view.get_items()  # リスト順
        # 既存が空 or 均一なら均一再配置
        is_uniform = False
        if existing_items:
            # リスト順での gaps（単調性が保たれている前提でソート不要）
            gaps = [existing_items[i + 1][1] - existing_items[i][1] for i in range(len(existing_items) - 1)]
            if gaps and max(gaps) - min(gaps) <= 1e-4:
                is_uniform = True
        if not existing_items or is_uniform:
            # 均一再配置（リスト順）Tposeを除いた n 点を dt..D に配置
            # Frame Time = D / n, P1@dt ... Pn@D, Tpose@0 は BVH出力時に付与
            dt = dur / count if count > 0 else dur
            new_items: list[tuple[Path, float]] = []
            for i, p in enumerate(list_paths):
                t = (i + 1) * dt
                # 最終は D にクランプ
                if i == count - 1:
                    t = dur
                new_items.append((p, float(t)))
            self.timeline_view.set_items(new_items)
            self._update_computed_label()
            return
        # 非均一保持: 既存はリスト順の出現回数で対応、新規は前後の中間へ（リスト順を保持）
        # 既存を出現回数マップで保持
        # Build map from (path_str, occurrence) -> time
        existing_map: dict[tuple[str, int], float] = {}
        occ_counter: dict[str, int] = {}
        for p, t in existing_items:
            k = str(p)
            occ = occ_counter.get(k, 0)
            existing_map[(k, occ)] = float(t)
            occ_counter[k] = occ + 1
        new_items: list[tuple[Path, float]] = []
        # 新リストの出現回数を数えながら構築
        new_occ_counter: dict[str, int] = {}
        for idx, p in enumerate(list_paths):
            k = str(p)
            occ = new_occ_counter.get(k, 0)
            new_occ_counter[k] = occ + 1
            if (k, occ) in existing_map:
                # 既存の時刻を流用（リスト順を保持）
                new_items.append((p, existing_map[(k, occ)]))
            else:
                # 新規: 前後の時刻から算出（リスト順）
                # prev は new_items の直前、next は既存の対応する位置以降の時刻を推定
                # 簡易: prev = new_items[-1] の時刻、next = 次の既存項目の時刻 or D
                if not new_items:
                    prev_t = 0.0
                else:
                    prev_t = new_items[-1][1]
                # next は list_paths の idx+1 以降で既存に存在する最初の項目の時刻を探す
                next_t = dur
                # 既存の残りをリスト順で走査して次の一致を探す（近似: dur を使用）
                # より正確には、既存_items の idx 付近の時刻を使うが、非均一時は dur で十分
                # ここでは prev と dur の中間を暫定とし、後で _enforce で単調性を保証
                # 要件に近い: prev+0.05 と中間の小さい方
                # next_t を dur として計算
                mid = (prev_t + next_t) / 2
                t_new = min(prev_t + 0.05, mid) if new_items else 0.0
                # 先頭は0固定、末尾はD固定のため、内側のみ上記を使用
                if idx == count - 1:
                    t_new = dur
                elif idx == 0:
                    t_new = 0.0
                else:
                    # prev と next の間に収める（next が dur の場合は上記 mid）
                    # list順で next がまだ未確定のため dur で近似
                    pass
                # 末尾以外は prev+0.05 を優先しつつ D を超えない
                if idx != 0 and idx != count - 1:
                    # next が dur の場合、中間は大きくなるため prev+0.05 が選ばれる
                    t_new = min(prev_t + 0.05, (prev_t + dur) / 2)
                new_items.append((p, float(t_new)))
        # 単調性を _enforce で保証するため、そのままセット
        self.timeline_view.set_items(new_items)
        self._update_computed_label()

    def _update_computed_label(self):
        count = self.list_widget.count()
        if count == 0:
            self.label_computed.setText("算出: -")
            return
        if count == 1:
            dur = float(self.spin_duration.value())
            # 常時Tpose: P1は D に配置、Tposeは0、Frame Time = D/1
            dt = dur / 1 if count >= 1 else 0.0333333
            if dt < MIN_FRAME_TIME:
                dt = MIN_FRAME_TIME
            # 表示は総フレーム n+1（Tpose含む）
            self.label_computed.setText(f"Frame Time: {dt:.4f}  総フレーム: 2（Tpose+1）")
            return
        try:
            items = self.timeline_view.get_items()
            if len(items) != count:
                self.label_computed.setText("算出: -（同期中）")
                return
            # quick compute without parsing files (use dummy data for dt only)
            # key_times は Tposeを除いた P1..Pn の n 点（dt..D）
            key_times = [t for _, t in items]
            dummy = [{} for _ in range(count)]
            from .timeline import compute_timeline_frames
            dt, _, inserted = compute_timeline_frames(float(self.spin_duration.value()), dummy, key_times)
            # Tposeを除いた n 点での dt/inserted、総フレームは Tpose+1 を加算
            # 均一時 total_user = n, 非均一 total_user = n+inserted (=F)
            if count == 2:
                total_user = 2
                # dt は D/2 のはず
                inserted_user = 0
            else:
                if inserted > 0:
                    import math
                    total_user = int(round(float(self.spin_duration.value()) / dt)) + 1
                    # 非均一時の dt は min_gap 基準、total_user は F
                    inserted_user = total_user - count
                else:
                    total_user = count
                    inserted_user = 0
            total = total_user + 1  # Tpose分
            msg = f"算出 Frame Time: {dt:.4f}  総フレーム: {total}（Tpose+{total_user}）"
            if inserted_user > 0:
                msg += f"（+{inserted_user}補間）"
            if dt < MIN_FRAME_TIME + 1e-9:
                msg += "  ※最小0.01でクランプ"
            self.label_computed.setText(msg)
        except Exception as e:
            self.label_computed.setText(f"算出エラー: {e}")

    def add_files(self, files):
        # existing full paths set
        existing_full = {str(p) for p in self._get_full_paths()}
        added = False
        for f in files:
            full = str(Path(f).resolve())
            # also check normalized string with original
            if str(Path(f)) in existing_full or full in existing_full:
                continue
            if self.list_widget.count() >= MAX_FILES:
                QMessageBox.warning(self, "上限", f"最大{MAX_FILES}件までです。")
                break
            item = QListWidgetItem()
            # store full path in UserRole, display will be numbered later
            item.setData(Qt.UserRole, str(Path(f)))
            # temporary text; will be renumbered
            item.setText(Path(f).name)
            item.setToolTip(str(Path(f)))
            self.list_widget.addItem(item)
            existing_full.add(str(Path(f)))
            existing_full.add(full)
            added = True
        if added:
            self._refresh_list_numbers()
            self._update_timeline_state()

    def on_add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "LLSD XMLを選択", "", "LLSD XML (*.xml);;All (*.*)")
        if files:
            self.add_files(files)

    def on_remove(self):
        rows = sorted([i.row() for i in self.list_widget.selectedIndexes()], reverse=True)
        for r in rows:
            self.list_widget.takeItem(r)
        self._refresh_list_numbers()
        self._update_timeline_state()

    def on_clear(self):
        self.list_widget.clear()
        self.timeline_view.set_items([])
        self.timeline_view.set_number_map({})
        try:
            self.timeline_view.set_ordered_paths([])
        except AttributeError:
            pass
        self._update_timeline_state()

    def move_selected(self, delta: int):
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        # タイムライン順＝リスト順のため、移動前のタイムラインを保持
        old_items = list(self.timeline_view.get_items())
        old_map: dict[tuple[str, int], float] = {}
        occ = {}
        for p, t in old_items:
            k = str(p)
            o = occ.get(k, 0)
            old_map[(k, o)] = float(t)
            occ[k] = o + 1
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
        self._refresh_list_numbers()
        # タイムラインもリスト順に並べ替え（時刻は出現回数で対応）
        new_paths = self._get_full_paths()
        new_occ = {}
        new_items: list[tuple[Path, float]] = []
        for p in new_paths:
            k = str(p)
            o = new_occ.get(k, 0)
            new_occ[k] = o + 1
            t = old_map.get((k, o), None)
            if t is None:
                # 新規は前後の時刻から推定（均一に近い位置）
                # 簡易: 前の時刻+0.05 or 0
                if new_items:
                    t = new_items[-1][1] + 0.05
                else:
                    t = 0.0
            new_items.append((p, float(t)))
        # 先頭0末尾Dを _enforce で保証
        self.timeline_view.set_items(new_items)
        self._sync_number_map()
        self.timeline_view.update()
        self._update_copy_button_state()
        self._update_computed_label()

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
        all_inputs = self._get_full_paths()
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
        include_face = False
        include_tail = False
        include_hands = not self.chk_no_hands.isChecked()

        # 常時Tposeを先頭に追加。Frame Time = D / n、総フレーム = n+1
        # タイムライン分岐（Tposeを除いた n 点で計算）
        use_timeline = count >= 2
        if use_timeline:
            timeline_items = self.timeline_view.get_items()  # リスト順、P1..Pn は dt..D
            if len(timeline_items) != count:
                QMessageBox.warning(self, "エラー", "タイムラインと入力リストが不一致です。ファイルを再追加してください。")
                return
            duration = float(self.spin_duration.value())
            inputs = [p for p, _ in timeline_items]
            key_times = [float(t) for _, t in timeline_items]  # dt..D
            # duration と整合（先頭は dt、末尾は D）
            # 呼出側で Tpose を除外して計算するため、key_times は dt..D のまま
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
                keyframes_data: list[dict] = []
                for idx, inp in enumerate(inputs):
                    self.log_msg(f"  [{idx+1}/{count}] {inp.name} 解析中... t={key_times[idx]:.2f}s")
                    QApplication.processEvents()
                    data = parse_llsd_xml(inp)
                    keyframes_data.append(data)
                    self.progress.setValue(idx + 1)
                # Tposeを除いた n 点で Frame Time を算出
                # 非均一時は全体で1つの Frame Time で必要な追加フレームを補間
                frame_time, frames_user, inserted = compute_timeline_frames(duration, keyframes_data, key_times)
                if frame_time < MIN_FRAME_TIME:
                    frame_time = MIN_FRAME_TIME
                # Frame Time は D / n が基本だが、非均一時の compute が min_gap から算出した dt を優先
                # 均一時（inserted==0）は D/n と一致するはず
                # 総フレームは Tpose + frames_user
                tpose_frame: dict = {}
                frames = [tpose_frame] + frames_user
                # Frame Time は compute の dt をそのまま使用（Tposeを含めた n+1 フレームで duration をカバー）
                # ただし n 点が dt..D に配置されているため、Tpose(0) から P1(dt) の gap も dt で均一
                # そのため total duration = len(frames)-1 * frame_time = D となる
                self.log_msg(f"  タイムライン解析: duration={duration}s, dt={frame_time:.5f}, ユーザフレーム={len(frames_user)} (補間+{inserted}) 総フレーム={len(frames)}（Tpose+{len(frames_user)}）")
                self.log_msg(f"HIERARCHY 構築: {len(bones)} bones")
                # Tposeは呼出側で付与済みのため sl_compat は False で二重挿入を避ける
                write_bvh_frames(frames, bones, out_path, frame_time=frame_time, units=units, sl_compat=False, include_face=include_face, include_tail=include_tail)
                self.log_msg(f"書き出し完了: {out_path} ({len(frames)}フレーム, dt={frame_time:.5f})")
                QMessageBox.information(self, "完了", f"変換が完了しました:\n{out_path}\n{len(frames)}フレーム (dt={frame_time:.5f}, 補間+{inserted}, Tpose含む)")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.log_msg(f"エラー: {e}")
                QMessageBox.critical(self, "エラー", f"変換に失敗しました:\n{e}")
            finally:
                self.progress.setVisible(False)
            return
        else:
            # 1件: 常時Tpose挿入で Frames:2
            inputs = all_inputs
            duration = float(self.spin_duration.value())
            frame_time = duration / 1 if duration > 1e-9 else 0.0333333
            if frame_time < MIN_FRAME_TIME:
                frame_time = MIN_FRAME_TIME
            if out_text:
                out_path = Path(out_text)
            else:
                out_path = inputs[0].with_suffix(".bvh")
            self.progress.setVisible(True)
            self.progress.setMaximum(count + 1)
            self.progress.setValue(0)
            self.log_msg(f"変換開始: {count}件 duration={duration}s → {out_path} (Tpose+1)")
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
                tpose_frame: dict = {}
                frames = [tpose_frame] + frames
                self.log_msg(f"HIERARCHY 構築: {len(bones)} bones")
                write_bvh_frames(frames, bones, out_path, frame_time=frame_time, units=units, sl_compat=False, include_face=include_face, include_tail=include_tail)
                self.log_msg(f"書き出し完了: {out_path} ({len(frames)}フレーム, dt={frame_time:.5f}, Tpose含む)")
                QMessageBox.information(self, "完了", f"変換が完了しました:\n{out_path}\n{len(frames)}フレーム (Tpose含む)")
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
