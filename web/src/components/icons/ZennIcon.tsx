/**
 * Zenn 公式ロゴアイコン。
 */
export function ZennIcon({ size = 24 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 88.3 88.3"
      width={size}
      height={size}
    >
      <path
        d="M2.4 83.3h17c.9 0 1.7-.5 2.2-1.2L68.4 5.2c.4-.7-.1-1.4-.8-1.4H51.2c-.7 0-1.4.4-1.8 1L2 82c-.4.6 0 1.3.4 1.3z"
        fill="#3EA8FF"
      />
      <path
        d="M60.3 83.3h15.5c.9 0 1.7-.5 2.2-1.3l8.6-14.8c.4-.7-.1-1.5-.9-1.5H71.2c-.7 0-1.3.3-1.7 1l-9.9 15.3c-.5.7.1 1.3.7 1.3z"
        fill="#3EA8FF"
      />
    </svg>
  );
}
