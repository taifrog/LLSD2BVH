# LLSDtoBVH

Firestorm / Aperture Viewer Poser でエクスポートした LLSD XML ポーズファイルから BVH への変換ツール。

## 前提

- Tポーズを基準とした差分ポーズを想定（`startFromTeePose` 前提）
- 顔 (`mFace*`) と Tail (`mTail*`) はデフォルトで除外、手 (`mHand*`) は含む
- Second Life 互換を優先しつつ Blender 汎用出力も可能

## 使い方

```bash
python -m llsd2bvh input.xml -o output.bvh
python -m llsd2bvh input.xml --units inch --sl-compat -o output_sl.bvh
python -m llsd2bvh poses/*.xml -o out_dir/
```

### オプション

- `--units {meter,inch}` デフォルト `meter`。SL アップロード用は `inch`
- `--sl-compat` 1フレーム目を基準フレームとして複製（SL BVH Reference Frame対応）
- `--frame-time` デフォルト `0.0333333`
- `--include-face --include-tail` 顔/Tail を含める
- `--help` で詳細表示

## 仕組み

- `avatar_skeleton.xml` から OFFSET/階層を取得
- LLSD `rotation` は `getEulerAngles` (roll,pitch,yaw rad) をそのまま読み、度数に変換して BVH `Zrotation Xrotation Yrotation` へ出力
- `floater_fs_poser.xml` の per-joint translation/negation を考慮（体幹は SWAP_YAW_AND_ROLL 等）

## 開発

```bash
pip install -r requirements.txt
pytest -q
```
