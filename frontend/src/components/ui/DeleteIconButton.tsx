import type { MouseEvent } from "react";

import { TrashIcon } from "../icons/TrashIcon";
import styles from "./DeleteIconButton.module.css";

/** DeleteIconButton のプロパティ型 */
type DeleteIconButtonProps = {
  /** aria-label / title に使う説明（例: "職務経歴を削除"）。アイコンのみなので必須。 */
  label: string;
  /** 削除実行ハンドラ */
  onClick: () => void;
  /** 配置微調整用の追加クラス（margin-left:auto など） */
  className?: string;
};

/**
 * 項目見出しの右端に置く、ゴミ箱アイコンだけの削除ボタン。
 * 職務経歴 / 取引先 / プロジェクト / 資格で共通利用する。
 * Collapsible の見出し内などに置いても親のトグルを誤発火させないよう stopPropagation する。
 */
export function DeleteIconButton({ label, onClick, className }: DeleteIconButtonProps) {
  const handleClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    onClick();
  };

  return (
    <button
      type="button"
      className={`${styles.deleteIcon}${className ? ` ${className}` : ""}`}
      aria-label={label}
      title={label}
      onClick={handleClick}
    >
      <TrashIcon />
    </button>
  );
}
