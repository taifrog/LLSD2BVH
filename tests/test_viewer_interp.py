# -*- coding: utf-8 -*-
"""Viewer補間(角度lerp + 時刻連続FK)テスト."""
import math
import pytest
from llsd2bvh.viewer.bvh_parser import BvhData, BvhJoint
from llsd2bvh.viewer.fk import lerp_angle_deg, compute_frame_positions, compute_frame_positions_at_time


def _make_bvh(channels, rows, frame_time=0.5):
    root = BvhJoint(name="mPelvis", offset=(0.0, 0.0, 1.0), channels=channels, children=[])
    child = BvhJoint(name="mTorso", offset=(1.0, 0.0, 0.0), channels=[], children=[])
    root.children = [child]
    joints = {}
    def flatten(j):
        joints[j.name] = j
        for c in j.children:
            flatten(c)
    flatten(root)
    channel_order = [("mPelvis", ch) for ch in channels]
    return BvhData(root=root, joints=joints, frame_time=frame_time, frames=rows, channel_order=channel_order, num_frames=len(rows))


def test_lerp_angle_mid():
    assert lerp_angle_deg(0, 90, 0.5) == pytest.approx(45.0)
    assert lerp_angle_deg(0, 90, 0.0) == pytest.approx(0.0)
    assert lerp_angle_deg(0, 90, 1.0) == pytest.approx(90.0)


def test_lerp_angle_wrap_shortest():
    # 170 -> -170 は +20°経由 (170->180->-170), 中点は180度付近
    mid = lerp_angle_deg(170, -170, 0.5)
    # 180 or -180 both valid, normalize to check distance to 180
    # normalize to -180..180
    norm = ((mid + 180) % 360) - 180
    assert abs(abs(norm) - 180) < 1e-6  # -180 or 180
    # 単純平均0°にならないことを保証
    assert abs(norm) > 90


def test_lerp_angle_350_to_10():
    mid = lerp_angle_deg(350, 10, 0.5)
    norm = ((mid + 180) % 360) - 180
    # 350->10 は +20°経由で中点0°
    assert norm == pytest.approx(0.0, abs=0.5)


def test_position_lerp():
    bvh = _make_bvh(["Xposition"], [[0.0], [10.0]], frame_time=0.5)
    # 整数フレームは一致
    pos0, _ = compute_frame_positions_at_time(bvh, 0.0)
    pos0_ref, _ = compute_frame_positions(bvh, 0)
    assert pos0["mPelvis"] == pytest.approx(pos0_ref["mPelvis"])
    pos1, _ = compute_frame_positions_at_time(bvh, 1.0)
    pos1_ref, _ = compute_frame_positions(bvh, 1)
    assert pos1["mPelvis"] == pytest.approx(pos1_ref["mPelvis"])
    # 中点 0.5 は X=5付近
    pos_mid, _ = compute_frame_positions_at_time(bvh, 0.5, rotation_mode="standard")
    # mPelvis X should be 5 (offset 0 + pos)
    assert pos_mid["mPelvis"][0] == pytest.approx(5.0, abs=1e-6)


def test_rotation_lerp_via_fk():
    # Yrotation 0 -> 90, child at (1,0,0) should swing in X-Z plane
    bvh = _make_bvh(["Yrotation"], [[0.0], [90.0]], frame_time=0.5)
    pos0, _ = compute_frame_positions_at_time(bvh, 0.0, rotation_mode="standard")
    pos1, _ = compute_frame_positions_at_time(bvh, 1.0, rotation_mode="standard")
    pos_mid, _ = compute_frame_positions_at_time(bvh, 0.5, rotation_mode="standard")
    # At 0: child should be (1,0,1) (offset chain)
    # At 90: Y90 rotates child offset (1,0,0) -> (0,0,-1) -> plus pelvis pos => (0,0,0)
    # Mid 45°: X~cos45, Z~1 - sin45
    # Just check mid is strictly between 0 and 1 in X and Z
    assert pos_mid["mTorso"][0] < pos0["mTorso"][0]
    assert pos_mid["mTorso"][0] > pos1["mTorso"][0]
    # clamp out of range
    pos_neg, _ = compute_frame_positions_at_time(bvh, -1.0, rotation_mode="standard")
    assert pos_neg["mTorso"] == pytest.approx(pos0["mTorso"])
    pos_over, _ = compute_frame_positions_at_time(bvh, 5.0, rotation_mode="standard")
    assert pos_over["mTorso"] == pytest.approx(pos1["mTorso"])


def test_wrap_via_fk():
    bvh = _make_bvh(["Zrotation"], [[170.0], [-170.0]], frame_time=0.5)
    pos_mid, _ = compute_frame_positions_at_time(bvh, 0.5, rotation_mode="standard")
    pos0, _ = compute_frame_positions(bvh, 0, rotation_mode="standard")
    pos1, _ = compute_frame_positions(bvh, 1, rotation_mode="standard")
    # wrap mid should be near 180, not near 0. So child Y should be opposite side.
    # With Z rotation, child offset (1,0,0) rotated 180 -> (-1,0,0)
    # At 0: Z170 rotates ~170, at mid 180 rotates ~ -1, at 1: -170
    # Check mid X < both ends (most negative)
    assert pos_mid["mTorso"][0] < pos0["mTorso"][0]
    assert pos_mid["mTorso"][0] < pos1["mTorso"][0]
