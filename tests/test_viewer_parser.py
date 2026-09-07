from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llsd2bvh.llsd_parser import parse_llsd_xml
from llsd2bvh.skeleton import load_skeleton, filter_skeleton
from llsd2bvh.bvh_writer import write_bvh
from llsd2bvh.viewer.bvh_parser import parse_bvh

SAMPLES = Path(__file__).parent / "samples"
SKELETON = Path(__file__).resolve().parents[1] / "avatar_skeleton.xml"

def test_parse_single_frame(tmp_path):
    data = parse_llsd_xml(SAMPLES / "testChange03.xml")
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    out = tmp_path / "out.bvh"
    write_bvh(data, fb, out, sl_compat=False, units="meter")
    bvh = parse_bvh(out)
    assert bvh.num_frames == 1
    assert bvh.root.name == "mPelvis"
    assert bvh.num_channels == len(bvh.channel_order)
    assert abs(bvh.frame_time - 0.0333333) < 1e-6
    # root should have 6 channels
    assert "Xposition" in bvh.root.channels
    # EndSite count
    assert any(n.endswith("_EndSite") for n in bvh.joints.keys())

def test_parse_multi_frame(tmp_path):
    data1 = parse_llsd_xml(SAMPLES / "testChange03.xml")
    data2 = parse_llsd_xml(SAMPLES / "testChange04.xml")
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    from llsd2bvh.bvh_writer import write_bvh_frames
    out = tmp_path / "multi.bvh"
    write_bvh_frames([{}, data1, data2], fb, out, frame_time=0.5, sl_compat=False, units="meter")
    bvh = parse_bvh(out)
    assert bvh.num_frames == 3
    # includes Tpose duplicate?
    assert bvh.num_frames == 3
    assert bvh.frames[0] != bvh.frames[1] or bvh.frames[1] != bvh.frames[2]
