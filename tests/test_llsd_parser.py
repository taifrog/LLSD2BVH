import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llsd2bvh.llsd_parser import parse_llsd_xml

SAMPLES = Path(__file__).parent / "samples"

def test_parse_testChange03():
    data = parse_llsd_xml(SAMPLES / "testChange03.xml")
    assert "_meta" in data
    assert data["_meta"]["version"] == 6
    assert data["_meta"]["startFromTeePose"] is True
    # 121 joints + meta
    joints = [k for k in data if not k.startswith("_")]
    assert len(joints) == 121
    # specific rotations
    assert math.isclose(data["mShoulderLeft"]["rotation"][0], 1.192059874534607, rel_tol=1e-6)
    assert math.isclose(data["mElbowLeft"]["rotation"][0], 0.7574729323387146, rel_tol=1e-6)
    assert math.isclose(data["mAnkleLeft"]["rotation"][0], 0.8674286007881165, rel_tol=1e-6)
    # others zero
    assert data["mHead"]["rotation"] == (0.0, 0.0, 0.0)

def test_parse_testChange04():
    data = parse_llsd_xml(SAMPLES / "testChange04.xml")
    # check pelvis pos/rot
    pos = data["mPelvis"]["position"]
    assert math.isclose(pos[0], -0.19, abs_tol=1e-6)
    assert math.isclose(pos[1], 0.75, abs_tol=1e-6)
    assert math.isclose(pos[2], 0.389, abs_tol=1e-3)
    rot = data["mPelvis"]["rotation"]
    # deg check
    assert math.isclose(math.degrees(rot[0]), -9.30, abs_tol=0.02)
    assert math.isclose(math.degrees(rot[1]), -18.60, abs_tol=0.02)
    assert math.isclose(math.degrees(rot[2]), 59.0, abs_tol=0.02)
    # check head
    h = data["mHead"]["rotation"]
    assert math.isclose(math.degrees(h[0]), 20.15, abs_tol=0.02)
    assert math.isclose(math.degrees(h[1]), -17.18, abs_tol=0.02)
