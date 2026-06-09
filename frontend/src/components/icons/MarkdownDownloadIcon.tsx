/**
 * Markdown ダウンロード（出力）マーク。Markdown 公式マーク（枠 + 「M」+ 下向き矢印）。
 * マーク自体が下向き矢印を含み「書き出し」を想起させる。色は currentColor を継承する。
 */
export function MarkdownDownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 208 128"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect
        x="5"
        y="5"
        width="198"
        height="118"
        rx="10"
        ry="10"
        fill="none"
        stroke="currentColor"
        strokeWidth="10"
      />
      <path
        fill="currentColor"
        d="M30 98V30h20l20 25 20-25h20v68h-20V59L70 84 50 59v39zm125 0-30-33h20V30h20v35h20z"
      />
    </svg>
  );
}
