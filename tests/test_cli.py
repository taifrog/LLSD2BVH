from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llsd2bvh.cli import main

def test_cli_single(tmp_path):
    inp = Path(__file__).parent / "samples" / "testChange03.xml"
    out = tmp_path / "out.bvh"
    rc = main([str(inp), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    txt = out.read_text(encoding="utf-8")
    assert "HIERARCHY" in txt

def test_cli_multi(tmp_path):
    s = Path(__file__).parent / "samples"
    rc = main([str(s / "testChange03.xml"), str(s / "testChange04.xml"), "-o", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "testChange03.bvh").exists()
    assert (tmp_path / "testChange04.bvh").exists()
