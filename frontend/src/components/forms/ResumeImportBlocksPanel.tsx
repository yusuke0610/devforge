import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";
import shared from "../../styles/shared.module.css";

type Props = {
  assist: UseResumeImportAssistReturn;
};

/**
 * PDF 取り込み補助の右カラム（割り当て候補ブロック一覧）。
 *
 * アップロードのトリガー（ファイル選択ボタン）はヘッダー側に置く。本パネルは抽出済み
 * ブロックを並べ、クリックで「選択中（緑枠）の入力欄」へ流し込む役割に専念する。
 */
export function ResumeImportBlocksPanel({ assist }: Props) {
  const { blocks, usedIds, loading, error, fileName, handleBlockClick } = assist;

  return (
    <div>
      <p style={{ fontSize: "0.85rem", color: "#333", margin: "0 0 0.6rem" }}>
        {IMPORT_ASSIST_MESSAGES.HINT}
      </p>

      {error && (
        <p className={shared.error} style={{ fontSize: "0.85rem", marginBottom: "0.6rem" }}>
          {error}
        </p>
      )}

      {!loading && blocks.length === 0 && (
        <p style={{ fontSize: "0.85rem", color: "#666" }}>
          {fileName ? IMPORT_ASSIST_MESSAGES.NO_BLOCKS : IMPORT_ASSIST_MESSAGES.EMPTY}
        </p>
      )}

      {loading && (
        <p style={{ fontSize: "0.85rem", color: "#666" }}>{IMPORT_ASSIST_MESSAGES.ANALYZING}</p>
      )}

      {blocks.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
          {blocks.map((block) => {
            const used = usedIds.has(block.id);
            return (
              <button
                key={block.id}
                type="button"
                title={block.text}
                onClick={() => handleBlockClick(block)}
                style={{
                  textAlign: "left",
                  whiteSpace: "normal",
                  wordBreak: "break-word",
                  padding: "0.35rem 0.5rem",
                  borderRadius: "6px",
                  border: "1px solid #d0d0d0",
                  background: used ? "#eaf6ee" : "#fff",
                  // #4: 黒文字で読みやすく（使用済みも黒のまま、背景で区別する）
                  color: "#1a1a1a",
                  fontSize: "0.85rem",
                  cursor: "pointer",
                }}
              >
                <span
                  style={{
                    fontSize: "0.7rem",
                    color: "#fff",
                    background: block.kind === "table" ? "#3b6fd4" : "#6b7280",
                    borderRadius: "4px",
                    padding: "0 0.3rem",
                    marginRight: "0.4rem",
                  }}
                >
                  {block.kind === "table"
                    ? IMPORT_ASSIST_MESSAGES.KIND_TABLE
                    : IMPORT_ASSIST_MESSAGES.KIND_LINE}
                </span>
                {used && <span style={{ color: "#2f9e54", marginRight: "0.3rem" }}>✓</span>}
                {block.text}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
