# LLSD2BVH

[English version is here](README.en.md).

Firestorm/Aperture ViewerのPoserでエクスポートしたLLSD XMLポーズファイルから、Second Life/Blender用BVHへの変換ツールです。

## 前提

- Tポーズを基準とした差分ポーズを想定しています(`startFromTeePose`前提。Viewer側で`Tポーズから開始`にチェックを入れてください)。
- 顔(`mFace*`)とテール(`mTail*`)は既定で除外します。手(`mHand*`)は既定で含みます(オプションで切り替えられます)。
- Second Life互換を優先しつつ、Blender汎用出力も可能です(`--units`/`--sl-compat`で切り替えられます)。

## 概要

本ツールはFirestorm/Aperture ViewerのPoserが出力するLLSD XML(`rotation`がroll/pitch/yawのEuler rad)を読み取り、BVHの`HIERARCHY`+`MOTION`に変換します。

- **対応ビューアはFirestorm/Apertureのみで、他ビューアは未確認です**(LLSDの`getEulerAngles`仕様に依存します)。
- 単一ポーズだけでなく、最大100件のポーズをドラッグ&ドロップで並べられます。タイムライン(横)で各ポーズの実行タイミングを指定し、1つのBVHに連結出力できます(v0.4.0からの新機能です)。600秒超の長尺は60秒以下で自動分割して複数BVHに出力します。
- アニメーション時間は0.1〜600秒で指定します(マスター時間。SLの1ファイル制限60秒を超える分は自動分割されます)。2件時はFrame Timeがアニメーション時間と等しくなります。3件以上で間隔が不均一な場合は、最小間隔から均一なFrame Timeを算出します。不足分はSlerp補間で追加フレームを自動挿入します(最低Frame Timeは0.01です)。
- 位置(`mPelvis`)の有無にかかわらず、先頭に基準フレーム(Tポーズ)を1つ付けて出力します(全出力は最低2フレーム。旧版の回転のみ`Frames:1`は廃止)。単位は位置ありなら`inch`、位置なしなら`meter`の自動判定を維持します(明示的に上書きできます)。
- Viewer検証済みのper-joint回転fix(`BVH(Z,X,Y)=(VX,VY,VZ)`)とPelvis位置`X=VY,Y=VZ,Z=VX`変換を適用します。Viewerアップロード時の向き・移動が一致します。

## 使い方: GUI版(推奨)

### ダウンロード・解凍・実行

