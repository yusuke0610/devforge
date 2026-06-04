/**
 * フォーム値（プリミティブ／配列／プレーンオブジェクトのみで構成）に対し、
 * パス指定で 1 点だけを更新・挿入・削除する immutable な純関数群。
 *
 * 経歴書の「変更点を項目ごとに baseline へ戻す（ロールバック）」処理で用いる。
 * 元のオブジェクトは一切破壊せず、辿った経路だけ浅いコピーした新しい値を返す。
 */

type Path = ReadonlyArray<string | number>;

/**
 * `path` が指す位置の値を `value` で置き換えた新しいオブジェクトを返す。
 * path が空配列のときは `value` 自体を返す（ルート置換）。
 */
export function setAtPath<T>(target: T, path: Path, value: unknown): T {
  if (path.length === 0) return value as T;
  const [head, ...rest] = path;

  if (Array.isArray(target)) {
    const index = head as number;
    const copy = target.slice();
    copy[index] = setAtPath(copy[index], rest, value);
    return copy as unknown as T;
  }

  const obj = target as Record<string, unknown>;
  return {
    ...obj,
    [head]: setAtPath(obj[head as string], rest, value),
  } as unknown as T;
}

/**
 * `path` の末尾セグメントが指す配列要素を取り除いた新しいオブジェクトを返す。
 * 経歴書で「追加された項目」を baseline 状態（＝項目が無い状態）へ戻すのに使う。
 */
export function removeAtPath<T>(target: T, path: Path): T {
  if (path.length === 0) return target;
  const [head, ...rest] = path;

  if (rest.length === 0) {
    if (Array.isArray(target)) {
      const copy = target.slice();
      copy.splice(head as number, 1);
      return copy as unknown as T;
    }
    // 配列以外への remove は今回の用途では発生しない（呼び出し側がパスを保証する）。
    return target;
  }

  if (Array.isArray(target)) {
    const copy = target.slice();
    copy[head as number] = removeAtPath(copy[head as number], rest);
    return copy as unknown as T;
  }

  const obj = target as Record<string, unknown>;
  return {
    ...obj,
    [head]: removeAtPath(obj[head as string], rest),
  } as unknown as T;
}

/**
 * `path` の末尾セグメントが指す位置に `value` を挿入した新しいオブジェクトを返す。
 * 経歴書で「削除された項目」を baseline の値で復元するのに使う。
 */
export function insertAtPath<T>(target: T, path: Path, value: unknown): T {
  if (path.length === 0) return target;
  const [head, ...rest] = path;

  if (rest.length === 0) {
    if (Array.isArray(target)) {
      const copy = target.slice();
      copy.splice(head as number, 0, value);
      return copy as unknown as T;
    }
    return target;
  }

  if (Array.isArray(target)) {
    const copy = target.slice();
    copy[head as number] = insertAtPath(copy[head as number], rest, value);
    return copy as unknown as T;
  }

  const obj = target as Record<string, unknown>;
  return {
    ...obj,
    [head]: insertAtPath(obj[head as string], rest, value),
  } as unknown as T;
}
