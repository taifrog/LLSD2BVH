# -*- coding: utf-8 -*-
"""Poser 設定の読み込み。floater_fs_poser.xml から joint_transform 等をパース。

MVPでは BVH 出力は LLSD の roll/pitch/yaw をそのまま度数化して出力する
（Viewerの保存時点で既に joint ローカル変換済みのため）。
このモジュールは将来の per-joint SWAP/NEGATE 対応のための土台。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple

# Viewer のデフォルト: SWAP_NOTHING
SWAP_NOTHING = "SWAP_NOTHING"
VALID_SWAPS = {
    "SWAP_NOTHING",
    "SWAP_YAW_AND_ROLL",
    "SWAP_YAW_AND_PITCH",
    "SWAP_ROLL_AND_PITCH",
    "SWAP_X2Y_Y2Z_Z2X",
    "SWAP_X2Z_Y2X_Z2Y",
}


def parse_floater_poser_xml(path: str | Path) -> Dict[str, Tuple[str, int]]:
    """floater_fs_poser.xml から joint_transform_* を読む。

    Returns:
        {joint_name: (swap_enum, negate_mask)}
        negate_mask bits: 1=YAW(VX), 2=PITCH(VY), 4=ROLL(VZ), 7=ALL
    """
    p = Path(path)
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8")
    result: Dict[str, Tuple[str, int]] = {}
    pattern = re.compile(r'name="(joint_transform_[^"]+)"[^>]*>([^<]+)</string>')
    for m in pattern.finditer(txt):
        key = m.group(1)  # joint_transform_mPelvis
        val = m.group(2).strip()
        joint = key.replace("joint_transform_", "")
        swap = SWAP_NOTHING
        negate = 0
        for token in val.split():
            token = token.strip().upper()
            if token in VALID_SWAPS:
                swap = token
            elif token == "NEGATE_YAW":
                negate |= 1
            elif token == "NEGATE_PITCH":
                negate |= 2
            elif token == "NEGATE_ROLL":
                negate |= 4
            elif token == "NEGATE_ALL":
                negate |= 7
        result[joint] = (swap, negate)
    return result


def parse_bvh_transforms(path: str | Path) -> Dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8")
    result: Dict[str, str] = {}
    for m in re.finditer(r'name="(bvh_joint_transform_[^"]+)"[^>]*>([^<]+)</string>', txt):
        joint = m.group(1).replace("bvh_joint_transform_", "")
        result[joint] = m.group(2).strip()
    return result
