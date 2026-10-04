# -*- coding: utf-8 -*-
"""BVHビューアウィンドウ（PreviewPanelをホストする薄ラッパー＋単独起動入口）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import QSettings

from .preview_panel import PreviewPanel


class BvhViewerWindow(QMainWindow):
    """単独ビューア用ウィンドウ。内容はPreviewPanelに委譲する。"""

    def __init__(self, initial_path: str | Path | None = None, lang: str = "ja", parent=None):
        super().__init__(parent)
        if lang not in ("ja", "en"):
            lang = "ja"
        else:
            # 単独起動時は保存言語を尊重（既存動作の維持）
            try:
                saved = QSettings("TAIFROG", "LLSD2BVH").value("lang", None)
                if lang == "ja" and saved in ("ja", "en"):
                    lang = saved
            except Exception:
                pass
        self._panel = PreviewPanel(lang=lang, parent=self)
        self.setCentralWidget(self._panel)
        self.setWindowTitle("BVH Viewer - Stick Figure")
        self.resize(900, 640)
        self.setAcceptDrops(True)
        if initial_path and Path(initial_path).exists():
            self.load_bvh(initial_path)

    @property
    def panel(self) -> PreviewPanel:
        """内蔵パネル（組込み利用向け）。"""
        return self._panel

    def load_bvh(self, path: str | Path) -> bool:
        """BVHを読み込む。成功時はタイトルにファイル名を反映する。"""
        ok = self._panel.load_bvh(path)
        if ok:
            self.setWindowTitle(f"BVH Viewer - {Path(path).name}")
        return ok

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
        self._panel._stop()
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
