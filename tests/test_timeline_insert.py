# -*- coding: utf-8 -*-
"""タイムライン挿入(中点優先)とブロック名中間省略のテスト(Qt不要)."""
from llsd2bvh.timeline import insertion_mid_time
from llsd2bvh.widgets.timeline_view import elide_middle_label


def test_mid_time_center():
    # 広い区間は中央
    assert insertion_mid_time(0.0, 5.0) == 2.5
    assert insertion_mid_time(1.0, 2.0) == 1.5


def test_mid_time_clamped():
    # 中点がepsに満たない側はクランプ（後段_enforceで単調性保証）
    assert insertion_mid_time(0.0, 0.06) == 0.05  # 中点0.03 -> lo+eps
    assert insertion_mid_time(4.96, 5.0) == 5.01  # 狭区間フォールバック lo+eps


def test_mid_time_narrow_fallback():
    # 幅 < 2*eps は従来通り lo+eps
    assert insertion_mid_time(1.0, 1.05) == 1.05
    assert insertion_mid_time(2.0, 2.0) == 2.05


def test_mid_time_bounds():
    for lo, hi in [(0.0, 5.0), (0.0, 0.2), (3.3, 4.4)]:
        v = insertion_mid_time(lo, hi)
        assert lo <= v <= hi + 0.05  # 狭区間フォールバックはhi超過あり得る


def _len_advance(s: str) -> int:
    return len(s)


def test_elide_no_change_when_fits():
    assert elide_middle_label("#1 ", "a.xml", 100, _len_advance) == "#1 a.xml"


def test_elide_keeps_tail_identifier():
    # 識別数字・拡張子が残ること（末尾切りでは消える）
    label = elide_middle_label("#3 ", "MuMuDance03.xml", 14, _len_advance)
    assert label.startswith("#3 ")
    assert "…" in label
    assert label.endswith("03.xml")
    assert len(label) <= 14


def test_elide_head_trimmed():
    label = elide_middle_label("#1 ", "MuMuDance01.xml", 12, _len_advance)
    assert label.startswith("#1 ")
    assert label.endswith("01.xml")
    assert "MuMuDance01.xml" not in label  # 省略が発生している


def test_elide_no_extension():
    label = elide_middle_label("#2 ", "VeryLongPoseName", 12, _len_advance)
    assert label.startswith("#2 ")
    assert "…" in label
    assert len(label) <= 12


def test_elide_stem_keeps_identifier():
    # ブロック表示は p.stem（拡張子なし）＋中間省略。識別数字が残ること
    from pathlib import Path
    stem = Path("MuMuDance03.xml").stem
    assert stem == "MuMuDance03"
    assert ".xml" not in stem
    label = elide_middle_label("#3 ", stem, 12, _len_advance)
    assert label.startswith("#3 ")
    assert label.endswith("03")
    assert ".xml" not in label
    assert len(label) <= 12
