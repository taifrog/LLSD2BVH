# -*- coding: utf-8 -*-
"""Forward Kinematics for BVH stick figure."""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .bvh_parser import BvhData, BvhJoint


def _mat_identity() -> List[List[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat_mult(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    res = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            s = 0.0
            for k in range(4):
                s += a[i][k] * b[k][j]
            res[i][j] = s
    return res


def _mat_translate(x: float, y: float, z: float) -> List[List[float]]:
    m = _mat_identity()
    m[0][3] = x
    m[1][3] = y
    m[2][3] = z
    return m


def _mat_rot_x(deg: float) -> List[List[float]]:
    rad = math.radians(deg)
    c = math.cos(rad); s = math.sin(rad)
    return [
        [1, 0, 0, 0],
        [0, c, -s, 0],
        [0, s, c, 0],
        [0, 0, 0, 1],
    ]


def _mat_rot_y(deg: float) -> List[List[float]]:
    rad = math.radians(deg)
    c = math.cos(rad); s = math.sin(rad)
    return [
        [c, 0, s, 0],
        [0, 1, 0, 0],
        [-s, 0, c, 0],
        [0, 0, 0, 1],
    ]


def _mat_rot_z(deg: float) -> List[List[float]]:
    rad = math.radians(deg)
    c = math.cos(rad); s = math.sin(rad)
    return [
        [c, -s, 0, 0],
        [s, c, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ]


def _transform_point(mat: List[List[float]], p: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x, y, z = p
    nx = mat[0][0]*x + mat[0][1]*y + mat[0][2]*z + mat[0][3]
    ny = mat[1][0]*x + mat[1][1]*y + mat[1][2]*z + mat[1][3]
    nz = mat[2][0]*x + mat[2][1]*y + mat[2][2]*z + mat[2][3]
    return (nx, ny, nz)


_SL_COMPAT_MAP = {
    "Zrotation": "X",
    "Xrotation": "Y",
    "Yrotation": "Z",
}

def compute_frame_positions(bvh: BvhData, frame_idx: int, rotation_mode: str = "sl_compat") -> Tuple[Dict[str, Tuple[float, float, float]], List[Tuple[Tuple[float,float,float], Tuple[float,float,float]]]]:
    """指定フレームのワールド座標を算出。

    rotation_mode:
        standard   : チャネルラベル通り Z->Z, X->X, Y->Y（BVH仕様準拠）
        sl_compat  : SL互換 Z->X, X->Y, Y->Z — MuMuDance等の -46°yaw が
                     Y値に格納されているケースで前傾(42°)を解消し直立(0.5°)に
                     復元。既定は sl_compat（本ツール出力BVHを想定）。

    Returns:
        positions: {joint_name: (x,y,z)}  world positions (EndSite含む)
        bones: [(parent_pos, child_pos), ...]  棒の両端
    """
    if not (0 <= frame_idx < bvh.num_frames):
        raise IndexError(f"frame_idx {frame_idx} out of range 0..{bvh.num_frames-1}")
    row = bvh.frames[frame_idx]
    # Map (joint, channel) -> value
    channel_values: Dict[Tuple[str, str], float] = {}
    for (jname, ch), val in zip(bvh.channel_order, row):
        channel_values[(jname, ch)] = val

    positions: Dict[str, Tuple[float,float,float]] = {}
    bones: List[Tuple[Tuple[float,float,float], Tuple[float,float,float]]] = []

    def recurse(joint: BvhJoint, parent_mat: List[List[float]]):
        # Build local matrix
        # 1. Offset translation
        ox, oy, oz = joint.offset
        # For root, add position channels if present
        # Determine root position
        px = channel_values.get((joint.name, "Xposition"), 0.0)
        py = channel_values.get((joint.name, "Yposition"), 0.0)
        pz = channel_values.get((joint.name, "Zposition"), 0.0)
        has_pos = any(k == (joint.name, c) for c in ("Xposition","Yposition","Zposition") for k in channel_values)
        # But only root typically has position; check if any position channel exists for this joint
        # If this joint has position channels, treat translation as (pos + offset) ? 
        # BVH spec: local = T(offset + motion_pos?) For root, offset is added.
        # We'll do: local translation = offset + motion_pos (if has_pos), else just offset
        if has_pos:
            # check existence individually; if channel_order includes position, use values
            # For joints without position channels, px/py/pz will be 0
            # So add offset
            tx = ox + px if (joint.name, "Xposition") in channel_values else ox
            ty = oy + py if (joint.name, "Yposition") in channel_values else oy
            tz = oz + pz if (joint.name, "Zposition") in channel_values else oz
        else:
            tx, ty, tz = ox, oy, oz

        local = _mat_translate(tx, ty, tz)

        # Rotations in channel order sequence
        # For joints with CHANNELS like "Zrotation Xrotation Yrotation", apply in that order
        for ch in joint.channels:
            if "rotation" not in ch:
                continue
            val = channel_values.get((joint.name, ch), 0.0)
            # SL互換では チャネル→軸 を巡回 (Z->X, X->Y, Y->Z)
            if rotation_mode == "sl_compat":
                axis = _SL_COMPAT_MAP.get(ch, ch[0])
            else:
                axis = ch[0]  # Z/X/Y
            if axis == "Z":
                local = _mat_mult(local, _mat_rot_z(val))
            elif axis == "X":
                local = _mat_mult(local, _mat_rot_x(val))
            elif axis == "Y":
                local = _mat_mult(local, _mat_rot_y(val))

        world = _mat_mult(parent_mat, local)
        # Joint world position is transform of origin (0,0,0) by world matrix
        pos = _transform_point(world, (0.0, 0.0, 0.0))
        positions[joint.name] = pos

        # Parent position for bone line is parent joint pos (if not root)
        # We'll compute bones after recursion: each child connected to parent pos
        for child in joint.children:
            # Recurse first to get child's position? Need parent pos already.
            # We'll recurse then create bone segment parent->child
            recurse(child, world)
            child_pos = positions[child.name]
            bones.append((pos, child_pos))

    identity = _mat_identity()
    recurse(bvh.root, identity)
    return positions, bones


def compute_all_frames(bvh: BvhData, rotation_mode: str = "sl_compat") -> List[Dict[str, Tuple[float,float,float]]]:
    """全フレームの positions を返す（テスト/プレビュー用）。"""
    result = []
    for i in range(bvh.num_frames):
        pos, _ = compute_frame_positions(bvh, i, rotation_mode=rotation_mode)
        result.append(pos)
    return result
