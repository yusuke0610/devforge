/**
 * 値が等しいかを判定する。プリミティブと配列・プレーンオブジェクトを再帰比較する。
 * フォーム値はプリミティブ／配列／プレーンオブジェクトのみで構成されている前提。
 *
 * dirty 判定（未保存マーク）で local / baseline の差分検出に用いる純関数。
 * 等価判定ロジックを 1 か所に集約し、各 hook での乖離を防ぐ。
 */
export function isDeepEqual(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (a === null || b === null) return false;
  if (typeof a !== "object" || typeof b !== "object") return false;

  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b)) return false;
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!isDeepEqual(a[i], b[i])) return false;
    }
    return true;
  }

  const objA = a as Record<string, unknown>;
  const objB = b as Record<string, unknown>;
  const keysA = Object.keys(objA);
  const keysB = Object.keys(objB);
  if (keysA.length !== keysB.length) return false;
  for (const k of keysA) {
    if (!Object.prototype.hasOwnProperty.call(objB, k)) return false;
    if (!isDeepEqual(objA[k], objB[k])) return false;
  }
  return true;
}
