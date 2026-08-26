from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llsd2bvh.skeleton import load_skeleton, filter_skeleton, get_bvh_order

SKELETON = Path(__file__).resolve().parents[1] / "avatar_skeleton.xml"

def test_load_skeleton():
    bones = load_skeleton(SKELETON)
    assert len(bones) == 133
    assert "mPelvis" in bones
    assert "mHead" in bones

def test_filter_default():
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones)
    assert "mFaceJaw" not in fb
    assert "mTail1" not in fb
    assert "mHandIndex1Left" in fb
    assert len(fb) == 56
    order = get_bvh_order(fb)
    assert order[0] == "mPelvis"
    assert "mTorso" in order
    assert "mToeRight" in order
    assert len(order) == len(set(order)) == 56

def test_filter_include_face():
    bones = load_skeleton(SKELETON)
    fb = filter_skeleton(bones, include_face=True)
    assert "mFaceJaw" in fb
