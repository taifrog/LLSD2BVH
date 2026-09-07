import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llsd2bvh.viewer.bvh_parser import parse_bvh
from llsd2bvh.viewer.fk import compute_frame_positions

def test_sl_compat_upright():
    p = Path(r"C:\data\SecondLifeCreate\pose\MuMuDance.bvh")
    import pytest
    if not p.exists():
        pytest.skip(f"sample BVH not found: {p}")
    bvh = parse_bvh(p)
    # frame1 has pelvis Y -46 which tilts in standard mode
    pos_sl, _ = compute_frame_positions(bvh, 1, rotation_mode="sl_compat")
    pos_std, _ = compute_frame_positions(bvh, 1, rotation_mode="standard")
    def tilt(pos):
        px, py, pz = pos['mPelvis']
        hx, hy, hz = pos['mHead']
        vx, vy, vz = hx-px, hy-py, hz-pz
        L = math.sqrt(vx*vx+vy*vy+vz*vz)
        return math.degrees(math.acos(max(-1,min(1,vz/L))))
    tilt_sl = tilt(pos_sl)
    tilt_std = tilt(pos_std)
    # sl_compat should be near upright (<5 deg), standard ~42 deg
    assert tilt_sl < 5.0, f"sl_compat tilt {tilt_sl} too large"
    assert tilt_std > 30.0, f"standard tilt {tilt_std} not tilted"
    # head should be above pelvis in Z
    assert pos_sl['mHead'][2] > pos_sl['mPelvis'][2]
