import { useState, useEffect, useCallback } from "react";
import {
  generateAnalysis,
  listAnalyses,
  deleteAnalysis,
  getAnalysisStatus,
  retryAnalysis,
  toAppError,
  type CareerAnalysisResponse,
} from "../../api";
import { FALLBACK_MESSAGES } from "../../constants/messages";
import type { AppErrorState } from "../../utils/appError";
import { isInProgressStatus } from "../../utils/taskStatus";
import { useTaskPolling } from "../useTaskPolling";

export type CareerAnalysisPhase = "loading" | "input" | "polling" | "list" | "detail";

/**
 * キャリアパス分析ページのフェーズ・データ・操作を管理するフック。
 * フェーズ管理・ポーリング・一覧取得・生成・削除を担う。
 */
export function useCareerAnalysisPage() {
  const [phase, setPhase] = useState<CareerAnalysisPhase>("loading");
  const [error, setError] = useState<AppErrorState | null>(null);
  const [analyses, setAnalyses] = useState<CareerAnalysisResponse[]>([]);
  const [pollingId, setPollingId] = useState<number | null>(null);

  const reloadAnalyses = useCallback(async () => {
    try {
      const data = await listAnalyses();
      setAnalyses(data);
      return data;
    } catch {
      return [];
    }
  }, []);

  const { startPolling, isPolling } = useTaskPolling({
    checkStatus: () => getAnalysisStatus(pollingId!),
    onCompleted: async () => {
      const data = await reloadAnalyses();
      setPhase(data.length > 0 ? "list" : "input");
    },
    onFailed: (err) => {
      setError(err);
      reloadAnalyses().then((data) => {
        setPhase(data.length > 0 ? "list" : "input");
      });
    },
  });

  // 初回ロード: 一覧取得 + pending/processing があればポーリング再開
  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const data = await listAnalyses();
        if (!active) return;
        setAnalyses(data);

        const pending = data.find((a) => isInProgressStatus(a.status));
        if (pending) {
          setPollingId(pending.id);
          setPhase("polling");
        } else {
          setPhase(data.length > 0 ? "list" : "input");
        }
      } catch {
        if (!active) return;
        setPhase("input");
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  // pollingId がセットされたらポーリング開始
  useEffect(() => {
    if (pollingId !== null && phase === "polling" && !isPolling) {
      startPolling();
    }
  }, [pollingId, phase, isPolling, startPolling]);

  /**
   * 指定ポジションで AI 分析を開始する。
   */
  const handleGenerate = async (targetPosition: string) => {
    if (!targetPosition.trim()) return;
    setError(null);
    try {
      const result = await generateAnalysis(targetPosition.trim());
      setPollingId(result.id);
      setPhase("polling");
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.ANALYSIS));
      setPhase("input");
    }
  };

  /**
   * 指定 ID の分析を削除する。
   * 成功時は削除後の一覧を返す。失敗時は null を返す。
   */
  const handleDelete = async (id: number): Promise<CareerAnalysisResponse[] | null> => {
    try {
      await deleteAnalysis(id);
      const updated = analyses.filter((a) => a.id !== id);
      setAnalyses(updated);
      return updated;
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.ANALYSIS_DELETE));
      return null;
    }
  };

  /**
   * 失敗した分析（failed / dead_letter）を再実行する。
   * 成功時はポーリングを再開する。
   */
  const handleRetry = async (id: number) => {
    setError(null);
    try {
      await retryAnalysis(id);
      setPollingId(id);
      setPhase("polling");
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.ANALYSIS_RERUN));
    }
  };

  return {
    phase,
    setPhase,
    error,
    analyses,
    handleGenerate,
    handleDelete,
    handleRetry,
  };
}
