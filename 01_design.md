# 01_design.md — LLSD2BVH Long Animation（10分・複数BVH分割）設計

- 日付: 2026-10-03
- 要件: `00_requirements.md`（承認済み）
- 正本ルール: `RuleForAIAgent.md` #1（設計工程フェーズ）
- 本フェーズでは実装コードを書かない。承認後にコーディングに進む。
- コーディング時の指定: `main`から新ブランチを切って開発・検証する（ブランチ名案: `feature/long-animation-split`）。

## 1. アーキテクチャと全体構成

```
LLSD XML群（最大100件、点モデル）
  → llsd_parser.parse_llsd_xml（既存、変更なし）
  → timeline.compute_timeline_frames(D<=600)（MAX_DURATIONのみ拡張）
      → 均一フレーム列 frames（dt継承）＋格子時刻 grid_times
  → timeline.split_frames(frames, dt, max_sec=60, overlap, loop)（新設）
      → part列 [(S_i, E_i, part_frames)]（重なり区間は両partに複製）
  → bvh_writer.write_bvh_frames(part_frames) ×N（既存、変更なし）
      → <basename>_part01.bvh ...
```

- 処理フロー変更点は分割層の追加のみ。回転fix・Pelvis入替・単位自動判定は不変。
- GUIはマスター編集→分割プレビュー→一括出力。CLIは同等を引数で実行。
- 外部依存の追加なし（PySide6/pytestのみ）。

## 2. モジュール（ファイル・関数）分割

| モジュール | 役割 | 変更内容 |
|---|---|---|
| `timeline.py` | 均一化＋分割核 | `MAX_DURATION 60→600`。新設 `split_frames()`＋`loop_closure_frames()`。`compute_timeline_frames`本体は不変 |
| `bvh_writer.py` | BVH書出 | 変更なし（part毎に呼ぶだけ）。`sl_compat`はpart毎に自動適用（各part先頭に基準フレーム） |
| `gui.py:MainWindow` | 統合GUI | 総時間Spin max600、重なりSpin 0〜5s（既定2.0）、ループCheck（既定OFF）、出力フォルダ化、分割サマリ行、プレビューpart切替 |
| `widgets/timeline_view.py:TimelineView` | レーン描画 | `_compute_rows`廃止→ファイル毎1レーン。見出し＝ファイル名。分割赤破線＋重なり黄帯。縦スクロール対応 |
| `cli.py` | CLI | `--total-duration/--max-split/--overlap/--loop/--concat`追加。既存動作は維持 |
| `i18n.py` | 日英辞書 | 新規キー（重なり/ループ/分割サマリ/part等）を日英追加 |

単一責任：均一化（既存）と分割（新設）を分離し、書出は触らない。

## 3. データ構造とインターフェース（I/O）

### 3.1 `compute_timeline_frames`（既存、I/O不変）

- 入力: `duration D (0.1〜600)`、`keyframes_data[N]`、`key_times[N]`（t0=0/t_last=D強制済み）。
- 出力: `(dt, frames, num_inserted)`。`frames`は均一間隔、`grid_times[i]=i*dt`（末尾=D補正）。

### 3.2 `split_frames`（新設）

```python
def loop_closure_frames(frames: list[dict], dt: float, loop_sec: float) -> list[dict]
    # 先頭 k=round(loop_sec/dt) フレームの複製を末尾に追記。D' = D + k*dt。

def split_frames(
    frames: list[dict], dt: float, duration: float,
    max_sec: float = 60.0, overlap_sec: float = 2.0,
) -> list[tuple[float, float, list[dict]]]
    # 戻り値: [(S_i, E_i, part_frames)]。S_0=0、E_i=S_i+max_sec、
    # S_{i+1}=E_i-overlap。part_framesは時刻[S_i,E_i]の複製参照。
    # 最終partが短くてもそのまま出す（吸収合併はしない＝予測可能性優先）。
```

- 均一格子前提のため境界は `i0=round(S_i/dt)`、`i1=round(E_i/dt)` で切る。重なりフレームは両partに含める（参照複製、再補間なし＝完全一致）。
- `overlap >= max_sec` は `max_sec/2` にクランプして警告。
- `overlap=0` は無重なり（境界共有1フレームのみ）。

