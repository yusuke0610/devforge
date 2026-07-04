import { useEffect, useRef, useState } from "react";

import { generateResumeDraftPdfBlobUrl } from "../api/agent";
import { toAppError, type AppErrorState } from "../api";
import type { AgentModelAlias } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";

/**
 * 経歴書ドラフト PDF の生成とプレビュー状態を管理するフック（ADR-0018）。
 *
 * 生成はサーバー側で LLM を 1 回呼ぶ同期処理（十数秒〜数十秒）のため、
 * generating 中はボタンを無効化して二重実行を防ぐ。生成物は DB に保存されず、
 * previewUrl（Blob URL）のみがこのフックのライフサイクルで管理される。
 *
 * @param model 使用モデル（ユーザーメニューで選択中のグローバル設定を渡す）
 */
export function useResumeDraftPdf(model: AgentModelAlias) {
  const [generating, setGenerating] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<AppErrorState | null>(null);
  // アンマウント時のクリーンアップと、再生成時の旧 URL 解放に使う（Blob リーク防止）
  const previewUrlRef = useRef<string | null>(null);

  /** プレビュー URL を差し替える。既存の Blob URL があれば解放してから新しい値をセットする。 */
  const updatePreviewUrl = (url: string | null) => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    previewUrlRef.current = url;
    setPreviewUrl(url);
  };

  // アンマウント時に残っている Blob URL を解放する（プレビュー表示中の画面離脱でリークしない）
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  /** ドラフト PDF を生成してプレビュー URL をセットする。 */
  const generate = async () => {
    if (generating) return;
    setGenerating(true);
    setError(null);
    try {
      updatePreviewUrl(await generateResumeDraftPdfBlobUrl(model));
    } catch (e) {
      // 409（連携データ不足）等は backend の message / action をそのまま表示する
      setError(toAppError(e, FALLBACK_MESSAGES.RESUME_DRAFT));
    } finally {
      setGenerating(false);
    }
  };

  /** プレビューを閉じ、Blob URL を解放する。 */
  const closePreview = () => {
    updatePreviewUrl(null);
  };

  return { generating, previewUrl, error, generate, closePreview };
}
