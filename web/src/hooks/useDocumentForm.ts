import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { FALLBACK_MESSAGES, UI_MESSAGES } from "../constants/messages";
import { useAppDispatch, useAppSelector } from "../store";
import {
  clearCache,
  setBaseline,
  setCache,
  type FormCacheKey,
} from "../store/formCacheSlice";

export type UseDocumentFormOptions<FormState, Payload, Response extends { id: string }> = {
  createInitialForm: () => FormState;
  loadLatest: () => Promise<Response>;
  createDocument: (payload: Payload) => Promise<Response>;
  updateDocument: (id: string, payload: Payload) => Promise<Response>;
  deleteDocument?: () => Promise<{ message: string }>;
  buildPayload: (form: FormState) => Payload;
  mapResponseToForm: (response: Response) => FormState;
  successMessage: string;
  beforeSave?: () => Promise<void>;
  /** 指定するとページ遷移してもフォーム状態が Redux ストアに保持される */
  cacheKey?: FormCacheKey;
  /**
   * true の間はマウント時の loadLatest を行わず、空フォームで起動する。
   * 未ログインのお試し入力（匿名モード）で 401 を無駄打ちしないために使う。
   */
  skipLoad?: boolean;
};

export function useDocumentForm<FormState, Payload, Response extends { id: string }>({
  createInitialForm,
  loadLatest,
  createDocument,
  updateDocument,
  deleteDocument,
  buildPayload,
  mapResponseToForm,
  successMessage,
  beforeSave,
  cacheKey,
  skipLoad = false,
}: UseDocumentFormOptions<FormState, Payload, Response>) {
  const dispatch = useAppDispatch();
  const cached = useAppSelector((s) =>
    cacheKey ? s.formCache[cacheKey] : undefined,
  );

  const [form, setFormRaw] = useState<FormState>(() => {
    if (cached?.form) return cached.form as FormState;
    return createInitialForm();
  });
  /**
   * dirty 判定の基準値となるサーバ最新スナップショット。
   * loadLatest / save 成功時にのみ更新し、編集中の setForm では変えない。
   * 未ロード状態では null（dirty 判定側で null は「すべて未変更」として扱う）。
   */
  const [baseline, setBaselineState] = useState<FormState | null>(
    (cached?.baseline as FormState | null) ?? null,
  );
  const [documentId, setDocumentId] = useState<string | null>(
    cached?.documentId ?? null,
  );
  const [loading, setLoading] = useState(!cached && !skipLoad);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  /** キャッシュキーを ref で保持（dispatch 時の最新値参照用） */
  const cacheKeyRef = useRef(cacheKey);
  cacheKeyRef.current = cacheKey;

  /**
   * documentId を ref で保持しておく。setForm 経由で setCache を発火するとき、
   * 「documentId は今 null」と誤って書き込むと、ページ再マウント時に POST にフォールバックして
   * UPDATE のはずが CREATE になる事故が起きる。ローカル state と同期する。
   */
  const documentIdRef = useRef<string | null>(documentId);
  documentIdRef.current = documentId;

  /**
   * setForm のラッパー: Redux キャッシュも同時更新する。
   *
   * setFormRaw の updater は React の render phase 内で実行されるため、
   * その中で同期 dispatch すると useAppSelector が render 中に自身を更新する形になり、
   * 「Cannot update a component while rendering a different component」警告が出る。
   * これを避けるため、dispatch は queueMicrotask で render phase の外に逃がす。
   * 結果として Redux への書き込みは現在の render commit 直後（次の microtask）に行われる。
   */
  const setForm: Dispatch<SetStateAction<FormState>> = useCallback(
    (action) => {
      setFormRaw((prev) => {
        const next = typeof action === "function" ? (action as (prev: FormState) => FormState)(prev) : action;
        if (cacheKeyRef.current) {
          const key = cacheKeyRef.current;
          queueMicrotask(() => {
            dispatch(
              setCache({
                key,
                form: next,
                documentId: documentIdRef.current,
              }),
            );
          });
        }
        return next;
      });
    },
    [dispatch],
  );

  /** フォームと documentId を同時に Redux キャッシュに反映する */
  const updateCache = useCallback(
    (formData: FormState, docId: string | null) => {
      if (cacheKeyRef.current) {
        dispatch(
          setCache({ key: cacheKeyRef.current, form: formData, documentId: docId }),
        );
      }
    },
    [dispatch],
  );

  /** baseline をローカル state と Redux キャッシュ両方に反映する（サーバ同期完了時のみ呼ぶ）。 */
  const commitBaseline = useCallback(
    (snapshot: FormState) => {
      setBaselineState(snapshot);
      if (cacheKeyRef.current) {
        dispatch(setBaseline({ key: cacheKeyRef.current, baseline: snapshot }));
      }
    },
    [dispatch],
  );

  useEffect(() => {
    // キャッシュが既にある場合・匿名モード（skipLoad）の場合は API ロードをスキップ。
    // 匿名モードは空フォームで起動し、ログイン後の再マウントで初めてロードする。
    if (cached || skipLoad) return;

    let active = true;
    setLoading(true);

    (async () => {
      try {
        const latest = await loadLatest();
        if (!active) return;
        setDocumentId(latest.id);
        const mapped = mapResponseToForm(latest);
        setFormRaw(mapped);
        updateCache(mapped, latest.id);
        commitBaseline(mapped);
      } catch {
        if (!active) return;
        // DB に未登録（404）のユーザー向け: 初期空フォームを baseline として確定する。
        // これにより以後のユーザー編集はすべて baseline との差分として検出され、
        // 各フィールド・配下要素（プロジェクト等）の未保存マークが正しく表示される。
        commitBaseline(createInitialForm());
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
    // cached / createInitialForm を依存配列に含めないことで、キャッシュ更新や呼び出し側の
    // インライン関数生成のたびに再 fetch しない（無限ループの原因になる）。
    // createInitialForm は catch 経路でしか参照されないため、最新値を見る必要は実用上ない。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadLatest, mapResponseToForm, updateCache, commitBaseline, skipLoad]);

  const saveButtonText = useMemo(() => {
    if (saving) return UI_MESSAGES.FORM_SAVING;
    return documentId ? UI_MESSAGES.FORM_UPDATE : UI_MESSAGES.FORM_SAVE;
  }, [documentId, saving]);

  /**
   * フォームを保存する。`overrideForm` を渡すと現在の form state ではなくそれを保存する
   * （ログイン後に退避ドラフトを state 反映を待たず即保存するケースで使う）。
   * 成功で true、失敗で false を返す（呼び出し側が成否に応じてドラフト破棄を判断できる）。
   */
  const save = async (overrideForm?: FormState): Promise<boolean> => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      if (beforeSave) await beforeSave();
      const payload = buildPayload(overrideForm ?? form);
      const saved = documentId
        ? await updateDocument(documentId, payload)
        : await createDocument(payload);
      const mapped = mapResponseToForm(saved);
      setDocumentId(saved.id);
      setFormRaw(mapped);
      updateCache(mapped, saved.id);
      commitBaseline(mapped);
      setSuccess(successMessage);
      return true;
    } catch (submitError) {
      const message =
        submitError instanceof Error
          ? submitError.message
          : FALLBACK_MESSAGES.SAVE;
      setError(message);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const deleteDoc = async () => {
    if (!deleteDocument || !documentId) return;
    setDeleting(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await deleteDocument();
      setDocumentId(null);
      const initial = createInitialForm();
      setFormRaw(initial);
      setBaselineState(null);
      if (cacheKeyRef.current) {
        dispatch(clearCache(cacheKeyRef.current));
      }
      setSuccess(result.message);
    } catch (deleteError) {
      const message =
        deleteError instanceof Error
          ? deleteError.message
          : FALLBACK_MESSAGES.DELETE;
      setError(message);
    } finally {
      setDeleting(false);
    }
  };

  return {
    form,
    setForm,
    baseline,
    documentId,
    loading,
    saving,
    deleting,
    error,
    success,
    setError,
    setSuccess,
    save,
    deleteDoc,
    saveButtonText,
  };
}