- F-2（2026-10-04追記）: 新規格子index（当該partの `[i0..i1]` が既出partの最大indexを超えるもの）を含まないpartは返さない。先頭partは常時保持。落としたpartの `(S,E)` は `logger.warning`＋呼出側ログに記録する。
- 命名（2026-10-04追記）: `part_filename(basename, index, total)` が `<basename>_part01.bvh` 形式を返す。2桁ゼロパディング、part数10超は3桁に自動拡張。

### 3.3 GUI状態

- `total_duration: float`、`overlap_sec: float`、`loop_enabled: bool`、`output_dir: Path`。
- `parts_cache: list[(S,E,frames)]`（変換・プレビュー共用、再計算は総時間/重なり/ループ変更時のみ）。
- サマリ表示例: `分割: 3ファイル (60.0s/60.0s/34.0s) 重なり2.0s`。
- プレビューpart切替: `QComboBox (part01〜N)`＋既存3Dビューア再利用。

### 3.4 CLI I/O

- 入力: LLSD群＋`--total-duration`（省略時はGUI同様の既定5.0s＋均等配置）。
- 出力: ディレクトリに `_partNN.bvh`。`--max-split`は当面60固定の表示のみ（可変化はOut of Scope）。

## 4. プラットフォーム特有の制約への対処

- **Python/PySide6**: 100レーン描画は`QScrollArea`縦スクロール＋可視域のみ描画（`paintEvent`でクリップ）。重い補間中はプログレス逐次更新で固まり感を抑える。
- **SL互換**: 各part≤60秒・`Frame Time≧0.01`を分割側で保証。`sl_compat`基準フレームはpart毎に付与（テレポート防止を全partで維持）。
- **LSL連携（ツール外）**: タイマー間隔＝`part長−重なり`で次partを`llStartAnimation`→旧を`llStopAnimation`する運用をREADMEに記載（スクリプト本体は本ツールに含めない）。

## 5. エラーハンドリングとエッジケース

| ケース | 検出 | 動作 |
|---|---|---|
| 重なり≧分割長 | `split_frames`先頭 | `max_sec/2`にクランプ＋警告ログ |
| ループ秒の丸め | `loop_closure` | `k=round(L/dt)`、k=0なら追記なし |
| フレーム0件 | 呼出直後 | `ValueError`（既存踏襲） |
| 1〜2件入力 | 均一化側 | 既存どおり（dt=D/(n-1)）、分割は通常適用 |
| 最終part極短 | 分割末尾 | そのまま出力（合併しない） |
| 縮退part（新規格子なし） | `split_frames` | 返さない（先頭partは保持）。`(S,E)` を警告ログに記録 |
| 疎dt（`dt > overlap`） | `split_frames`先頭 | 警告ログ（重なり内に格子点なしの可能性） |
| ループ追記k=0 | `loop_closure_frames` | 警告ログ（閉包効果なし）。追記なし |
| 出力フォルダ未指定 | GUI | 先頭ファイル名＋`_split/`に自動作成 |
| 100件超 | 追加時 | 追加拒否＋メッセージ（既存20件制限の拡張版） |

## 6. 要件→設計トレーサビリティ

- FR-1（600s/100件）→ `timeline.MAX_DURATION`＋`gui.MAX_FILES`＋Spin上限。
- FR-2（60s分割/命名/フォルダ）→ `split_frames`＋`gui`出力解決。
- FR-3（重なり複製）→ `split_frames`の両part包含。
- FR-4（ループ閉包）→ `loop_closure_frames`＋チェックボックス。
- FR-5（レーン化/分割線/重なり帯）→ `TimelineView`再設計。
- FR-6（プレビュー/part切替）→ `parts_cache`＋ComboBox。
- FR-7（CLI）→ 新規引数5件。

## 7. スコープ外の再確認

- LSLスクリプト本体、自動アップロード、レンジモデル、分割長可変、非Windows対応は扱わない。

## 8. 承認条件

- 本書でOKなら「承認（コーディングへ）」と返答ください。承認後は新ブランチ `feature/long-animation-split` を`main`から切ってコーディングに入ります（検証も同ブランチ）。
