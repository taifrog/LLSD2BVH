# -*- coding: utf-8 -*-
"""avatar_skeleton.xml の読み込みと階層構築。"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple


def _parse_vec(s: str) -> Tuple[float, float, float]:
    parts = (s or "0 0 0").strip().split()
    vals = []
    for p in parts:
        try:
            vals.append(float(p))
        except ValueError:
            vals.append(0.0)
    while len(vals) < 3:
        vals.append(0.0)
    return tuple(vals[:3])


def load_skeleton(xml_path: str | Path) -> Dict[str, Dict]:
    """avatar_skeleton.xml を読み、{name: {pos, pivot, parent, children, aliases}} を返す。"""
    path = Path(xml_path)
    tree = ET.parse(str(path))
    root = tree.getroot()
    bones: Dict[str, Dict] = {}
    parent_map: Dict[str, str | None] = {}

    # 再帰で bone 要素を辿る
    def walk(elem, parent_name: str | None):
        for child in elem.findall("bone"):
            name = child.get("name")
            if not name:
                continue
            pos = _parse_vec(child.get("pos", "0 0 0"))
            pivot = _parse_vec(child.get("pivot", "0 0 0"))
            aliases = (child.get("aliases") or "").split()
            bones[name] = {
                "name": name,
                "pos": pos,
                "pivot": pivot,
                "aliases": aliases,
                "parent": parent_name,
                "children": [],
                "element": child,
            }
            parent_map[name] = parent_name
            walk(child, name)

    # <linden_skeleton> 直下の bone から開始
    for bone_elem in root.findall("bone"):
        name = bone_elem.get("name")
        if not name:
            continue
        pos = _parse_vec(bone_elem.get("pos", "0 0 0"))
        pivot = _parse_vec(bone_elem.get("pivot", "0 0 0"))
        aliases = (bone_elem.get("aliases") or "").split()
        bones[name] = {
            "name": name,
            "pos": pos,
            "pivot": pivot,
            "aliases": aliases,
            "parent": None,
            "children": [],
            "element": bone_elem,
        }
        walk(bone_elem, name)

    # children リスト構築
    for name, data in bones.items():
        parent = data["parent"]
        if parent and parent in bones:
            bones[parent]["children"].append(name)

    return bones


# デフォルトで除外するグループ
EXCLUDE_BY_DEFAULT = {
    "mFace",  # 顔
    "mTail",  # 尻尾
}


def filter_skeleton(bones: Dict[str, Dict], include_face: bool = False, include_tail: bool = False, include_hands: bool = True, include_collision: bool = False) -> Dict[str, Dict]:
    """不要なボーンを除外したコピーを返す。"""
    result: Dict[str, Dict] = {}
    for name, data in bones.items():
        # 明示的なカテゴリ
        if name.startswith("mFace"):
            if not include_face:
                continue
            result[name] = data
            continue
        if name.startswith("mTail"):
            if not include_tail:
                continue
            result[name] = data
            continue
        if name.startswith("mHand"):
            if not include_hands:
                continue
            result[name] = data
            continue
        support = (data.get("element").get("support") if data.get("element") is not None else "")
        if support == "base":
            result[name] = data
            continue
        # extended かつ base/hand/face/tail 以外 (例: mSpine*) は除外
        continue
    return result


# BVH 用 canonical 階層（base 26 + 手）。親子は Second Life 標準に準拠。
BVH_HIERARCHY: Dict[str, List[str]] = {
    "mPelvis": ["mTorso", "mHipLeft", "mHipRight"],
    "mTorso": ["mChest"],
    "mChest": ["mNeck", "mCollarLeft", "mCollarRight"],
    "mNeck": ["mHead"],
    "mHead": ["mSkull", "mEyeLeft", "mEyeRight"],
    "mCollarLeft": ["mShoulderLeft"],
    "mShoulderLeft": ["mElbowLeft"],
    "mElbowLeft": ["mWristLeft"],
    "mWristLeft": ["mHandThumb1Left", "mHandIndex1Left", "mHandMiddle1Left", "mHandRing1Left", "mHandPinky1Left"],
    "mCollarRight": ["mShoulderRight"],
    "mShoulderRight": ["mElbowRight"],
    "mElbowRight": ["mWristRight"],
    "mWristRight": ["mHandThumb1Right", "mHandIndex1Right", "mHandMiddle1Right", "mHandRing1Right", "mHandPinky1Right"],
    "mHipLeft": ["mKneeLeft"],
    "mKneeLeft": ["mAnkleLeft"],
    "mAnkleLeft": ["mFootLeft"],
    "mFootLeft": ["mToeLeft"],
    "mHipRight": ["mKneeRight"],
    "mKneeRight": ["mAnkleRight"],
    "mAnkleRight": ["mFootRight"],
    "mFootRight": ["mToeRight"],
    # 手の指はチェーン
    "mHandThumb1Left": ["mHandThumb2Left"],
    "mHandThumb2Left": ["mHandThumb3Left"],
    "mHandIndex1Left": ["mHandIndex2Left"],
    "mHandIndex2Left": ["mHandIndex3Left"],
    "mHandMiddle1Left": ["mHandMiddle2Left"],
    "mHandMiddle2Left": ["mHandMiddle3Left"],
    "mHandRing1Left": ["mHandRing2Left"],
    "mHandRing2Left": ["mHandRing3Left"],
    "mHandPinky1Left": ["mHandPinky2Left"],
    "mHandPinky2Left": ["mHandPinky3Left"],
    "mHandThumb1Right": ["mHandThumb2Right"],
    "mHandThumb2Right": ["mHandThumb3Right"],
    "mHandIndex1Right": ["mHandIndex2Right"],
    "mHandIndex2Right": ["mHandIndex3Right"],
    "mHandMiddle1Right": ["mHandMiddle2Right"],
    "mHandMiddle2Right": ["mHandMiddle3Right"],
    "mHandRing1Right": ["mHandRing2Right"],
    "mHandRing2Right": ["mHandRing3Right"],
    "mHandPinky1Right": ["mHandPinky2Right"],
    "mHandPinky2Right": ["mHandPinky3Right"],
}


def get_bvh_order(bones: Dict[str, Dict], root: str = "mPelvis") -> List[str]:
    """BVH_HIERARCHY に基づく DFS 順。存在しないボーンはスキップ。"""
    order: List[str] = []
    visited = set()

    def dfs(name: str):
        if name not in bones or name in visited:
            return
        visited.add(name)
        order.append(name)
        for child in BVH_HIERARCHY.get(name, []):
            if child in bones:
                dfs(child)
        # BVH_HIERARCHY にない子（拡張）があれば skeleton の children も辿る
        for child in bones[name].get("children", []):
            if child not in visited and child in bones and child not in BVH_HIERARCHY.get(name, []):
                dfs(child)

    dfs(root)
    return order


def get_hierarchy_order(bones: Dict[str, Dict], root: str = "mPelvis") -> List[str]:
    """DFS順で階層順リストを返す。"""
    order: List[str] = []

    def dfs(name: str):
        if name not in bones:
            return
        order.append(name)
        for child in bones[name]["children"]:
            # フィルタされた子はスキップ
            if child in bones:
                dfs(child)

    if root in bones:
        dfs(root)
    else:
        # ルートがない場合は全てを返す
        for name in bones:
            if bones[name]["parent"] is None or bones[name]["parent"] not in bones:
                dfs(name)
    return order
