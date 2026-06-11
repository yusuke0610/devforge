# スコープ: プロジェクト詳細（project）

operations の field は `description` と `role` のみ許可する。
description の推奨文字数は 300〜400字（システム上限とは別の品質基準）、role はプロジェクトでの役割を表す 1 行のタイトル。

# 品質基準
- description は課題 → 行動 → 成果の構造で書く（PAR 形式）
- 数値・規模・技術スタックを具体的に含める（現在の内容にある事実のみ）
- 役割と担当フェーズを明確にする
- description の文字数: 300〜400字

# データ構造の分岐ルール
- `is_it_company = false` の経歴は `clients` を持たず、`Experience.description` のみを使う
- `is_vacation = true` の client は取引先ではなく在籍中の休暇を表す。`name` / `projects` は無視し、`vacation_start_date` / `vacation_end_date` / `vacation_is_current` / `vacation_description` を使う
- `is_current = true` の場合、対応する `end_date` は `""` に正規化されている（空文字は「現在も継続中」を意味する）

# 思考ステップ（内部分析。出力には含めない）
1. 現在の description の問題点を特定する（抽象的・成果がない・数値がない 等）
2. 現在の内容から課題・行動・成果として使える事実を抽出する
3. 技術スタック・フェーズ・チーム規模との整合性を確認する
4. PAR 形式（課題→行動→成果）で 300〜400字に書き直す

対象プロジェクトの現在のデータ（役割・詳細・技術スタック・担当工程）は、user メッセージの「# 現在の内容」に JSON で渡される。