1. [GitHub Releases](https://github.com/taifrog/LLSD2BVH/releases)から`LLSD2BVH_vX.Y.Z.zip`(例: `LLSD2BVH_v0.4.0.zip`)をダウンロードします。
2. 右クリックして`すべて展開`で解凍します(`LLSD2BVH/`フォルダが生成されます)。
3. `LLSD2BVH/LLSD2BVH.exe`をダブルクリックで起動します。

> 初回起動時にSmartScreen`WindowsによってPCが保護されました`と表示された場合は、`詳細情報`から`実行`をクリックしてください。2回目以降は表示されません。コード署名なしのため表示されるだけで、機能に影響はありません。

Python環境がある場合は`exe`なしでも起動できます:

```bash
pip install -r requirements.txt  # PySide6
python -m llsd2bvh.gui
# または
llsd2bvh-gui
```

### 画面の説明

#### メイン画面

![GUI画面](docs/screenshot-gui.png)

| 部位 | 説明 |
|------|------|
| ① 入力リスト | LLSD XMLの一覧です。ドラッグ&ドロップ、または`追加…`で最大100件まで追加できます。`削除`、`↑`、`↓`、`クリア`、`コピー`で編集できます。リストはファイル管理用で、出力順はタイムラインの時刻順になります。 |
| ② タイムライン | 横方向の時間軸です(0〜アニメーション時間)。ファイル毎に1レーン(見出し＝ファイル名)で各ポーズをブロック表示します。60秒毎に赤破線の分割線、境界前後に黄色の重なり帯を描画します。ドラッグで時刻を移動し、ダブルクリックで数値入力できます。先頭ブロックは0秒に固定され、末尾ブロックは`duration`に固定されます(濃色で表示)。2件以上で有効で、1件時は無効です。上部の`－`、`＋`、`100%`、`ズーム: n%`で100〜400%に拡大できます(±50%刻み)。ホイールで拡大縮小し、空所の左ドラッグでパンできます。100件時は縦スクロールします。 |
| ③ アニメーション時間 | BVH全体の秒数です。0.1〜600.0秒で指定します(最大600秒のマスター時間。60秒超は自動分割されます)。既定は5.0秒です。2件時はFrame Timeが`duration`と等しくなります。3件以上で均一な場合はFrame Timeが最小間隔と等しくなります。不均一な場合は最小間隔から均一なFrame Timeを算出します。不足分は補間フレーム(`Slerp`+位置`lerp`)を自動挿入します。最低Frame Timeは0.01でクランプします。 |
| ④ 算出Frame Time/総フレーム | タイムラインから自動算出されたFrame Timeと総フレーム数を表示します(例: `算出Frame Time: 0.3125 総フレーム: 18 (Tポーズ+17 P1@0s) (+9補間)`)。非均一時は補間数が括弧で表示されます。 |
| ⑤ 出力先 | 出力フォルダです。未指定なら先頭ファイル名+`_split/`に自動作成します。`参照…`でフォルダを選択できます。ファイル名は`<先頭名>_part01.bvh`形式(2桁ゼロパディング、11part以上は3桁に自動拡張)です。 |
| ⑥ Skeleton | `avatar_skeleton.xml`のパスです。未指定なら`exe`内蔵(`_internal`)または`exe`横のファイルを自動で使用します。Viewer更新時に差し替える場合は`exe`と同じフォルダに置いてください。 |
| ⑦ Units/SL互換 | 出力単位とSL互換です。`自動`(推奨)は位置ありなら`inch`、位置なしなら`meter`になります。先頭の基準フレーム(Tポーズ)は全出力に共通で付きます。`Frame Time`は現行では非表示で自動算出されます。 |
| ⑧ 手を除外 | 含めるボーンの切り替えです。既定は手を含みます(チェックOFF)。チェックをONにすると手を除外します(顔・テールは常時除外で、手のみ切り替えられます)。 |
| ⑨ Progress/Log | 変換進捗とログ表示です。 |
| ⑩ プレビュー/ビューア/変換/閉じる | `プレビュー`は出力BVHを3Dスティックモデル(棒人間)で表示します(変換後に有効)。`ビューア`は任意のBVHを3Dで表示します(変換不要、常時有効。空で開いてビューア側の`参照…`やドラッグ&ドロップで選択)。`変換`で実行し、完了時にダイアログで出力パスとフレーム数を表示します。 |
| ⑪ 重なり/ループ対応/分割サマリ | part境界の重なり秒数です。0.0〜5.0秒で指定し、既定は2.0秒(0.1秒刻み)です。`ループ対応`をONにすると末尾に先頭ポーズの重なり分を自動追記します(既定OFF)。サマリ行に分割内容を表示します(例: `分割: 3ファイル (60.0s/60.0s/34.0s) 重なり2.0s`)。 |
| ⑫ part切替 | `part:`ドロップダウンでpart01〜Nを切り替えて既存ビューアで表示します(変換後に有効)。 |

#### BVHビューア

![BVHビューア](docs/screenshot-viewer.png)

| 部位 | 説明 |
|------|------|
| ① BVH選択 | 上部`BVH: … 参照…`で行が表示されます。メイン画面の`プレビュー`/`ビューア`、または単体起動`python -m llsd2bvh.viewer`/`bvh-viewer`から開きます。ドラッグ&ドロップでも読み込めます。 |
| ② 3Dビュー | 3Dスティックモデル(棒人間: 骨線・関節点)と床グリッドです。左ドラッグで回転し、右ドラッグでパンし、ホイールでズームします。左上に`yaw/pitch/dist`、右下に操作ヒントを表示します。 |
| ③ 情報行 | ファイル名・`Frames/FrameTime/Channels/Joints`と`f/t/dt`です。補間ON時は`1->2 (50%) f=1.50 [補間]`のようにフレーム間を30fpsで連続表示します。 |
| ④ スライダー | `0〜Frames-1`をドラッグ、または`◀`/`▶`で1コマ移動します。再生中は整数部のみ同期します。 |
| ⑤ 再生コントロール | `◀`、`▶再生/■停止`、`ループ`、`▶`、`速度(0.25x〜2x)`、`補間`(既定ONで30fps滑らかにチャネル`lerp`+角度最短ラップ(`wrap`)、OFFでコマ送り)、`Tポーズ先頭をスキップ`、`回転(SL互換/BVH標準)`です。 |
| ⑥ 視点プリセット | `正面(180°)/側面(90°)/上面(85°)/リセット(180°/0°)`です。任意回転後はリセットで初期視点に戻します。 |

### 基本的な使い方

1. Firestorm/ApertureのPoserでポーズを作成し、LLSD XMLとしてエクスポートします。
   - 必ずTポーズにセットしてからポージングしてください(変更した箇所だけ保存されるため)。
   - エクスポート方法は、右下の`自分のポーズ`をクリックします。右側に表示されるエリアに名前を付けて、`ポーズを保存`をクリックして保存します。
   - エクスポートしたファイルの場所は、`初期設定`から`セットアップ`、`ディレクトリ`の順に開きます。`設定フォルダを開く`をクリックし、その中の`poses`フォルダにあります。
2. GUIの入力リストにXMLをドラッグ&ドロップ(または`追加…`)で追加します。リストはそのまま残り、タイムライン(横)へ自動配置されます。
   - 1件の場合: タイムラインは無効です。先頭に基準フレーム(Tポーズ)を付けて2フレームBVHとして出力します。
   - 2件の場合: タイムラインの両端(0秒と`duration`)に配置します。先頭に基準フレームを付けて出力します。
   - 3件以上: 各ブロックをドラッグで時刻を移動し、ダブルクリックで数値入力します。アニメーション時間を0.1〜600秒で指定します。間隔が均一ならそのまま出力します。不均一なら最小間隔から均一なFrame Timeを算出します。不足分は`Slerp`(回転)+`lerp`(位置)で補間フレームを自動挿入して出力します。
3. タイムラインでポーズのタイミングを調整し、アニメーション時間を確認します(算出Frame Timeと総フレーム数が表示されます)。`－`/`＋`やホイールで拡大して細かく編集できます。重なり秒数とループ対応を設定し、分割サマリ行でpart構成を確認します。
4. 必要に応じて出力フォルダやUnits/SL互換を変更します(通常は`自動`のままで問題ありません)。
5. `変換`をクリックします。ログにpart毎の`書き出し完了`と表示されれば成功です。出力された`.bvh`をViewerやBlenderで読み込んでください。
6. 変換後は`プレビュー`で確認します。任意BVHの確認だけなら`ビューア`で3Dスティックモデル(棒人間)表示します(補間ONで滑らかに30fps再生します。視点は正面/側面/上面/リセットで切り替えられます)。

## 使い方: CLI版(コマンドライン版)

### コマンド

```bash
# 単一ファイル
python -m llsd2bvh input.xml -o output.bvh
# またはインストール後
llsd2bvh input.xml -o output.bvh

# SLアップロード用に明示的に inch/2フレーム
python -m llsd2bvh input.xml --units inch --sl-compat -o output_sl.bvh

# 複数ファイルをディレクトリに個別出力
python -m llsd2bvh poses/*.xml -o out_dir/

# ディレクトリ指定(*.xml を一括)
python -m llsd2bvh poses/ -o out_dir/

# ワイルドカード(シェル展開されない環境でもOK)
python -m llsd2bvh "poses/*.xml" -o out_dir/

# 連結→自動分割(マスター150秒を60秒以下で3分割)
python -m llsd2bvh poses/*.xml --concat --total-duration 150 --overlap 2.0 -o split_out/

# ループ閉包付きで連結→分割
python -m llsd2bvh poses/*.xml --concat --total-duration 120 --overlap 2.0 --loop -o split_out/
```

> GUI版は複数入力を連結して複数BVHに自動分割します。CLI版は既定で複数入力を個別のBVHに分割出力します(`--concat`でGUI相当の連結→分割になります)。

### オプション

| オプション | 説明 | 既定値 |
|------------|------|--------|
| `inputs` | 入力LLSD XML(複数可、ワイルドカード/ディレクトリ可) | 必須 |
| `-o, --output` | 出力BVHパス。複数入力時はディレクトリ | 未指定時は入力と同名の`.bvh` |
| `--skeleton` | `avatar_skeleton.xml`のパス | 自動探索(`exe`横/`_internal`/`CWD`/リポジトリ直下/Viewer既定パス) |
| `--units {meter,inch}` | 出力単位 | `自動`: 位置ありは`inch`、位置なしは`meter`。明示時は上書きします |
| `--sl-compat` | SL互換(現行は受付のみ。出力は基準フレーム付き固定のため効果なし) | - |
| `--no-sl-compat` | SL互換を無効化(現行は受付のみ。出力は基準フレーム付き固定のため効果なし) | - |
| `--frame-time FLOAT` | Frame Time | `0.0333333` |
| `--include-face` | 顔ボーン(`mFace*`)を含めます | 除外 |
| `--include-tail` | テールボーン(`mTail*`)を含めます | 除外 |
| `--no-hands` | 手ボーン(`mHand*`)を除外します | 含む |
| `--total-duration FLOAT` | 連結時のマスター秒数(`--concat`用) | `5.0` |
| `--max-split FLOAT` | 1part上限秒数(当面60固定) | `60.0` |
| `--overlap FLOAT` | part境界の重なり秒数 | `2.0` |
| `--loop` | ループ閉包: 先頭ポーズを末尾に追記 | OFF |
| `--concat` | 入力群を連結→自動分割して複数BVH出力 | OFF(個別出力) |
| `-h, --help` | ヘルプ表示 | - |

```bash
python -m llsd2bvh --help
```

## 本ツールの仕様

### 仕組み

- **階層**: `avatar_skeleton.xml`(`C:\Program Files\SecondLifeViewer\character\avatar_skeleton.xml`を同梱)から`OFFSET`と親子関係を取得します。正規化した`BVH_HIERARCHY`(`mPelvis`をROOTとする26関節+手指)で`HIERARCHY`を構築します。単位は`meter`から`inch`へ39.37008倍で変換します。
- **回転**: LLSDの`rotation`は`LLQuaternion.getEulerAngles`のroll(VX)/pitch(VY)/yaw(VZ)[rad]をそのまま読みます。度数変換してBVH`Zrotation Xrotation Yrotation`(ZXY順)へ出力します。Viewer検証済みのper-joint fix`BVH(Z,X,Y)=(VX,VY,VZ)`を`mHead/mNeck/mChest/mTorso/mCollar/mShoulder/mElbow/mWrist/mHip/mKnee/mAnkle/mPelvis`(17ジョイント)に適用します。
- **位置**: `mPelvis`の`position`のみを使用します。Viewer BVHの`Xpos=VY, Ypos=VZ, Zpos=VX`入替と`inch`変換を適用します。全出力の先頭に基準フレーム(Tポーズ)を1つ付けます。
- **フィルタ**: `skeleton.py:filter_skeleton`で`support=="base"`のみを既定とします。`mFace*`/`mTail*`/`mHand*`はオプションで切り替えます。
- **タイムライン**: `timeline.py:compute_timeline_frames`で`t0=0, t_last=duration`を強制します。均一ならそのまま出力します。不均一なら`dt = duration / (ceil(duration/min_gap)+1)`で均一化します。格子点`t=i*dt`を前後のキーフレーム間で`Slerp`(回転は`Quaternion`、位置は`lerp`)補間します。2件時は`dt=duration`です。1件時はタイムライン無効です。
- **長尺分割**: `timeline.py:split_frames`でマスター(最大600秒)を60秒以下のpartに自動分割します(`S_0=0`、`E_i=S_i+60`、`S_{i+1}=E_i-重なり`)。重なり区間のフレームは両partに複製します(再補間なし)。`loop_closure_frames`でループ時は先頭ポーズの重なり分を末尾に追記します。新規格子点を含まない縮退partは落とします。疎いタイムライン(`dt`が重なりより粗い)では警告を出します。

### ビルド方法

```powershell
# 依存関係
pip install pyinstaller PySide6

# onedir ビルド(推奨: フォルダ配布, 約110MB)
powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1
# 出力: dist/LLSD2BVH/LLSD2BVH.exe + _internal/ + avatar_skeleton.xml
#       dist/LLSD2BVH_vX.Y.Z.zip (例: 約44MB)

# エントリ: tools/entry_gui.py が相対import対策のラッパー
# spec: LLSD2BVH.spec(windowed/onedir, excludesでQt3D/WebEngine等を除外)
```

`avatar_skeleton.xml`は`exe`に内蔵(`_internal/avatar_skeleton.xml`)されていますが、`exe`と同じフォルダに同名ファイルを置くか、GUIのSkeleton欄で明示指定することで差し替え可能です(優先順位: 明示指定 > `exe`横 > `_internal` > `CWD`)。

### 開発

```bash
pip install -r requirements.txt
pytest -q
```

### Second Lifeでの連続再生(LSL連播の目安)

- 各partは60秒以下の独立BVHです。インワールドではタイマーで順次再生します。切り替え間隔の目安は`part長 - 重なり`です(例: 60秒part+重なり2秒なら58秒で次を`llStartAnimation`し、旧を`llStopAnimation`します)。
- ループ再生時は閉包追記済みの最終partまで再生し、先頭に戻します。LSLスクリプト本体は本ツールに含みません。
