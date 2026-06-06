/** テキスト整形・計測のユーティリティ。 */

/**
 * 空白（半角・全角スペース・改行・タブ）を除いた文字数を数える。
 * JS の正規表現 `\s` は全角スペース U+3000 も対象に含むため「空白を含めない」要件を満たす。
 */
export function countNonWhitespace(value: string): number {
  return value.replace(/\s/g, "").length;
}
