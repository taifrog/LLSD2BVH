# -*- coding: utf-8 -*-
"""CLI エントリ。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .llsd_parser import parse_llsd_xml
from .skeleton import load_skeleton, filter_skeleton
from .bvh_writer import write_bvh


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
    return p


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
