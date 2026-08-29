# -*- coding: utf-8 -*-
"""GUI スクリーンショット撮影用。サンプル1-2件を追加した状態で保存。"""
import sys
from pathlib import Path

# src を path に追加（pip install -e 前でも動くように）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from llsd2bvh.gui import MainWindow

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    # サンプルを1-2件追加した状態
    samples = [
        str(ROOT / "tests" / "samples" / "testChange03.xml"),
        str(ROOT / "tests" / "samples" / "testChange04.xml"),
    ]
    # 存在するものだけ
    samples = [s for s in samples if Path(s).exists()]
    if samples:
        win.add_files(samples[:2])
        win.edit_output.setText(str(ROOT / "dist" / "LLSD2BVH" / "output.bvh"))
    win.show()
    # 描画を待ってからキャプチャ
    def grab_and_quit():
        app.processEvents()
        pix = win.grab()
        out = ROOT / "docs" / "screenshot-gui.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out))
        print(f"saved: {out} ({pix.width()}x{pix.height()})")
        # 少し待って終了
        QTimer.singleShot(500, app.quit)
    QTimer.singleShot(800, grab_and_quit)
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
