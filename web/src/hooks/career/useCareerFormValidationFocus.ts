/**
 * 職務経歴書フォームの「保存前バリデーション結果を画面へ反映する」責務をまとめたフック。
 *
 * CareerResumeForm の本体には UI 構成だけを残し、バリデーション失敗時の
 * インラインメッセージ・該当フィールドのフォーカス強調（赤枠）・隠れフィールド
 * （自己PR / 職務要約）のモーダル自動展開・送信フロー分岐をここへ集約する。
 */

import { useCallback, useRef, useState } from "react";
import type { Dispatch, FormEvent, SetStateAction } from "react";

import type { CareerTextFieldKey } from "../../formTypes";
import type { CareerFieldLocator, CareerFormState } from "../../payloadBuilders";
import { validateCareerForm } from "../../payloadBuilders";

type UseCareerFormValidationFocusParams = {
  form: CareerFormState;
  setForm: Dispatch<SetStateAction<CareerFormState>>;
  isAuthenticated: boolean;
  /** 編集中フォームと保存済みの変更点件数。0 件なら確認を挟まず保存する。 */
  changeCount: number;
  /** 変更が無いときの直接保存（戻り値は使わず void で発火する）。 */
  save: () => unknown;
  /** 変更があるときに開く保存確認モーダル。 */
  openSaveConfirm: () => void;
  /** 未ログインで保存を試みたときのログイン導線。 */
  requestLogin: () => void;
  /**
   * ログイン往復の直前に現在のフォームを同期的に退避する。
   * 通常は CareerResumeForm の effect が入力のたびに退避するが、最後の入力直後に
   * 送信されると effect が未反映のままログイン遷移して入力を失う恐れがあるため、
   * ここで同期保存して取りこぼしを防ぐ。
   */
  persistDraft?: (form: CareerFormState) => void;
  /** career_summary / self_pr の失敗時に該当 Markdown モーダルを自動で開く。 */
  openMarkdownField: (field: "career_summary" | "self_pr") => void;
};

export function useCareerFormValidationFocus({
  form,
  setForm,
  isAuthenticated,
  changeCount,
  save,
  openSaveConfirm,
  requestLogin,
  persistDraft,
  openMarkdownField,
}: UseCareerFormValidationFocusParams) {
  /**
   * 保存前バリデーション（項目バリデーション）のメッセージ。
   * 保存/削除/PDF などの非同期処理の成否はトーストで通知するが、
   * 入力エラーは該当フィールドのフォーカス・赤枠とセットでフォーム内にインライン表示する。
   */
  const [validationError, setValidationError] = useState<string | null>(null);

  /**
   * バリデーション失敗フィールドの位置と nonce。保存時にセットし、
   * 該当入力へのフォーカス・赤枠表示・折りたたみ自動展開に使う。
   * nonce は「同じフィールドで再度保存した時」も折りたたみ展開 effect を再発火させるための鍵。
   */
  const [focusTarget, setFocusTarget] = useState<{
    locator: CareerFieldLocator;
    nonce: number;
  } | null>(null);
  const focusNonceRef = useRef(0);

  /** 編集が入ったらフォーカス強調を解除する（赤枠を消す）setForm ラッパー。 */
  const setFormAndClearFocus = useCallback<Dispatch<SetStateAction<CareerFormState>>>(
    (action) => {
      setFocusTarget(null);
      setValidationError(null);
      setForm(action);
    },
    [setForm],
  );

  const onChangeField = useCallback(
    (key: CareerTextFieldKey, value: string) => {
      setFocusTarget(null);
      setValidationError(null);
      setForm((prev) => ({ ...prev, [key]: value }));
    },
    [setForm],
  );

  /** バリデーション失敗を画面へ反映する（メッセージ・フォーカス・モーダル自動展開）。 */
  const applyValidationError = useCallback(
    (validation: NonNullable<ReturnType<typeof validateCareerForm>>) => {
      setValidationError(validation.message);
      focusNonceRef.current += 1;
      setFocusTarget({ locator: validation.locator, nonce: focusNonceRef.current });
      // 自己PR / 職務要約はモーダルへ逃がしているため、該当フィールドの失敗時はモーダルを自動で開く
      // （隠れた textarea には直接フォーカスできないため）。
      if (
        validation.locator.kind === "career_summary" ||
        validation.locator.kind === "self_pr"
      ) {
        openMarkdownField(validation.locator.kind);
      }
    },
    [openMarkdownField],
  );

  const onSubmit = useCallback(
    (event: FormEvent) => {
      event.preventDefault();

      // 未ログインのお試し入力: 全項目の入力完了は求めず（カジュアルな体験を優先）、
      // 氏名だけ確認して（空の経歴書でログインさせない）ドラフトを退避し、ログインを促す。
      // 残りの項目検証はログイン後の実保存時にサーバ側で行う。
      if (!isAuthenticated) {
        if (!form.full_name.trim()) {
          const validation = validateCareerForm(form);
          if (validation) applyValidationError(validation);
          return;
        }
        setValidationError(null);
        setFocusTarget(null);
        // ログイン遷移の直前に最新フォームを同期退避してから促す（effect 任せにせず取りこぼし防止）。
        persistDraft?.(form);
        requestLogin();
        return;
      }

      // 保存前にフォーム全体を検証し、最初のエラーフィールドへフォーカスする。
      const validation = validateCareerForm(form);
      if (validation) {
        applyValidationError(validation);
        return;
      }
      setValidationError(null);
      setFocusTarget(null);
      // 変更が無ければ確認を挟まずそのまま保存。変更があれば確認ダイアログを開く。
      if (changeCount === 0) {
        void save();
        return;
      }
      openSaveConfirm();
    },
    [
      isAuthenticated,
      form,
      applyValidationError,
      requestLogin,
      persistDraft,
      changeCount,
      save,
      openSaveConfirm,
    ],
  );

  return {
    validationError,
    focusLocator: focusTarget?.locator ?? null,
    focusNonce: focusTarget?.nonce ?? 0,
    setFormAndClearFocus,
    onChangeField,
    onSubmit,
  };
}
