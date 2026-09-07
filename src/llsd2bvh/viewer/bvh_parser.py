# -*- coding: utf-8 -*-
"""BVH パーサ（出力BVH専用）。HIERARCHY + MOTION を解析し FK用データを返す。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class BvhJoint:
    name: str
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    channels: List[str] = field(default_factory=list)
    children: List["BvhJoint"] = field(default_factory=list)
    is_end_site: bool = False

    def __repr__(self) -> str:
        return f"BvhJoint({self.name}, offset={self.offset}, ch={self.channels}, children={len(self.children)})"


@dataclass
class BvhData:
    root: BvhJoint
    joints: Dict[str, BvhJoint]  # name -> joint (EndSite含む)
    frame_time: float
    frames: List[List[float]]  # frames x num_channels
    channel_order: List[Tuple[str, str]]  # [(joint_name, channel_name), ...] MOTION列順
    num_frames: int

    @property
    def num_channels(self) -> int:
        return len(self.channel_order)


def _tokenize(text: str) -> List[str]:
    # bracesを分離、End Site は2トークンで扱うがそのまま split
    text = text.replace("{", " { ").replace("}", " } ")
    # normalize line breaks
    return text.split()


def _parse_joint_block(name: str, tokens: List[str], idx: int) -> Tuple[BvhJoint, int]:
    """'{'直後から '}' までをパース。idxは '{' の次の位置。"""
    joint = BvhJoint(name=name)
    n = len(tokens)
    while idx < n:
        tok = tokens[idx]
        if tok == "}":
            idx += 1
            break
        elif tok == "OFFSET":
            # OFFSET x y z
            if idx + 3 >= n:
                raise ValueError("OFFSET requires 3 values")
            x = float(tokens[idx + 1]); y = float(tokens[idx + 2]); z = float(tokens[idx + 3])
            joint.offset = (x, y, z)
            idx += 4
        elif tok == "CHANNELS":
            if idx + 2 >= n:
                raise ValueError("CHANNELS requires count + names")
            count = int(tokens[idx + 1])
            ch = tokens[idx + 2: idx + 2 + count]
            joint.channels = ch
            idx += 2 + count
        elif tok == "JOINT":
            child_name = tokens[idx + 1]
            # next should be {
            if tokens[idx + 2] != "{":
                raise ValueError(f"Expected '{{' after JOINT {child_name}")
            child, idx = _parse_joint_block(child_name, tokens, idx + 3)
            joint.children.append(child)
        elif tok == "ROOT":
            # nested ROOT should not happen, but handle like JOINT
            child_name = tokens[idx + 1]
            if tokens[idx + 2] != "{":
                raise ValueError(f"Expected '{{' after ROOT {child_name}")
            child, idx = _parse_joint_block(child_name, tokens, idx + 3)
            joint.children.append(child)
        elif tok == "End":
            # Expect "Site" "{"
            if idx + 2 >= n or tokens[idx + 1] != "Site":
                raise ValueError("Expected 'Site' after 'End'")
            if tokens[idx + 2] != "{":
                raise ValueError("Expected '{' after End Site")
            idx += 3  # skip End Site {
            # Inside: OFFSET x y z, then }
            # allow extra whitespace / multiple OFFSET? spec says one
            end_offset = (0.0, 0.0, 0.0)
            while idx < n and tokens[idx] != "}":
                if tokens[idx] == "OFFSET":
                    x = float(tokens[idx + 1]); y = float(tokens[idx + 2]); z = float(tokens[idx + 3])
                    end_offset = (x, y, z)
                    idx += 4
                else:
                    idx += 1
            # consume }
            if idx < n and tokens[idx] == "}":
                idx += 1
            end_name = joint.name + "_EndSite"
            # Ensure uniqueness if multiple End Sites under same parent (rare, but use suffix)
            # For BVH, each joint has at most one End Site.
            end_joint = BvhJoint(name=end_name, offset=end_offset, channels=[], children=[], is_end_site=True)
            joint.children.append(end_joint)
        else:
            # unknown token, skip
            idx += 1
    return joint, idx


def parse_bvh(path: str | Path) -> BvhData:
    """BVHファイルをパースして BvhData を返す。"""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    tokens = _tokenize(text)
    if not tokens:
        raise ValueError("Empty BVH file")
    n = len(tokens)
    idx = 0
    # Find HIERARCHY
    if tokens[0] != "HIERARCHY":
        raise ValueError("BVH must start with HIERARCHY")
    idx = 1
    # Expect ROOT
    if idx >= n or tokens[idx] != "ROOT":
        raise ValueError("Expected ROOT after HIERARCHY")
    root_name = tokens[idx + 1]
    if tokens[idx + 2] != "{":
        raise ValueError("Expected '{' after ROOT name")
    root, idx = _parse_joint_block(root_name, tokens, idx + 3)

    # Find MOTION
    # tokens may have extra after root block before MOTION
    motion_idx = None
    for i in range(idx, n):
        if tokens[i] == "MOTION":
            motion_idx = i
            break
    if motion_idx is None:
        raise ValueError("MOTION not found")
    idx = motion_idx + 1
    # Frames: <int>
    if idx >= n or tokens[idx] != "Frames:":
        # Some BVH have "Frames:" as one token, we split by whitespace so it's "Frames:"
        raise ValueError("Expected 'Frames:'")
    num_frames = int(tokens[idx + 1])
    idx += 2
    # Frame Time: <float>  -> tokens "Frame" "Time:" "<float>"
    if idx + 2 >= n or tokens[idx] != "Frame" or tokens[idx + 1] != "Time:":
        raise ValueError("Expected 'Frame Time:'")
    frame_time = float(tokens[idx + 2])
    idx += 3

    # Collect channel_order via DFS (appearance order)
    channel_order: List[Tuple[str, str]] = []

    def collect_channels(j: BvhJoint):
        for ch in j.channels:
            channel_order.append((j.name, ch))
        for c in j.children:
            if not c.is_end_site:
                collect_channels(c)
            # End Site has no channels, skip

    collect_channels(root)
    expected_channels = len(channel_order)
    # Remaining tokens are floats
    remaining = tokens[idx:]
    # Filter to only numeric? Should all be numeric after MOTION
    # But if file is truncated, remaining may be less
    values: List[float] = []
    for t in remaining:
        try:
            values.append(float(t))
        except ValueError:
            # skip non-numeric (should not happen)
            continue
    # Need num_frames * expected_channels values
    if len(values) < num_frames * expected_channels:
        raise ValueError(f"MOTION data incomplete: need {num_frames*expected_channels} got {len(values)}")
    # Slice to exactly needed (ignore extra)
    frames: List[List[float]] = []
    pos = 0
    for _ in range(num_frames):
        row = values[pos: pos + expected_channels]
        frames.append(row)
        pos += expected_channels

    # Build joints dict (flatten)
    joints: Dict[str, BvhJoint] = {}

    def flatten(j: BvhJoint):
        joints[j.name] = j
        for c in j.children:
            flatten(c)

    flatten(root)

    return BvhData(
        root=root,
        joints=joints,
        frame_time=frame_time,
        frames=frames,
        channel_order=channel_order,
        num_frames=num_frames,
    )


def get_joint_names(bvh: BvhData, include_end_sites: bool = False) -> List[str]:
    """Depth-first joint names (EndSite除外が既定)."""
    result: List[str] = []

    def dfs(j: BvhJoint):
        if not j.is_end_site or include_end_sites:
            result.append(j.name)
        for c in j.children:
            dfs(c)

    dfs(bvh.root)
    return result
