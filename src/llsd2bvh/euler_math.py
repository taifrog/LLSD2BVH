# -*- coding: utf-8 -*-
"""Euler 変換ユーティリティ。

LLSD rotation は roll(VX), pitch(VY), yaw(VZ) [rad]。
BVH は度数。MVPでは 1:1 で rad→deg 変換のみ行う。
将来的に per-joint swap/negate を考慮する場合はここで matrix 経由の変換を追加。
"""
from __future__ import annotations

import math
from typing import Tuple


def rad_to_deg(rad: float) -> float:
    return rad * 180.0 / math.pi


def llsd_rotation_to_bvh_deg(rotation_rad: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """LLSD (VX,VY,VZ) rad → BVH deg (X,Y,Z) としてそのまま返す。"""
    return tuple(rad_to_deg(v) for v in rotation_rad)


def bvh_deg_for_channels(rotation_rad: Tuple[float, float, float], order: str = "ZXY") -> Tuple[float, ...]:
    """指定チャネル順でBVH用deg値を返す。

    order が "ZXY" の場合は (deg(Z), deg(X), deg(Y)) の順。
    rotation_rad は (VX=roll, VY=pitch, VZ=yaw) に対応。
    本MVPでは VX→X, VY→Y, VZ→Z の直接マッピングと仮定。
    """
    deg = llsd_rotation_to_bvh_deg(rotation_rad)
    # deg = (degX, degY, degZ)  where X=VX, Y=VY, Z=VZ
    mapping = {"X": 0, "Y": 1, "Z": 2}
    out = []
    for ch in order:
        ch = ch.upper()
        if ch in mapping:
            out.append(deg[mapping[ch]])
        else:
            raise ValueError(f"Unknown channel {ch}")
    return tuple(out)


# Head/Neck/Chest/Torso/Collar/Shoulder/Elbow/Wrist/Hip/Knee/Ankle/Pelvis Fix
# 検証済み: Head, Neck, Chest, Torso, CollarL/R, Shoulder-Wrist, HipL, Pelvis Rot(UD->VY, LR->VZ, Roll->VX)
# BVH(Z,X,Y)=(VX,VY,VZ) でViewerと一致
_HEAD_FIX_JOINTS = {
    "mHead", "mNeck", "mChest", "mTorso",
    "mCollarLeft", "mCollarRight",
    "mShoulderLeft", "mShoulderRight",
    "mElbowLeft", "mElbowRight",
    "mWristLeft", "mWristRight",
    "mHipLeft", "mHipRight",
    "mKneeLeft", "mKneeRight",
    "mAnkleLeft", "mAnkleRight",
    "mPelvis",
}


def llsd_to_bvh_deg(joint: str, rotation_rad: Tuple[float, float, float], order: str = "ZXY") -> Tuple[float, ...]:
    """jointを考慮したLLSD→BVH deg変換。Headのみ逆巡回を適用。"""
    if joint in _HEAD_FIX_JOINTS:
        dx = rad_to_deg(rotation_rad[0])
        dy = rad_to_deg(rotation_rad[1])
        dz = rad_to_deg(rotation_rad[2])
        # BVH(Z,X,Y)=(VX,VY,VZ)
        bvh_z = dx
        bvh_x = dy
        bvh_y = dz
        mapping = {"Z": bvh_z, "X": bvh_x, "Y": bvh_y}
        return tuple(mapping[ch.upper()] for ch in order)
    return bvh_deg_for_channels(rotation_rad, order)
