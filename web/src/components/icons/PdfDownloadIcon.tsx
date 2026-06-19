/**
 * PDF ダウンロード（出力）マーク。書類 + 「PDF」+ 下向き矢印で「PDFを書き出す」を表す。
 * 色はボタン側の currentColor を継承する。
 */
export function PdfDownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* 書類（右上に折り返し） */}
      <path
        d="M14 2.75H7A2.25 2.25 0 0 0 4.75 5v14A2.25 2.25 0 0 0 7 21.25h10A2.25 2.25 0 0 0 19.25 19V8z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M14 2.75V8h5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      {/* PDF ラベル */}
      <text
        x="12"
        y="13.2"
        textAnchor="middle"
        fontSize="4.6"
        fontWeight="700"
        fontFamily="sans-serif"
        fill="currentColor"
      >
        PDF
      </text>
      {/* 下向きダウンロード矢印 */}
      <path
        d="M12 14.8v3.4M10.2 16.6 12 18.4l1.8-1.8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
