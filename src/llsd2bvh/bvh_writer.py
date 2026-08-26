# -*- coding: utf-8 -*-
"""BVH ライター。"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple

from .euler_math import llsd_to_bvh_deg


# BVH で使うデフォルト骨オフセット（skeleton にない場合の fallback）
# avatar_skeleton.xml の pos の親からの差分を OFFSET とするが、
# ルート以外の OFFSET は skeleton の pos 差分を再計算する必要がある。
# 簡易化: skeleton の pos をそのまま親からの OFFSET として扱うのではなく、
# skeleton の pos (pivot 相対) を OFFSET に用いる。
# avatar_skeleton.xml の各 bone pos は親 pivot からの相対なので、そのまま使える。

# SL標準 階層（avatar_skeleton.xml の親子に基づくが、一部フラット化して BVH 互換に）
# mPelvis を ROOT とし、skeleton の親子をそのまま再帰出力する。


def _format_float(v: float) -> str:
    # BVHは小数6桁程度で十分、不要な末尾0を除く
    s = f"{v:.6f}"
    # 去除 trailing zeros
    if "." in s:
        s = s.rstrip("0").rstrip(".")
        if s == "-0":
            s = "0"
        if s == "":
            s = "0"
    return s


def write_bvh(
    joints_data: Dict[str, Dict],
    bones: Dict[str, Dict],
    out_path: str | Path,
    frame_time: float = 0.0333333,
    units: str | None = None,
    sl_compat: bool | None = None,
    include_face: bool = False,
    include_tail: bool = False,
) -> Path:
    """BVH ファイルを書き出す。

    joints_data: llsd_parser の出力 {joint: {rotation, position}}
    bones: skeleton.load_skeleton の出力（フィルタ済み）
    units/sl_compat が None の場合は mPelvis の位置有無で自動判定:
      位置あり (>|1e-6|) → inch + Frames:2、位置なし → meter + Frames:1
    明示指定時は指定値を優先。
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 自動判定用に mPelvis 位置を取得（閾値 1e-6）
    _pelvis_pos_raw = (0.0, 0.0, 0.0)
    if "mPelvis" in joints_data:
        _pelvis_pos_raw = joints_data["mPelvis"].get("position", (0.0, 0.0, 0.0))
    _has_pos = any(abs(v) > 1e-6 for v in _pelvis_pos_raw)
    # None の場合のみ自動
    if units is None:
        units = "inch" if _has_pos else "meter"
    if sl_compat is None:
        sl_compat = True if _has_pos else False

    # 階層構築: canonical BVH_HIERARCHY に基づく
    from .skeleton import get_bvh_order, BVH_HIERARCHY

    root_name = "mPelvis"
    if root_name not in bones:
        for name, data in bones.items():
            if data["parent"] is None or data["parent"] not in bones:
                root_name = name
                break

    output_bones = set(bones.keys())
    order: List[str] = get_bvh_order(bones, root=root_name)
    # BVH_HIERARCHY に含まれないが存在するボーン（例: 追加の顔ボーン）があれば末尾に追加
    for name in list(output_bones):
        if name not in order:
            parent = bones[name].get("parent")
            if parent in output_bones:
                order.append(name)

    # OFFSET は skeleton の pos を親からの相対として使う
    # avatar_skeleton.xml の pos は親 pivot からの相対なので、親の pos との差ではない
    # 正確には pos をそのまま OFFSET にするのが Viewer の内部表現に近い
    # 単位変換: meter -> inch (SL) は 39.3701 倍
    scale = 1.0
    if units == "inch":
        scale = 39.37008

    # MOTION データ生成
    # ROOT は 6ch (Xpos Ypos Zpos Zrot Xrot Yrot) – SL慣例 Z X Y
    # JOINT は 3ch (Zrot Xrot Yrot) – 同上
    # ここでは Viewer の bvh_joint_transform が未考慮なため、Z X Y 順で統一
    # LLSD rotation (VX,VY,VZ) -> BVH (Z,X,Y) = (VZ,VX,VY)
    # 位置は LLSD pos (VX,VY,VZ) -> BVH (Xpos,Ypos,Zpos) は (VY,VZ,VX) の Y Z X 入替がViewerのBVH出力だが、
    # MVPでは (VX,VY,VZ) を (X,Y,Z) としてそのまま使う。Pelvis の pos が申告と一致するように調整するなら Y Z X にする必要あり。
    # 申告では file pos [-0.19,0.75,0.389] vs ユーザ 0.39,0.75,-0.19 → file は [Z,Y,X] 入替に見えるため、
    # 再現性を考慮し Pelvis pos は申告通りに file の [0],[1],[2] を [X,Y,Z] として扱わず、file そのままを BVH X,Y,Z にする
    # → ここでは file pos をそのまま Xpos,Ypos,Zpos に出力（単位変換のみ）。

    # Joint ごとの BVH deg を計算（Headのみ逆巡回Fix）
    bvh_rot: Dict[str, Tuple[float, float, float]] = {}
    for name in order:
        rot = (0.0, 0.0, 0.0)
        if name in joints_data:
            rot = joints_data[name].get("rotation", (0.0, 0.0, 0.0))
        bvh_rot[name] = tuple(llsd_to_bvh_deg(name, rot, order="ZXY"))

    # ROOT 位置 – Variant B (X=VY, Y=VZ, Z=VX) が Viewerで Up→Y, Left→X, Forward→Z と一致することを inch_2f で検証
    # LLSD X=前, Y=左, Z=上 → BVH Xpos=左(Y), Ypos=上(Z), Zpos=前(X)
    pelvis_pos = (0.0, 0.0, 0.0)
    if "mPelvis" in joints_data:
        pelvis_pos = joints_data["mPelvis"].get("position", (0.0, 0.0, 0.0))
    # 位置SWAP: (Xpos, Ypos, Zpos) = (VY, VZ, VX)
    pelvis_pos_swapped = (pelvis_pos[1], pelvis_pos[2], pelvis_pos[0])
    pelvis_pos_scaled = tuple(v * scale for v in pelvis_pos_swapped)
    # Pelvis 回転も BVH Z X Y で
    pelvis_rot = bvh_rot.get(root_name, (0.0, 0.0, 0.0))

    # チャネル数: ROOT 6 + (n-1)*3
    num_channels = 6 + (len(order) - 1) * 3 if order else 0

    # 1フレーム（または sl_compat で2フレーム）
    motion_lines: List[List[float]] = []
    frame_values: List[float] = []
    # ROOT: Xpos Ypos Zpos Zrot Xrot Yrot
    frame_values.extend([pelvis_pos_scaled[0], pelvis_pos_scaled[1], pelvis_pos_scaled[2]])
    frame_values.extend([pelvis_rot[0], pelvis_rot[1], pelvis_rot[2]])
    for name in order:
        if name == root_name:
            continue
        rot = bvh_rot.get(name, (0.0, 0.0, 0.0))
        frame_values.extend([rot[0], rot[1], rot[2]])
    motion_lines.append(frame_values)
    if sl_compat:
        # 1フレーム目を基準フレーム（全0）として複製、2フレーム目が実ポーズ がSLの慣例
        # Viewer は 1フレーム目の非ゼロ差分で joint 有効判定するため、基準フレームは 0 にする
        base = [0.0] * num_channels
        motion_lines.insert(0, base)

    frames = len(motion_lines)

    # 書き出し
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("HIERARCHY\n")
        # 階層再帰
        def write_joint(name: str, depth: int, is_root: bool = False):
            indent = "\t" * depth
            bone = bones[name]
            pos = bone["pos"]
            # OFFSET は bone pos のまま（avatar_skeleton の pos は親からの相対）
            # 単位変換も適用
            off_x = pos[0] * scale
            off_y = pos[1] * scale
            off_z = pos[2] * scale
            if is_root:
                f.write(f"{indent}ROOT {name}\n")
            else:
                f.write(f"{indent}JOINT {name}\n")
            f.write(f"{indent}{{\n")
            f.write(f"{indent}\tOFFSET {_format_float(off_x)} {_format_float(off_y)} {_format_float(off_z)}\n")
            if is_root:
                f.write(f"{indent}\tCHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n")
            else:
                f.write(f"{indent}\tCHANNELS 3 Zrotation Xrotation Yrotation\n")
            # 子を出力: canonical 優先
            children = [c for c in BVH_HIERARCHY.get(name, []) if c in output_bones]
            # 追加の子（canonical にないが skeleton にある）を追記
            extra = [c for c in bone.get("children", []) if c in output_bones and c not in children]
            for child in children + extra:
                write_joint(child, depth + 1)
            # 葉なら End Site
            if not children:
                f.write(f"{indent}\tEnd Site\n")
                f.write(f"{indent}\t{{\n")
                # End Site OFFSET は bone の end から推定。avatar_skeleton の end を使う
                end_vec = bone.get("element").get("end", "0 0 0.1") if bone.get("element") is not None else "0 0 0.1"
                try:
                    ex, ey, ez = [float(v) * scale for v in end_vec.split()]
                except Exception:
                    ex, ey, ez = 0.0, 0.0, 0.1 * scale
                # 末端がない場合は上方向へ少し延長
                if abs(ex) < 1e-9 and abs(ey) < 1e-9 and abs(ez) < 1e-9:
                    ez = 0.05 * scale if scale == 1 else 2.0
                f.write(f"{indent}\t\tOFFSET {_format_float(ex)} {_format_float(ey)} {_format_float(ez)}\n")
                f.write(f"{indent}\t}}\n")
            f.write(f"{indent}}}\n")

        write_joint(root_name, 0, is_root=True)

        f.write("MOTION\n")
        f.write(f"Frames: {frames}\n")
        f.write(f"Frame Time: {_format_float(frame_time)}\n")
        for line in motion_lines:
            f.write(" ".join(_format_float(v) for v in line) + "\n")

    return out_path
