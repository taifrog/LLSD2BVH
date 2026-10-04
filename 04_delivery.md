# 04_delivery.md — LLSD2BVH Long Animation 納品書（README段階）

- 日付: 2026-10-04
- ブランチ: `feature/long-animation-split`（`main` から分岐、未push・未マージ）
- 承認履歴: 要件→設計→M1→M2→M3→検証(FB対応M4)→README→検証完了→納品承認（2026-10-03〜04）

## 納品物（branch内）

| commit | 内容 |
|---|---|
| `7a9bef9` | timeline核：600s・split/loop-closed・テスト11件 |
| `44c771c` | TimelineViewレーン化・分割線/重なり帯・テスト5件 |
| `a9e371d` | GUI項目・CLI・i18n・結合テスト4件 |
| `2eb6227` | F-1（0値単一化）・F-2（縮退落とし）・W-1（警告）・掃除 |
| `e952eda` | README日英＋9-a＋mockup追跡化 |

- テスト: pytest 59件全緑。検証シナリオ `02_test_scenario.md`（V-1〜V-7クリア）。
- 未追跡残置: `02_test_scenario.md`、`docs/NEXT_gui_mockup_requirements_memo.md`（次回用）。

## 保留（ユーザー指示）

- PR作成・push・ビルド・リリース・GitHub公開は未実施。再開時は指示をもらうこと。
- 再開手順: `git status` →差分確認→機密混入検査（key/token/secret）→push→PR→タグ＋Releases。

## 次回候補

- `docs/NEXT_gui_mockup_requirements_memo.md`（B-1〜B-4、次ブランチ `feature/gui-mockup-align` 案）
- 警告文の日英化、改行の納品時統一（`.gitattributes`＋正規化1発）
