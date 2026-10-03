# -*- coding: utf-8 -*-
"""CLI エントリ。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .llsd_parser import parse_llsd_xml
from .skeleton import load_skeleton, filter_skeleton
from .bvh_writer import write_bvh, write_bvh_frames
from .timeline import compute_timeline_frames, loop_closure_frames, split_frames, part_filename


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llsd2bvh",
        description="Firestorm Poser LLSD XML → BVH 変換",
    )
    p.add_argument("inputs", nargs="+", help="入力 LLSD XML ファイル (複数可、ワイルドカードはシェル展開)")
    p.add_argument("-o", "--output", help="出力 BVH パス（入力が複数の場合はディレクトリ）")
    p.add_argument("--skeleton", help="avatar_skeleton.xml パス", default=None)
    p.add_argument("--units", choices=["meter", "inch"], default=None, help="出力単位 (default: 自動: 位置あり→inch, 位置なし→meter。明示時は上書き)")
    p.add_argument("--sl-compat", action="store_true", default=None, help="SL互換: 1フレーム目を基準フレームとして複製 (Frames:2) (default: 自動: 位置あり→2f, 位置なし→1f。明示時は上書き)")
    p.add_argument("--no-sl-compat", action="store_true", help="SL互換を無効化（自動判定を上書き）")
    p.add_argument("--frame-time", type=float, default=0.0333333, help="Frame Time (default: 0.0333333)")
    p.add_argument("--include-hands", action="store_true", help="手ボーンを含める（デフォルトは除外）")
    p.add_argument("--no-hands", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--total-duration", type=float, default=5.0, help="マスター秒数 (--concat用, default: 5.0)")
    p.add_argument("--max-split", type=float, default=60.0, help="1part上限秒数 (default: 60.0, 当面固定)")
    p.add_argument("--overlap", type=float, default=2.0, help="part境界の重なり秒数 (default: 2.0)")
    p.add_argument("--loop", action="store_true", help="ループ閉包: 先頭ポーズを末尾に追記")
    p.add_argument("--concat", action="store_true", help="入力群を連結→自動分割して複数BVH出力")
    return p


def _run_concat(args: argparse.Namespace, inputs: list[Path], bones, include_hands: bool) -> int:
    """入力群を連結→自動分割して複数BVH出力する。"""
    from datetime import datetime
    duration = float(args.total_duration)
    overlap = float(args.overlap)
    max_split = float(args.max_split)
    keyframes_data = []
    for inp in inputs:
        if not inp.exists():
            print(f"skip: {inp} が存在しません", file=sys.stderr)
            continue
        try:
            keyframes_data.append(parse_llsd_xml(inp))
        except Exception as e:
            print(f"error: {inp} のパースに失敗: {e}", file=sys.stderr)
            continue
    if not keyframes_data:
        print("error: 有効な入力がありません。", file=sys.stderr)
        return 2
    n = len(keyframes_data)
    key_times = [i * duration / (n - 1) for i in range(n)] if n > 1 else [0.0]
    try:
        frame_time, frames_user, _ = compute_timeline_frames(duration, keyframes_data, key_times)
    except Exception as e:
        print(f"error: タイムライン算出に失敗: {e}", file=sys.stderr)
        return 2
    frames_work = frames_user
    duration_eff = duration
    if args.loop:
        closed = loop_closure_frames(frames_user, frame_time, overlap)
        duration_eff = duration + (len(closed) - len(frames_user)) * frame_time
        print(f"  loop closure: +{len(closed) - len(frames_user)} frames (D'={duration_eff:.2f}s)")
        frames_work = closed
    try:
        parts = split_frames(frames_work, frame_time, duration_eff, max_sec=max_split, overlap_sec=overlap)
    except Exception as e:
        print(f"error: 分割に失敗: {e}", file=sys.stderr)
        return 2
    out_arg = Path(args.output) if args.output else None
    if out_arg is not None and (out_arg.is_dir() or not out_arg.suffix):
        out_dir = out_arg
    elif out_arg is not None:
        out_dir = out_arg.parent
    else:
        out_dir = inputs[0].parent / (inputs[0].stem + "_split")
    out_dir.mkdir(parents=True, exist_ok=True)
    basename = inputs[0].stem
    # --no-sl-compat が指定されたら False で上書き、--sl-compat が指定されたら True、未指定は None で自動
    eff_sl_compat = args.sl_compat
    if getattr(args, "no_sl_compat", False):
        eff_sl_compat = False
    tpose: dict = {}
    for i, (s, e, pf) in enumerate(parts):
        out_path = out_dir / part_filename(basename, i, len(parts))
        try:
            write_bvh_frames(
                [tpose] + list(pf),
                bones,
                out_path,
                frame_time=frame_time,
                units=args.units,
                sl_compat=eff_sl_compat,
                include_face=False,
                include_tail=False,
            )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {out_path.name} written ({s:.1f}-{e:.1f}s)")
        except Exception as e:
            print(f"error: {out_path} の書き出しに失敗: {e}", file=sys.stderr)
            return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # skeleton 解決 (PyInstaller 対応: exe横 > 内蔵 > CWD)
    skeleton_path = args.skeleton
    if skeleton_path is None:
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            meipass = Path(getattr(sys, '_MEIPASS', exe_dir))
            candidates = [
                exe_dir / "avatar_skeleton.xml",
                exe_dir / "_internal" / "avatar_skeleton.xml",
                meipass / "avatar_skeleton.xml",
                meipass / "_internal" / "avatar_skeleton.xml",
                Path.cwd() / "avatar_skeleton.xml",
                Path(__file__).parent.parent.parent / "avatar_skeleton.xml",
            ]
        else:
            candidates = [
                Path(__file__).parent.parent.parent / "avatar_skeleton.xml",
                Path.cwd() / "avatar_skeleton.xml",
            ]
        candidates.append(Path(r"C:\Program Files\SecondLifeViewer\character\avatar_skeleton.xml"))
        for c in candidates:
            if c.exists():
                skeleton_path = str(c)
                break
    if skeleton_path is None or not Path(skeleton_path).exists():
        print("error: avatar_skeleton.xml が見つかりません。--skeleton で指定してください。", file=sys.stderr)
        return 2

    bones = load_skeleton(skeleton_path)
    # 顔・尻尾は常時除外、手はデフォルト除外（--include-hands で含む、旧 --no-hands は互換aliasで除外のまま）
    include_hands = bool(getattr(args, "include_hands", False))
    bones = filter_skeleton(
        bones,
        include_face=False,
        include_tail=False,
        include_hands=include_hands,
    )

    # 入力解決
    inputs: list[Path] = []
    for inp in args.inputs:
        p = Path(inp)
        if p.is_dir():
            inputs.extend(sorted(p.glob("*.xml")))
        else:
            # glob が展開されていない場合も考慮
            import glob as globmod
            matched = globmod.glob(str(inp))
            if matched:
                inputs.extend(Path(m) for m in matched)
            elif p.exists():
                inputs.append(p)
            else:
                print(f"warn: 入力が見つかりません: {inp}", file=sys.stderr)

    if not inputs:
        print("error: 入力が見つかりません。", file=sys.stderr)
        return 2

    if args.concat:
        return _run_concat(args, inputs, bones, include_hands)

    # 出力解決
    out_arg = Path(args.output) if args.output else None
    is_multi = len(inputs) > 1

    if out_arg and is_multi and out_arg.suffix.lower() == ".bvh":
        print("warn: 入力が複数のため出力はディレクトリとして扱います。", file=sys.stderr)
        is_multi = True

    for inp in inputs:
        if not inp.exists():
            print(f"skip: {inp} が存在しません", file=sys.stderr)
            continue
        try:
            data = parse_llsd_xml(inp)
        except Exception as e:
            print(f"error: {inp} のパースに失敗: {e}", file=sys.stderr)
            continue

        # 出力パス決定
        if out_arg is None:
            out_path = inp.with_suffix(".bvh")
        elif is_multi:
            out_dir = out_arg if out_arg.is_dir() or not out_arg.suffix else out_arg
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / (inp.stem + ".bvh")
        else:
            out_path = out_arg
            if out_path.is_dir():
                out_path = out_path / (inp.stem + ".bvh")

        # --no-sl-compat が指定されたら False で上書き、--sl-compat が指定されたら True、未指定は None で自動
        eff_sl_compat = args.sl_compat
        if getattr(args, "no_sl_compat", False):
            eff_sl_compat = False
        try:
            write_bvh(
                joints_data=data,
                bones=bones,
                out_path=out_path,
                frame_time=args.frame_time,
                units=args.units,
                sl_compat=eff_sl_compat,
                include_face=False,
                include_tail=False,
            )
            print(f"written: {out_path}")
        except Exception as e:
            print(f"error: {out_path} の書き出しに失敗: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            continue

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
