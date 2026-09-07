# -*- coding: utf-8 -*-
"""`python -m llsd2bvh.viewer` 起動点（推奨）。

`python -m llsd2bvh.viewer.viewer_window` 直実行は親パッケージ __init__ の
即時 import と競合して RuntimeWarning を出すため、本モジュールを経由する。
"""
from .viewer_window import main

if __name__ == "__main__":
    raise SystemExit(main())
