import { useFocusOnMatch } from "../../hooks/useFocusOnMatch";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";
import { CharCount } from "../ui/CharCount";
import { ModalShell } from "../ui/ModalShell";
import { MarkdownTextarea } from "./MarkdownTextarea";

type Props = {
  /** ヘッダー / 入力ラベルに使うフィールド名（例: 自己PR / 職務要約） */
  title: string;
  /** Markdown 値 */
  value: string;
  /** 値変更ハンドラ（親の onChangeField 経由で即時に formCache へ反映される） */
  onChange: (value: string) => void;
  /** モーダルを閉じるコールバック（× / オーバーレイ共通） */
  onClose: () => void;
  /** 取り込み補助。ファイルがあれば右カラムに原本ビューを再掲する */
  assist?: UseResumeImportAssistReturn;
  /** バリデーション失敗フィールドとして強調＆フォーカスするか */
  invalid?: boolean;
};

/**
 * 自己PR・職務要約のような単一 Markdown フィールドを専用 UI で入力させるモーダル。
 * 左に大きな入力欄、右に取り込み原本ビュー、右下に文字数カウント（空白除外）を表示する。
 * 保存ボタンは持たず、入力は即時に親（formCache）へ反映される。
 */
export function MarkdownFieldModal({ title, value, onChange, onClose, assist, invalid }: Props) {
  // バリデーション起因でモーダルが開かれた時、入力欄へフォーカスする。
  const textareaRef = useFocusOnMatch<HTMLTextAreaElement>(!!invalid);

  return (
    <ModalShell title={title} onClose={onClose} assist={assist}>
      <MarkdownTextarea
        label={title}
        value={value}
        onChange={onChange}
        rows={16}
        fill
        required
        invalid={invalid}
        textareaRef={textareaRef}
      />
      <CharCount value={value} />
    </ModalShell>
  );
}
