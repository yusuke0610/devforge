import { useCallback, useEffect, useRef, useState } from "react";

import {
  fetchResumeDraftPdfBlobUrl,
  getResumeDraftStatus,
  startResumeDraft,
} from "../api/agent";
import { toAppError, type AppErrorState } from "../api";
import type { AgentModelAlias } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";
import { isInProgressStatus } from "../utils/taskStatus";
import { useTaskPolling } from "./useTaskPolling";

/**
 * 経歴書ドラフト PDF の生成とプレビュー状態を管理するフック（ADR-0018 / 非同期化）。
 *
 * 生成はサーバー側のバックグラウンドタスク（LLM 1 コール → PDF 生成）で、enqueue（202）→
 * ステータスポーリング → 完了後に PDF を取得してプレビュー、という流れ。画面を離れても
 * バックエンドの生成は継続し、完了は通知ベルで知らされる。マウント時に進行中タスクを
 * 検知した場合はポーリングを再開する（別画面から戻ったケースの復帰）。
 *
 * 生成物（payload）はサーバーに保存されるが、previewUrl（Blob URL）は本フックの
 * ライフサイクルで管理する（リーク防止のため再生成・アンマウントで revoke する）。
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
  const updatePreviewUrl = useCallback((url: string | null) => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    previewUrlRef.current = url;
    setPreviewUrl(url);
  }, []);

  // アンマウント時に残っている Blob URL を解放する（プレビュー表示中の画面離脱でリークしない）
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  /** 完了後に PDF を取得してプレビュー URL をセットする。 */
  const loadPreview = useCallback(async () => {
    try {
      updatePreviewUrl(await fetchResumeDraftPdfBlobUrl());
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.RESUME_DRAFT));
    } finally {
      setGenerating(false);
    }
  }, [updatePreviewUrl]);

  const { startPolling } = useTaskPolling({
    checkStatus: getResumeDraftStatus,
    onCompleted: () => {
      void loadPreview();
    },
    onFailed: (e) => {
      setError(e);
      setGenerating(false);
    },
  });

  // マウント時に進行中タスクがあればポーリングを再開する（別画面から戻った場合の復帰）
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { status } = await getResumeDraftStatus();
        if (cancelled || !isInProgressStatus(status)) return;
        setGenerating(true);
        startPolling();
      } catch {
        // ステータス取得失敗は復帰を諦めるだけ（生成ボタンから開始できる）
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [startPolling]);

  /** ドラフト生成を開始する（enqueue → ポーリング → 完了で自動プレビュー）。 */
  const generate = async () => {
    if (generating) return;
    setGenerating(true);
    setError(null);
    try {
      await startResumeDraft(model);
      startPolling();
    } catch (e) {
      // 409（連携データ不足）/ 402（残高不足）等は backend の message / action をそのまま表示する
      setError(toAppError(e, FALLBACK_MESSAGES.RESUME_DRAFT));
      setGenerating(false);
    }
  };

  /** プレビューを閉じ、Blob URL を解放する。 */
  const closePreview = () => {
    updatePreviewUrl(null);
  };

  return { generating, previewUrl, error, generate, closePreview };
}
