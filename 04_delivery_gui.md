# 04_delivery_gui.md — GUIレイアウト変更 納品書（README段階）

- 日付: 2026-10-04
- ブランチ: `feature/gui-mockup-align`（`feature/long-animation-split` のtipから分岐、未push・未マージ）
- 承認履歴: 要件→設計→G-1→G-2→G-3→G-4→検証(FB対応G-5/G-6/G-7)→README→検証完了→納品承認（2026-10-04）

## 納品物（branch内）

| commit | 内容 |
|---|---|
| `cba3027` | PreviewPanel抽出・単独Viewer薄ラッパー化・テスト6件 |
| `08dd77a` | 3ライン構成・20/60/20記憶・折畳み・テスト7件 |
| `d19efb8` | 縦パン・最小幅対策・テスト3件 |
| `caab0e4` | ダークテーマ・pos()修正・テスト3件 |
| `913e427` | 検証FB5点（視点順/幅固定/自動表示/情報行）・テスト5件 |
| `cc63530` | 幅ハード固定・背景黒化・テスト3件 |
| `c904b96` | プレビューボタン削除・part選択移動・テスト3件 |
| `f215d98` | README日英＋9-a |

- テスト: pytest 89件全緑（-W errorでも自コード警告ゼロ）。検証シナリオ `02_test_scenario_gui.md`（G-1〜G-6クリア）。
- 未追跡残置: `00_requirements_gui.md`、`01_design_gui.md`、`02_test_scenario*.md`、`NEXT_gui_mockup_requirements_memo.md`、`layout-preview.html`。

## 保留（ユーザー指示）

- PR作成・push・ビルド・リリース・GitHub公開は未実施。再開時は指示をもらうこと。

## 次回候補

- B-3 プレビュー連続再生、B-4 警告文日英化（`NEXT_gui_mockup_requirements_memo.md`）
