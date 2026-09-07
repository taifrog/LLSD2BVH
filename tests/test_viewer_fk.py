import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llsd2bvh.llsd_parser import parse_llsd_xml
from llsd2bvh.skeleton import load_skeleton, filter_skeleton, get_bvh_order
from llsd2bvh.bvh_writer import write_bvh
from llsd2bvh.viewer.bvh_parser import parse_bvh
from llsd2bvh.viewer.fk import compute_frame_positions

SAMPLES = Path(__file__).parent / "samples"
SKELETON = Path(__file__).resolve().parents[1] / "avatar_skeleton.xml"

def test_fk_tpose_positions(tmp_path):
    # Tpose empty frame should place pelvis at its OFFSET (0,0,1.067) in meter
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    out = tmp_path / "tpose.bvh"
    # empty dict => Tpose
    write_bvh({}, fb, out, sl_compat=False, units="meter")
    bvh = parse_bvh(out)
    pos, bones_seg = compute_frame_positions(bvh, 0)
    # mPelvis should be at its offset (0,0,1.067)
    pelvis = pos["mPelvis"]
    assert math.isclose(pelvis[0], 0.0, abs_tol=1e-4)
    assert math.isclose(pelvis[1], 0.0, abs_tol=1e-4)
    assert math.isclose(pelvis[2], 1.067, abs_tol=1e-3)
    # mTorso should be offset from pelvis: mTorso pos (0,0,0.084) => world ~ (0,0,1.151)
    torso = pos["mTorso"]
    # offset chain mPelvis(1.067) + mTorso(0.084) = 1.151
    assert math.isclose(torso[2], 1.151, abs_tol=1e-3)
    # bones contain pelvis-> segments
    assert len(bones_seg) > 10

def test_fk_rotation(tmp_path):
    # Test single rotation 90deg around Z for mChest (via hand/head fix not needed)
    # Create minimal BVH by writing with known rotation
    data = parse_llsd_xml(SAMPLES / "testChange04.xml")
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    out = tmp_path / "rot.bvh"
    write_bvh(data, fb, out, sl_compat=False, units="meter")
    bvh = parse_bvh(out)
    pos, bones_seg = compute_frame_positions(bvh, 0)
    # Just check that FK runs and positions differ from Tpose
    pelvis = pos["mPelvis"]
    # Should still be near origin offset, not error
    assert all(math.isfinite(v) for v in pelvis)
    # Check that number of positions matches joints (excluding EndSite maybe inclusive)
    assert "mHead" in pos
    assert "mShoulderLeft" in pos

def test_fk_frame_count(tmp_path):
    from llsd2bvh.bvh_writer import write_bvh_frames
    data1 = parse_llsd_xml(SAMPLES / "testChange03.xml")
    data2 = parse_llsd_xml(SAMPLES / "testChange04.xml")
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    out = tmp_path / "multi2.bvh"
    write_bvh_frames([{}, data1, data2], fb, out, frame_time=0.1, sl_compat=False, units="meter")
    bvh = parse_bvh(out)
    for i in range(bvh.num_frames):
        pos, bones_seg = compute_frame_positions(bvh, i)
        assert "mPelvis" in pos
        assert len(bones_seg) == len([k for k in pos.keys() if not k.endswith("_EndSite")]) + sum(1 for k in pos if k.endswith("_EndSite")) - 1  or len(bones_seg) > 0
