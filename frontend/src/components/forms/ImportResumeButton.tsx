import { useRef } from "react";

import type { UseResumeImportReturn } from "../../hooks/career/useResumeImport";

type Props = {
  importState: UseResumeImportReturn;
};

/**
 * 職務経歴書 PDF インポートボタン。
 * クリックでファイルピッカーを開き、選択後にインポート処理を開始する。
 */
export function ImportResumeButton({ importState }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { phase, start } = importState;

  const isLoading = phase === "uploading" || phase === "polling";

  const handleClick = () => {
    if (isLoading) return;
    inputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // 同じファイルを再選択できるよう値をリセットする
    e.target.value = "";
    await start(file);
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        style={{ display: "none" }}
        onChange={handleFileChange}
        aria-label="職務経歴書 PDF を選択"
      />
      <button type="button" onClick={handleClick} disabled={isLoading}>
        {phase === "uploading"
          ? "アップロード中..."
          : phase === "polling"
            ? "解析中..."
            : "PDF からインポート"}
      </button>
    </>
  );
}
