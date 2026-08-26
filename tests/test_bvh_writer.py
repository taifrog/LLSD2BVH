import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llsd2bvh.llsd_parser import parse_llsd_xml
from llsd2bvh.skeleton import load_skeleton, filter_skeleton, get_bvh_order
from llsd2bvh.bvh_writer import write_bvh

SAMPLES = Path(__file__).parent / "samples"
SKELETON = Path(__file__).resolve().parents[1] / "avatar_skeleton.xml"

def test_write_bvh_testChange03(tmp_path):
    data = parse_llsd_xml(SAMPLES / "testChange03.xml")
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    out = tmp_path / "out.bvh"
    write_bvh(data, fb, out)
    txt = out.read_text(encoding="utf-8")
    assert "HIERARCHY" in txt
    assert "ROOT mPelvis" in txt
    assert "MOTION" in txt
    assert "Frames: 1" in txt
    # check motion values contain 68.3
    assert "68.3" in txt
    # check channel count
    order = get_bvh_order(fb)
    expected = 6 + (len(order)-1)*3
    # motion line is last line
    lines = txt.splitlines()
    mi = [i for i,l in enumerate(lines) if l.strip()=="MOTION"][0]
    vals = lines[mi+3].split()
    assert len(vals) == expected

def test_write_bvh_sl_compat(tmp_path):
    data = parse_llsd_xml(SAMPLES / "testChange04.xml")
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    out = tmp_path / "out.bvh"
    write_bvh(data, fb, out, sl_compat=True, units="inch")
    txt = out.read_text(encoding="utf-8")
    assert "Frames: 2" in txt
    # inch scaling: pelvis pos 0.75m -> 29.5 inch
    assert "29.52" in txt or "29.527" in txt

def test_bvh_zxy_order(tmp_path):
    """Verify Z X Y mapping for testChange04 mTorso etc. (Head/Neck/Chest/Torso Fix適用)"""
    data = parse_llsd_xml(SAMPLES / "testChange04.xml")
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    out = tmp_path / "out.bvh"
    write_bvh(data, fb, out, units="meter", sl_compat=False)
    txt = out.read_text(encoding="utf-8")
    lines = txt.splitlines()
    mi = [i for i,l in enumerate(lines) if l.strip()=="MOTION"][0]
    vals = list(map(float, lines[mi+3].split()))
    order = get_bvh_order(fb)
    def idx(joint):
        pos = order.index(joint)
        return 6 + (pos-1)*3 if pos>0 else 3
    # mTorso file rad [-0.2435,0.2039,-0.4743] deg [-13.95,11.68,-27.17]
    # Fix: BVH(Z,X,Y)=(VX,VY,VZ) => Z -13.95 X 11.68 Y -27.17
    mTorso_vals = vals[idx("mTorso"): idx("mTorso")+3]
    assert math.isclose(mTorso_vals[0], -13.95, abs_tol=0.02)
    assert math.isclose(mTorso_vals[1], 11.68, abs_tol=0.02)
    assert math.isclose(mTorso_vals[2], -27.17, abs_tol=0.02)
