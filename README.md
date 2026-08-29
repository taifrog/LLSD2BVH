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

## GUI版（推奨）

```bash
pip install -r requirements.txt
python -m llsd2bvh.gui
# または
llsd2bvh-gui
```

最大20件のLLSD XMLをドラッグ＆ドロップで並べて、1つのBVHに全フレーム連結して出力します。

## exe版（--onedir 配布）

ビルド済み `dist/LLSD2BVH_v0.1.0.zip` を展開し、`LLSD2BVH/LLSD2BVH.exe` を起動してください。

```powershell
# 自前でビルドする場合
pip install pyinstaller PySide6
powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1
# 出力: dist/LLSD2BVH/LLSD2BVH.exe  (フォルダ配布, 110MB)
#       dist/LLSD2BVH_v0.1.0.zip
```

* `avatar_skeleton.xml` は exe に内蔵されています。Viewer更新で差し替える場合は exe と同じフォルダの `avatar_skeleton.xml` を置き換えてください（GUIの Skeleton 欄で明示指定も可）。
* 初回起動時に SmartScreen「Windowsによって PC が保護されました」が出る場合は「詳細情報」→「実行」。

## 開発

```bash
pip install -r requirements.txt
pytest -q
```
