import { useAppSelector } from "../store";
import { createInitialCareerForm } from "../formMappers";
import { useCareerDirty } from "../hooks/career/useCareerDirty";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import type { CareerFormState } from "../payloadBuilders";

/**
 * formCache に入っている unknown 値が CareerFormState として安全に使える形か検証する。
 * useCareerDirty / buildClean は form.experiences.map(...) など配列・文字列フィールドへ
 * ネストアクセスするため、最低限その先頭構造を確認してから渡す（不正値での実行時クラッシュを防ぐ）。
 */
function isCareerFormState(value: unknown): value is CareerFormState {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.full_name === "string" &&
    typeof v.career_summary === "string" &&
    typeof v.self_pr === "string" &&
    Array.isArray(v.experiences) &&
    Array.isArray(v.qualifications)
  );
}

/**
 * 職務経歴書に未保存の変更があるとき、アプリのどのページ（職務経歴書 / GitHub連携
 * など）からでも × 閉じ・リロード時にブラウザ標準の離脱確認を出すためのガード。
 *
 * 未保存判定を職務経歴書フォームのローカル state ではなく Redux の `formCache` から行うため、
 * フォームがアンマウントされていても（別ページへ移動していても）有効に働く。
 * 描画は行わない（null）ので、本コンポーネントの再描画は周辺ツリーに波及しない。
 *
 * 対象はログイン済みのみ。未ログインのお試し入力は baseline が null（未ロード）で
 * dirty.any が常に false になるため自然に対象外となる（入力は sessionStorage に自動退避される）。
 */
export function CareerUnsavedGuard({ isAuthenticated }: { isAuthenticated: boolean }) {
  const cache = useAppSelector((s) => s.formCache.career);
  // 不正・欠損した値が入っていた場合は安全側（未保存なし）に倒す。
  const form = isCareerFormState(cache?.form) ? cache.form : createInitialCareerForm();
  const baseline = isCareerFormState(cache?.baseline) ? cache.baseline : null;
  const dirty = useCareerDirty(form, baseline);

  useUnsavedChangesWarning(isAuthenticated && dirty.any);

  return null;
}
