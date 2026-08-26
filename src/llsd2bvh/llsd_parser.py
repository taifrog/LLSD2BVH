# -*- coding: utf-8 -*-
"""LLSD XML Poser ファイルのパース。

Firestorm/Aperture Viewer の Poser が出力する LLSD XML は
<llsd><map><key>joint</key><map><key>rotation</key><array>3×real</array> ... と並ぶ。
rotation は LLQuaternion.getEulerAngles 由来の roll(X), pitch(Y), yaw(Z) [rad]。
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any


def parse_llsd_xml(path: str | Path) -> Dict[str, Any]:
    """LLSD XML をパースして {joint: {rotation, position, scale, ...}, _meta: {...}} を返す。

    rotation: tuple[float,float,float] rad (roll,pitch,yaw) に対応する [0,1,2]
    position: tuple[float,float,float] meter (VX,VY,VZ)
    """
    p = Path(path)
    tree = ET.parse(str(p))
    root = tree.getroot()
    # <llsd> 直下の <map>
    map_elem = root.find("map")
    if map_elem is None:
        # まれに <llsd> 直下が <map> でない場合
        map_elem = root
    result: Dict[str, Any] = {}
    meta: Dict[str, Any] = {}
    # <map> の子は key, value の交互
    children = list(map_elem)
    i = 0
    while i < len(children):
        key_elem = children[i]
        if key_elem.tag != "key":
            i += 1
            continue
        key = (key_elem.text or "").strip()
        if i + 1 >= len(children):
            break
        val_elem = children[i + 1]
        i += 2
        if key in ("version", "startFromTeePose"):
            # <map><key>value</key><integer|boolean>...
            inner_map = val_elem
            # inner_map は <map> かつ <key>value</key> を含む
            for j in range(0, len(inner_map), 2):
                if j + 1 >= len(inner_map):
                    break
                k2 = inner_map[j]
                v2 = inner_map[j + 1]
                if k2.tag == "key" and (k2.text or "").strip() == "value":
                    if v2.tag == "integer":
                        meta[key] = int((v2.text or "0").strip())
                    elif v2.tag == "boolean":
                        txt = (v2.text or "0").strip()
                        meta[key] = txt == "1" or txt.lower() == "true"
                    else:
                        meta[key] = (v2.text or "").strip()
            continue
        if val_elem.tag != "map":
            # enabled だけの簡易 joint (enabled 0) などはスキップ
            continue
        # joint の map
        joint_data: Dict[str, Any] = {}
        # joint map の子も key/value 交互
        inner = list(val_elem)
        j = 0
        while j < len(inner):
            k_elem = inner[j]
            if k_elem.tag != "key":
                j += 1
                continue
            k = (k_elem.text or "").strip()
            if j + 1 >= len(inner):
                break
            v_elem = inner[j + 1]
            j += 2
            if k == "enabled":
                txt = (v_elem.text or "0").strip()
                joint_data["enabled"] = txt == "1" or txt.lower() == "true"
            elif k == "jointBaseRotationIsZero":
                txt = (v_elem.text or "0").strip()
                joint_data["jointBaseRotationIsZero"] = txt == "1" or txt.lower() == "true"
            elif k in ("rotation", "position", "scale"):
                arr = v_elem  # <array>
                vals = []
                for real_elem in arr.findall("real"):
                    try:
                        vals.append(float((real_elem.text or "0").strip()))
                    except ValueError:
                        vals.append(0.0)
                # 3要素に正規化
                while len(vals) < 3:
                    vals.append(0.0)
                joint_data[k] = tuple(vals[:3])
            else:
                # 未知のキーは無視
                pass
        # デフォルト補完
        joint_data.setdefault("rotation", (0.0, 0.0, 0.0))
        joint_data.setdefault("position", (0.0, 0.0, 0.0))
        joint_data.setdefault("scale", (0.0, 0.0, 0.0))
        joint_data.setdefault("enabled", True)
        joint_data.setdefault("jointBaseRotationIsZero", True)
        result[key] = joint_data
    result["_meta"] = meta
    return result


def rotation_rad_to_deg(rotation_rad: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(math.degrees(v) for v in rotation_rad)
