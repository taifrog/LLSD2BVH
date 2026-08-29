# -*- coding: utf-8 -*-
"""PyInstaller entry for GUI (avoids relative import issue)."""
import sys
from llsd2bvh.gui import main

if __name__ == '__main__':
    sys.exit(main())
