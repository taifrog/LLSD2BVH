# -*- coding: utf-8 -*-
"""Viewer座標変換の左右テスト（鏡像なしの確認）.

BVH座標系: X=前, Y=左右(左+), Z=上。
Viewer座標系: X=左右(右+), Y=上, Z=奥行(手前+)。
左(Y+)は画面左(X-)に、右(Y-)は画面右(X+)に対応すること。
"""
from llsd2bvh.viewer.gl_widget import StickFigureWidget


def test_left_maps_to_screen_left():
    m = StickFigureWidget._map_bvh_to_viewer
    # 左肩 (Y+) -> viewer X-
    assert m((0.0, 0.079, 0.0))[0] < 0.0
    # 右肩 (Y-) -> viewer X+
    assert m((0.0, -0.079, 0.0))[0] > 0.0


def test_up_front_preserved():
    m = StickFigureWidget._map_bvh_to_viewer
    # 上(Z+) -> viewer Y+
    assert m((0.0, 0.0, 1.0))[1] > 0.0
    # 前(X+) -> viewer 奥(-Z)
    assert m((1.0, 0.0, 0.0))[2] < 0.0


def test_mapping_is_proper_rotation():
    # 鏡像でないこと（行列式 +1）。基底ベクトルの像で確認。
    m = StickFigureWidget._map_bvh_to_viewer
    ex = m((1.0, 0.0, 0.0))
    ey = m((0.0, 1.0, 0.0))
    ez = m((0.0, 0.0, 1.0))
    # 外積 ex × ey == ez なら正規回転
    cx = ex[1] * ey[2] - ex[2] * ey[1]
    cy = ex[2] * ey[0] - ex[0] * ey[2]
    cz = ex[0] * ey[1] - ex[1] * ey[0]
    assert abs(cx - ez[0]) < 1e-9
    assert abs(cy - ez[1]) < 1e-9
    assert abs(cz - ez[2]) < 1e-9
