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
    # サンプルを2-3件追加した状態（タイムライン表示）
    samples = [
        str(ROOT / "tests" / "samples" / "testChange03.xml"),
        str(ROOT / "tests" / "samples" / "testChange04.xml"),
        str(ROOT / "tests" / "samples" / "testChange01.xml"),
    ]
    # 存在するものだけ
    samples = [s for s in samples if Path(s).exists()]
    if samples:
        win.add_files(samples[:3])
        win.spin_duration.setValue(5.0)
        win.edit_output.setText(str(ROOT / "dist" / "LLSD2BVH" / "output.bvh"))
        # 重なりデモ用に2件目を0.4秒に寄せて縦ずらしを確認
        items = win.timeline_view.get_items()
        if len(items) == 3:
            win.timeline_view.set_items([(items[0][0], 0.0), (items[1][0], 0.4), (items[2][0], 5.0)])
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
