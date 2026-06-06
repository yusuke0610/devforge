import { useEffect, useState } from "react";

import { FALLBACK_MESSAGES } from "../../constants/messages";
import type { CareerFormState } from "../../payloadBuilders";
import { proofreadCareerForm } from "../../proofread/proofreadClient";
import type { ProofreadIssue } from "../../proofread/types";

/** 校正の取得状態。 */
export type ProofreadState = {
  /** 校正指摘の一覧（フィールド横断・収集順）。 */
  issues: ProofreadIssue[];
  /** 校正処理中フラグ。 */
  proofreading: boolean;
  /** 校正失敗時のメッセージ。 */
  error: string | null;
};

/**
 * デバウンス。ダイアログ表示中に form が変わるのはロールバック操作のみだが、
 * 校正は worker 往復があるため軽くまとめる。
 */
const DEBOUNCE_MS = 300;

/**
 * 保存確認ダイアログが開いている間（`enabled`）、編集中フォームを校正するフック。
 *
 * - ロールバックで form が変わるたびに再校正する（デバウンス付き）。
 * - ダイアログを閉じたら結果をクリアし、次回開いた時に前回の指摘を残さない。
 * - `react-hooks/set-state-in-effect` を避けるため、状態更新はすべて setTimeout 内で行う。
 */
export function useProofread(form: CareerFormState, enabled: boolean): ProofreadState {
  const [issues, setIssues] = useState<ProofreadIssue[]>([]);
  const [proofreading, setProofreading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const handle = setTimeout(
      () => {
        if (!active) return;
        if (!enabled) {
          setIssues([]);
          setError(null);
          setProofreading(false);
          return;
        }
        setProofreading(true);
        setError(null);
        proofreadCareerForm(form)
          .then((result) => {
            if (active) setIssues(result);
          })
          .catch((err) => {
            if (active) {
              setIssues([]);
              setError(err instanceof Error ? err.message : FALLBACK_MESSAGES.PROOFREAD);
            }
          })
          .finally(() => {
            if (active) setProofreading(false);
          });
      },
      enabled ? DEBOUNCE_MS : 0,
    );
    return () => {
      active = false;
      clearTimeout(handle);
    };
  }, [enabled, form]);

  return { issues, proofreading, error };
}
