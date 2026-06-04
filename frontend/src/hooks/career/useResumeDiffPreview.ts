import { useEffect, useMemo, useState } from "react";

import { getCareerResumePreview, type ResumePreviewResponse } from "../../api/resumes";
import type { ResumeCreate } from "../../api/types";
import { FALLBACK_MESSAGES } from "../../constants/messages";
import { buildCareerPayload, type CareerFormState } from "../../payloadBuilders";

/** 左右 diff プレビューの取得状態。 */
export type ResumeDiffPreview = {
  /** 左ペイン（保存済み）の整形 HTML。未保存・取得不可なら null。 */
  baselineHtml: string | null;
  /** 右ペイン（編集中）の整形 HTML。取得前・エラー時は null。 */
  editedHtml: string | null;
  /** iframe に流し込む画面用 CSS（baseline / edited で共通）。 */
  css: string;
  /** 編集中プレビューの取得中フラグ。 */
  loading: boolean;
  /** 取得失敗・入力不正のメッセージ。 */
  error: string | null;
};

/**
 * 編集中プレビュー再取得の遅延。diff モーダル表示中に form が変わるのはロールバック操作のみで、
 * 連続入力は発生しないため即時反映（0ms）にする。setTimeout 自体は effect 本体での同期 setState を
 * 避ける（react-hooks/set-state-in-effect 回避）目的で残す。
 */
const EDITED_DEBOUNCE_MS = 0;

/** form/baseline を payload 化する（render 中に評価し、effect 内の同期 setState を避ける）。 */
function toPayload(state: CareerFormState | null): { payload?: ResumeCreate; error?: string } {
  if (!state) return {};
  try {
    return { payload: buildCareerPayload(state) };
  } catch (e) {
    return { error: e instanceof Error ? e.message : FALLBACK_MESSAGES.PREVIEW };
  }
}

/**
 * baseline（保存済み）と form（編集中）を backend のプレビュー API で整形 HTML 化するフック。
 *
 * - baseline はモーダルを開いている間不変なので、開いた時に 1 回だけ取得する。
 * - form はロールバックで変わるため、その都度（即時に）再取得して右ペインへ反映する。
 * - payload 化できない（未保存の空 baseline・入力不正）場合はクラッシュせず安全側に倒す
 *   （baseline=null 表示 / form=エラーメッセージ）。payload 化は render 中（useMemo）で評価する。
 */
export function useResumeDiffPreview(
  form: CareerFormState,
  baseline: CareerFormState | null,
  enabled: boolean,
): ResumeDiffPreview {
  const [baselinePreview, setBaselinePreview] = useState<ResumePreviewResponse | null>(null);
  const [editedPreview, setEditedPreview] = useState<ResumePreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // payload 化を render 中に評価（不正入力はここで検出し、effect では同期 setState しない）。
  const baselinePayload = useMemo(() => toPayload(baseline).payload ?? null, [baseline]);
  const edited = useMemo(() => toPayload(form), [form]);

  // baseline プレビュー: モーダルを開いた時（enabled / baseline 変化時）に 1 回取得。
  useEffect(() => {
    if (!enabled || !baselinePayload) return;
    let active = true;
    getCareerResumePreview(baselinePayload)
      .then((res) => {
        if (active) setBaselinePreview(res);
      })
      .catch(() => {
        if (active) setBaselinePreview(null);
      });
    return () => {
      active = false;
    };
  }, [enabled, baselinePayload]);

  // 編集中プレビュー: enabled の間、form 変化のたびに即時取得（ロールバックを右ペインへ反映）。
  useEffect(() => {
    if (!enabled || !edited.payload) return;
    const payload = edited.payload;
    let active = true;
    const handle = setTimeout(() => {
      setLoading(true);
      setFetchError(null);
      getCareerResumePreview(payload)
        .then((res) => {
          if (active) setEditedPreview(res);
        })
        .catch((err) => {
          if (active) {
            setFetchError(err instanceof Error ? err.message : FALLBACK_MESSAGES.PREVIEW);
          }
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, EDITED_DEBOUNCE_MS);
    return () => {
      active = false;
      clearTimeout(handle);
    };
  }, [enabled, edited]);

  // 入力不正は editedHtml を null にしてエラーを優先表示する。
  const editedHtml = edited.error ? null : (editedPreview?.html ?? null);

  return {
    baselineHtml: baselinePreview?.html ?? null,
    editedHtml,
    css: editedPreview?.css ?? baselinePreview?.css ?? "",
    loading,
    error: edited.error ?? fetchError,
  };
}
