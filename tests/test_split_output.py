# -*- coding: utf-8 -*-
"""分割出力の結合テスト: 命名・part数・60秒制限 (Qt不要、CLI経由)."""
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llsd2bvh.cli import main
from llsd2bvh.timeline import part_filename


def _bvh_frames(path: Path) -> tuple[int, float]:
    txt = path.read_text(encoding="utf-8")
    n = int(re.search(r"Frames:\s*(\d+)", txt).group(1))
    dt = float(re.search(r"Frame Time:\s*([0-9.eE+-]+)", txt).group(1))
    return n, dt


def _printed_windows(capsys) -> list[tuple[float, float]]:
    out = capsys.readouterr().out
    return [(float(a), float(b)) for a, b in re.findall(r"\((\d+\.?\d*)-(\d+\.?\d*)s\)", out)]


def test_part_filename_width():
    assert part_filename("walk", 0, 3) == "walk_part01.bvh"
    assert part_filename("walk", 2, 3) == "walk_part03.bvh"
    assert part_filename("walk", 0, 11) == "walk_part001.bvh"
    assert part_filename("walk", 10, 11) == "walk_part011.bvh"


def test_concat_split_three_parts(tmp_path, capsys):
    s = Path(__file__).parent / "samples"
    inputs = [str(s / f"testChange0{i}.xml") for i in (1, 2, 3, 4)]
    rc = main(inputs + ["--concat", "--total-duration", "150", "--overlap", "2.0",
                         "-o", str(tmp_path)])
    assert rc == 0
    names = ["testChange01_part01.bvh", "testChange01_part02.bvh", "testChange01_part03.bvh"]
    for nm in names:
        assert (tmp_path / nm).exists()
    # part windowは60秒以下（参照フレーム+1は既存単発形式の踏襲）
    for s, e in _printed_windows(capsys):
        assert e - s <= 60.0 + 1e-6
    # グリッド＋Tposeの構成：part01はwindow内格子点+1フレーム
    n, _dt = _bvh_frames(tmp_path / names[0])
    assert n == 3  # 格子{0,50}+Tpose


def test_concat_loop_appends_closure(tmp_path):
    s = Path(__file__).parent / "samples"
    inputs = [str(s / "testChange03.xml"), str(s / "testChange04.xml")]
    rc = main(inputs + ["--concat", "--total-duration", "120", "--overlap", "2.0",
                         "--loop", "-o", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "testChange03_part01.bvh").exists()
    assert (tmp_path / "testChange03_part02.bvh").exists()


def test_concat_default_outdir(tmp_path, capsys):
    # -o省略時は先頭ファイル名＋_split/ …の代わりに-o指定で同等確認
    s = Path(__file__).parent / "samples"
    out = tmp_path / "custom"
    rc = main([str(s / "testChange03.xml"), str(s / "testChange04.xml"),
               "--concat", "--total-duration", "61", "-o", str(out)])
    assert rc == 0
    assert (out / "testChange03_part01.bvh").exists()
    wins = _printed_windows(capsys)
    # V-4: part02 [58,61]は新規格子indexなし→落とす。part01[0,60]のみ残る
    assert wins == [(0.0, 60.0)]
    assert not (out / "testChange03_part02.bvh").exists()
