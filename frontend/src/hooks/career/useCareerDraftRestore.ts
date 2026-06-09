import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { CareerFormState } from "../../payloadBuilders";
import { clearCareerDraft, loadCareerDraft } from "../../utils/careerDraft";

type UseCareerDraftRestoreOptions = {
  /** 認証済みか。未ログイン（匿名入力中）は何もしない。 */
  isAuthenticated: boolean;
  /** useDocumentForm の loading。ロード確定（新規/既存判定）まで待つ。 */
  loading: boolean;
  /** ロード確定後の documentId。null=サーバに既存経歴書なし（新規ユーザー）。 */
  documentId: string | null;
  /** 退避ドラフトをフォームへ復元する（useDocumentForm.setForm）。 */
  setForm: Dispatch<SetStateAction<CareerFormState>>;
  /** ドラフトを保存する（useDocumentForm.save）。成功で true。 */
  save: (overrideForm?: CareerFormState) => Promise<boolean>;
  /** 既存経歴書ありでドラフトを復元したときの通知（情報トースト）。 */
  notifyRestored: () => void;
};

/**
 * 未ログインで入力 → ログイン往復してきたユーザーの退避ドラフトをフォームへ橋渡しするフック。
 *
 * `/career` で認証済みになった初回（ロード確定後）に一度だけ発火する:
 * 1. 退避ドラフトが無ければ何もしない。
 * 2. サーバに既存経歴書なし（documentId === null）→ ドラフトをそのまま新規保存し、成功時にトースト。
 * 3. 既存経歴書あり → ドラフトをフォームへ復元（dirty 表示）し情報トースト。上書き保存はユーザー操作に委ねる。
 *
 * いずれもフォームへ反映 / 保存を試みた時点でドラフトは破棄する。再マウント時に古いドラフトを
 * 復元し直して既存編集を踏み潰す事故を防ぐため、消費後の sessionStorage は残さない。
 */
export function useCareerDraftRestore({
  isAuthenticated,
  loading,
  documentId,
  setForm,
  save,
  notifyRestored,
}: UseCareerDraftRestoreOptions): void {
  // 一度処理したら再実行しない（同一マウント内での多重発火を防ぐ）。
  const handledRef = useRef(false);

  useEffect(() => {
    if (handledRef.current) return;
    // 未ログイン、またはロード未確定（新規/既存が決まっていない）うちは待機する。
    if (!isAuthenticated || loading) return;

    const draft = loadCareerDraft();
    handledRef.current = true;
    if (!draft) return;

    if (documentId === null) {
      // 新規ユーザー: 退避ドラフトをそのまま保存する。
      void (async () => {
        const ok = await save(draft);
        if (ok) {
          clearCareerDraft();
        } else {
          // 保存失敗（例: バリデーション 422）。データを失わないようフォームへ展開し、
          // ユーザーが修正して再保存できるようにする。エラーはトーストで別途通知済み。
          setForm(draft);
          clearCareerDraft();
        }
      })();
    } else {
      // 既存経歴書あり: ドラフトをフォームへ復元し、更新はユーザー判断に委ねる。
      setForm(draft);
      clearCareerDraft();
      notifyRestored();
    }
  }, [isAuthenticated, loading, documentId, setForm, save, notifyRestored]);
}
