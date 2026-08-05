import { useCallback, useEffect, useState } from "react";

import { getResumeDraftCandidates } from "../api/agent";
import { toAppError, type AppErrorState } from "../api";
import type { ResumeDraftCandidateResponse } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";
import { buildDefaultSelection, toggleCandidate } from "../utils/resumeDraftCandidates";

/**
 * ドラフトに載せるリポジトリ候補の取得と選択状態を管理するフック（ADR-0026 決定 2）。
 *
 * マウント時に候補を全件取得し、backend が示した `default_selected` を初期選択にする。
 * 以降の採否はユーザーの操作だけで決まり、機械が選択を書き換えることはない
 * （デフォルト非選択のものも自由に選び直せる）。選択の計算そのものは
 * `utils/resumeDraftCandidates` の純関数に置き、ここは取得と state 管理に専念する。
 *
 * 未連携・旧形式キャッシュ（409）は error に載せる。候補が取れないときに生成へ進めない
 * のは意図した挙動で、呼び出し側は再連携の導線を出す。
 *
 * 引数は**連携結果の分析時刻**（`analyzed_at`）。連携結果がまだ無い間は `null` を渡すと
 * 取得自体を止める（確実に 409 になる要求でエラートーストを出さないため）。再連携で
 * 分析時刻が変わったら自動で取り直す — 連携結果の有無（真偽値）を鍵にすると、既に連携
 * 済みのユーザーが再連携しても true→true で変化せず、古い候補が残ってしまう。
 */
export function useResumeDraftCandidates(analyzedAt: string | null) {
  const [candidates, setCandidates] = useState<ResumeDraftCandidateResponse[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [selectionLimit, setSelectionLimit] = useState(0);
  // 取得対象があれば初回 effect で即取得が走るため、最初から loading 表示にしてちらつきを防ぐ
  const [loading, setLoading] = useState(analyzedAt !== null);
  const [error, setError] = useState<AppErrorState | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getResumeDraftCandidates();
      const list = res.candidates ?? [];
      const limit = res.selection_limit ?? 0;
      setCandidates(list);
      setSelectionLimit(limit);
      setSelected(buildDefaultSelection(list, limit));
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.RESUME_DRAFT));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (analyzedAt === null) {
      setLoading(false);
      return;
    }
    void reload();
  }, [analyzedAt, reload]);

  /** 候補の採否を切り替える（上限に達している場合、未選択の追加だけが抑止される）。 */
  const toggle = useCallback(
    (fullName: string) => {
      setSelected((prev) => toggleCandidate(prev, fullName, selectionLimit));
    },
    [selectionLimit],
  );

  return { candidates, selected, selectionLimit, loading, error, toggle, reload };
}
