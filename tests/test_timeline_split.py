# -*- coding: utf-8 -*-
"""timeline分割核（split_frames / loop_closure_frames）のテスト(Qt不要)."""
import logging

import pytest

from llsd2bvh.timeline import loop_closure_frames, split_frames


def _frames(n: int) -> list[dict]:
    return [{"idx": i} for i in range(n)]


def test_split_150s_overlap2_three_parts():
    # 150秒/重なり2秒→3partでS/Eが設計どおり
    frames = _frames(151)
    parts = split_frames(frames, 1.0, 150.0, max_sec=60.0, overlap_sec=2.0)
    assert [(s, e) for s, e, _ in parts] == [(0.0, 60.0), (58.0, 118.0), (116.0, 150.0)]


def test_split_overlap_frames_identical():
    # 重なりフレームが両partで完全一致（再補間なしの参照複製）
    frames = _frames(151)
    parts = split_frames(frames, 1.0, 150.0, max_sec=60.0, overlap_sec=2.0)
    tail = parts[0][2][-3:]
    head = parts[1][2][:3]
    assert tail == head
    assert all(a is b for a, b in zip(tail, head))
    # part境界の格子一致：part0末尾時刻60 == part1先頭から2番目の時刻60
    assert parts[0][2][-1]["idx"] == 60
    assert parts[1][2][2]["idx"] == 60


def test_split_overlap_zero_shares_single_frame():
    # overlap=0は境界1フレームのみ共有
    frames = _frames(121)
    parts = split_frames(frames, 1.0, 120.0, max_sec=60.0, overlap_sec=0.0)
    assert [(s, e) for s, e, _ in parts] == [(0.0, 60.0), (60.0, 120.0)]
    assert parts[0][2][-1] is parts[1][2][0]


def test_loop_closure_appends_head():
    # 先頭k=round(2.0/0.5)=4フレームが末尾に追記される
    frames = _frames(11)
    closed = loop_closure_frames(frames, 0.5, 2.0)
    assert len(closed) == 15
    assert closed[-4:] == frames[:4]
    assert closed[:11] == frames
    # 入力は不変
    assert len(frames) == 11


def test_loop_closure_zero_noop():
    # k=0なら追記なし（内容等価の別リスト）
    frames = _frames(11)
    closed = loop_closure_frames(frames, 0.5, 0.1)
    assert closed == frames and closed is not frames


def test_overlap_clamped_to_half(caplog):
    # overlap>=max_secはmax_sec/2にクランプ＋警告
    frames = _frames(121)
    with caplog.at_level(logging.WARNING):
        parts = split_frames(frames, 1.0, 120.0, max_sec=60.0, overlap_sec=60.0)
    assert any("clamped" in r.message for r in caplog.records)
    assert parts[1][0] == pytest.approx(30.0)


def test_split_single_frame():
    # 1件入力でも1partが出る
    parts = split_frames([{"idx": 0}], 5.0, 5.0)
    assert len(parts) == 1
    assert parts[0][0] == pytest.approx(0.0)
    assert parts[0][1] == pytest.approx(5.0)
    assert parts[0][2] == [{"idx": 0}]


def test_split_two_frames():
    # 2件入力でも通常適用
    frames = _frames(2)
    parts = split_frames(frames, 5.0, 5.0)
    assert len(parts) == 1
    assert parts[0][2] == frames


def test_split_tiny_final_part_kept():
    # 最終part極短でもそのまま出す（合併しない）
    frames = _frames(122)
    parts = split_frames(frames, 1.0, 121.0, max_sec=60.0, overlap_sec=2.0)
    assert [(s, e) for s, e, _ in parts] == [(0.0, 60.0), (58.0, 118.0), (116.0, 121.0)]
    assert parts[-1][2][0]["idx"] == 116


def test_all_parts_within_limit():
    # 全partが60秒以下（複数条件で走査）
    for duration, overlap in [(150.0, 2.0), (121.0, 2.0), (60.0, 5.0), (359.0, 0.0), (600.0, 5.0)]:
        dt = 1.0
        frames = _frames(int(duration) + 1)
        parts = split_frames(frames, dt, duration, overlap_sec=overlap)
        assert parts[0][0] == pytest.approx(0.0)
        assert parts[-1][1] == pytest.approx(duration)
        for s, e, pf in parts:
            assert e - s <= 60.0 + 1e-9


def test_split_empty_raises():
    with pytest.raises(ValueError):
        split_frames([], 1.0, 10.0)
    with pytest.raises(ValueError):
        loop_closure_frames([], 1.0, 2.0)
