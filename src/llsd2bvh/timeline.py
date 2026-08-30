# -*- coding: utf-8 -*-
"""タイムライン・補間ロジック。

- duration (0 < D <= 60), 最小フレームタイム 0.01
- t0=0, t_last=D 強制
- Slerp による回転補間、位置は lerp
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple

MIN_FRAME_TIME = 0.01
MAX_DURATION = 60.0
EPS = 1e-6
UNIFORM_EPS = 1e-4


def _normalize_quat(q: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    return (w / n, x / n, y / n, z / n)


def euler_to_quat(roll: float, pitch: float, yaw: float) -> Tuple[float, float, float, float]:
    """Euler rad (VX=roll, VY=pitch, VZ=yaw) -> quaternion.
    Order ZYX (yaw*pitch*roll) を仮定: q = qz * qy * qx
    """
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return _normalize_quat((w, x, y, z))


def quat_to_euler(q: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
    """quaternion -> Euler rad (roll, pitch, yaw) ZYX."""
    w, x, y, z = _normalize_quat(q)
    # roll (x-axis)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    # pitch (y-axis)
    sinp = 2.0 * (w * y - z * x)
    sinp = max(-1.0, min(1.0, sinp))
    pitch = math.asin(sinp)
    # yaw (z-axis)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return (roll, pitch, yaw)


def quat_slerp(q1: Tuple[float, float, float, float], q2: Tuple[float, float, float, float], t: float) -> Tuple[float, float, float, float]:
    """球面線形補間。"""
    q1 = _normalize_quat(q1)
    q2 = _normalize_quat(q2)
    dot = q1[0] * q2[0] + q1[1] * q2[1] + q1[2] * q2[2] + q1[3] * q2[3]
    # 最短経路
    if dot < 0.0:
        q2 = (-q2[0], -q2[1], -q2[2], -q2[3])
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        # 線形補間で近似
        w = q1[0] + t * (q2[0] - q1[0])
        x = q1[1] + t * (q2[1] - q1[1])
        y = q1[2] + t * (q2[2] - q1[2])
        z = q1[3] + t * (q2[3] - q1[3])
        return _normalize_quat((w, x, y, z))
    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    w = s0 * q1[0] + s1 * q2[0]
    x = s0 * q1[1] + s1 * q2[1]
    y = s0 * q1[2] + s1 * q2[2]
    z = s0 * q1[3] + s1 * q2[3]
    return _normalize_quat((w, x, y, z))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolate_joint_data(data_a: Dict, data_b: Dict, alpha: float) -> Dict:
    """2フレーム間の補間。rotationはSlerp、positionはlerp。"""
    if alpha <= 0:
        return data_a
    if alpha >= 1:
        return data_b
    result: Dict = {}
    # union of joints
    keys = set(data_a.keys()) | set(data_b.keys())
    keys.discard("_meta")
    for k in keys:
        ja = data_a.get(k, {})
        jb = data_b.get(k, {})
        rot_a = ja.get("rotation", (0.0, 0.0, 0.0))
        rot_b = jb.get("rotation", (0.0, 0.0, 0.0))
        # Slerp
        q1 = euler_to_quat(rot_a[0], rot_a[1], rot_a[2])
        q2 = euler_to_quat(rot_b[0], rot_b[1], rot_b[2])
        qm = quat_slerp(q1, q2, alpha)
        rot_m = quat_to_euler(qm)
        # position: only meaningful for mPelvis, but lerp all
        pos_a = ja.get("position", (0.0, 0.0, 0.0))
        pos_b = jb.get("position", (0.0, 0.0, 0.0))
        pos_m = tuple(_lerp(pos_a[i], pos_b[i], alpha) for i in range(3))
        # build
        entry = {}
        entry["rotation"] = rot_m
        entry["position"] = pos_m
        # keep enabled etc. lerp not needed, take a if alpha<0.5 else b for booleans
        entry["enabled"] = ja.get("enabled", True) if alpha < 0.5 else jb.get("enabled", True)
        entry["jointBaseRotationIsZero"] = ja.get("jointBaseRotationIsZero", True) if alpha < 0.5 else jb.get("jointBaseRotationIsZero", True)
        # scale lerp (rarely used)
        if "scale" in ja or "scale" in jb:
            sc_a = ja.get("scale", (0.0, 0.0, 0.0))
            sc_b = jb.get("scale", (0.0, 0.0, 0.0))
            entry["scale"] = tuple(_lerp(sc_a[i], sc_b[i], alpha) for i in range(3))
        result[k] = entry
    # meta blend (take first)
    if "_meta" in data_a:
        result["_meta"] = data_a["_meta"]
    elif "_meta" in data_b:
        result["_meta"] = data_b["_meta"]
    return result


def compute_timeline_frames(
    duration: float,
    keyframes_data: List[Dict],
    key_times: List[float],
) -> Tuple[float, List[Dict], int]:
    """タイムラインから均一フレーム列を算出。

    Args:
        duration: アニメーション秒数 (<=60)
        keyframes_data: 長さNのDictリスト
        key_times: 長さNの時刻リスト（0<=t<=duration、ソート済み、t0=0,t_last=D強制済みを想定）

    Returns:
        (frame_time, frames_data, num_inserted)
        frames_dataは補間済みの均一間隔フレーム列
    """
    n = len(keyframes_data)
    if n == 0:
        raise ValueError("no keyframes")
    # n は Tposeを除いたユーザフレーム数。duration D に対して
    # 全体を Tpose + n 点で n+1 フレームとみなし、Frame Time = D / n。
    # ここでは P1..Pn の n 点のみを扱い、Tposeは呼出側で先頭に追加される。
    # 均一時の gap は D/n ではなく、P1..Pn が dt..D に配置されるため gap = D/n（n>=2で D/(n) ?）
    # 例: n=1 D=3 -> dt=3, P1@3 ; n=2 D=3 -> dt=1.5, P1@1.5 P2@3
    if n == 1:
        dt = float(duration) / 1 if duration > 1e-9 else 0.0333333
        if dt < MIN_FRAME_TIME:
            dt = MIN_FRAME_TIME
        return (dt, keyframes_data, 0)
    if n == 2:
        dt = float(duration) / 2 if duration > 1e-9 else float(duration)
        if dt < MIN_FRAME_TIME:
            dt = MIN_FRAME_TIME
        return (dt, keyframes_data, 0)

    # n >= 3
    # 均一判定
    gaps = [key_times[i + 1] - key_times[i] for i in range(n - 1)]
    # 全て正であること
    if any(g <= EPS for g in gaps):
        # 重複や逆順は均一とみなさず、補間対象
        uniform = False
    else:
        min_gap = min(gaps)
        max_gap = max(gaps)
        uniform = (max_gap - min_gap) <= UNIFORM_EPS

    if uniform:
        dt = gaps[0]
        if dt < MIN_FRAME_TIME:
            dt = MIN_FRAME_TIME
        # フレームはそのまま
        return (dt, keyframes_data, 0)

    # 非均一: 最小間隔から総フレーム数を算出
    min_gap = min(gaps) if gaps else duration
    if min_gap < MIN_FRAME_TIME:
        min_gap = MIN_FRAME_TIME
    # 総フレーム数 F = ceil(D / min_gap) + 1
    import math as _math
    f_est = _math.ceil(duration / min_gap) + 1
    # dt を再算出して端点を合わせる
    dt = duration / (f_est - 1) if f_est > 1 else duration
    if dt < MIN_FRAME_TIME:
        dt = MIN_FRAME_TIME
        f_est = int(round(duration / dt)) + 1
        dt = duration / (f_est - 1) if f_est > 1 else duration
    # 上限チェック（SL的に大きすぎないか）
    # 6001 frame @60s/0.01 が上限想定。超える場合は dt を 0.01 にクランプ済みなので OK

    # グリッド生成
    grid_times = [i * dt for i in range(f_est)]
    # 浮動誤差で最後が D にならない場合を補正
    if grid_times:
        grid_times[-1] = float(duration)

    frames: List[Dict] = []
    # 各グリッド時刻を補間
    for t in grid_times:
        # t が key_times の範囲内にあるはず（0..D）
        # 包含する区間を探す
        # key_times はソート済み
        # 末尾はそのまま
        if t <= key_times[0] + EPS:
            frames.append(keyframes_data[0])
            continue
        if t >= key_times[-1] - EPS:
            frames.append(keyframes_data[-1])
            continue
        # 線形探索（N<=20 なので十分）
        idx = 0
        for i in range(n - 1):
            if key_times[i] - EPS <= t <= key_times[i + 1] + EPS:
                idx = i
                break
        t0 = key_times[idx]
        t1 = key_times[idx + 1]
        span = t1 - t0
        if span < EPS:
            alpha = 0.0
        else:
            alpha = (t - t0) / span
            alpha = max(0.0, min(1.0, alpha))
        # alpha が 0/1 のときは補間せず直接返す（誤差回避）
        if alpha <= 1e-9:
            frames.append(keyframes_data[idx])
        elif alpha >= 1 - 1e-9:
            frames.append(keyframes_data[idx + 1])
        else:
            frames.append(interpolate_joint_data(keyframes_data[idx], keyframes_data[idx + 1], alpha))

    num_inserted = len(frames) - n
    return (dt, frames, num_inserted)
