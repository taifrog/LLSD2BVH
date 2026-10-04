# -*- coding: utf-8 -*-
"""F-1/F-2/W-1の統一テスト: 0値単一化・縮退落とし・疎警告."""
import logging
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llsd2bvh.cli import main
from llsd2bvh.timeline import loop_closure_frames, split_frames


def _motion_lines(path: Path) -> list[list[float]]:
    txt = path.read_text(encoding="utf-8")
    body = txt.split("Frame Time:")[1]
    rows = []
    for line in body.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        rows.append([float(x) for x in line.split()])
    return rows


def _is_zero_row(row: list[float]) -> bool:
    return all(v == 0.0 for v in row)


def test_single_rotation_only_two_frames_zero_head(tmp_path):
    # 単発・回転のみ→2フレーム、先頭は0値1つのみ（旧Frames:1は廃止）
    s = Path(__file__).parent / "samples"
    out = tmp_path / "single.bvh"
    assert main([str(s / "testChange03.xml"), "-o", str(out)]) == 0
    rows = _motion_lines(out)
    assert len(rows) == 2
    assert _is_zero_row(rows[0])
    assert not _is_zero_row(rows[1])


def test_concat_part_single_zero_head(tmp_path):
    # 位置あり連結partの0値は先頭1つのみ
    s = Path(__file__).parent / "samples"
    rc = main([str(s / "testChange03.xml"), str(s / "testChange04.xml"),
               "--concat", "--total-duration", "120", "--overlap", "2.0",
               "-o", str(tmp_path)])
    assert rc == 0
    rows = _motion_lines(tmp_path / "testChange03_part01.bvh")
    assert _is_zero_row(rows[0])
    assert sum(1 for r in rows if _is_zero_row(r)) == 1


def test_v3_degenerate_dropped_to_two_parts(tmp_path, capsys):
    # V-3再現（03/04・120s・loop・overlap2）: 旧3part→2part
    s = Path(__file__).parent / "samples"
    rc = main([str(s / "testChange03.xml"), str(s / "testChange04.xml"),
               "--concat", "--total-duration", "120", "--overlap", "2.0",
               "--loop", "-o", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "testChange03_part01.bvh").exists()
    assert (tmp_path / "testChange03_part02.bvh").exists()
    assert not (tmp_path / "testChange03_part03.bvh").exists()
    err = capsys.readouterr().err
    assert "dropping degenerate part" in err


def test_sparse_warning_fires(caplog):
    # dt > overlapで疎警告
    frames = [{"idx": i} for i in range(2)]
    with caplog.at_level(logging.WARNING, logger="llsd2bvh.timeline"):
        split_frames(frames, 120.0, 120.0, max_sec=60.0, overlap_sec=2.0)
    assert any("sparse grid" in r.message for r in caplog.records)


def test_loop_noop_warning_fires(caplog):
    # k=0で閉包警告、追記なし
    frames = [{"idx": i} for i in range(2)]
    with caplog.at_level(logging.WARNING, logger="llsd2bvh.timeline"):
        closed = loop_closure_frames(frames, 120.0, 2.0)
    assert closed == frames
    assert any("noop" in r.message for r in caplog.records)
