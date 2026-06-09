import { useAppSelector } from "../store";
import { createInitialCareerForm } from "../formMappers";
import { useCareerDirty } from "../hooks/career/useCareerDirty";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import type { CareerFormState } from "../payloadBuilders";

/**
 * 職務経歴書に未保存の変更があるとき、アプリのどのページ（職務経歴書 / GitHub連携 /
 * ブログ連携 など）からでも × 閉じ・リロード時にブラウザ標準の離脱確認を出すためのガード。
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
  const form = (cache?.form as CareerFormState | undefined) ?? createInitialCareerForm();
  const baseline = (cache?.baseline as CareerFormState | null | undefined) ?? null;
  const dirty = useCareerDirty(form, baseline);

  useUnsavedChangesWarning(isAuthenticated && dirty.any);

  return null;
}
