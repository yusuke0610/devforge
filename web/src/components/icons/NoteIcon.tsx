/**
 * note 公式ロゴアイコン。
 */
export function NoteIcon({ size = 24 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      width={size}
      height={size}
    >
      <rect width="100" height="100" rx="14" fill="#41C9B4" />
      <text
        x="50"
        y="72"
        textAnchor="middle"
        fontFamily="Arial, Helvetica, sans-serif"
        fontWeight="bold"
        fontSize="62"
        fill="#FFFFFF"
      >
        n
      </text>
    </svg>
  );
}
