/**
 * enabled で取得可否を制御する単発フェッチの共通フック。
 *
 * 「enabled が true の間だけ取得 → loading / error / data を管理 → refresh で再取得」
 * という同型のロジックを各データ取得フック（残高・使用量・レート等）が個別に持っていたため、
 * ここへ集約する。`refresh` が重なったときに古い応答が新しい状態を上書きしないよう
 * リクエスト順序（seq）ガードを内蔵する。
 */

import { useCallback, useEffect, useRef, useState } from "react";

type UseAsyncResourceOptions<T> = {
  /** false の間は自動取得しない（無料モデル選択中に残高 API を叩かない等）。省略時は常に取得。 */
  enabled?: boolean;
  /** data の初期値（未取得状態を表す値）。 */
  initialData: T;
  /** 取得失敗時、Error でない / message が無い場合に使う日本語フォールバック。 */
  fallbackMessage: string;
};

export type UseAsyncResourceReturn<T> = {
  data: T;
  loading: boolean;
  error: string | null;
  /** 手動再取得。呼び出し側が購入・送信後などに最新化するのに使う。 */
  refresh: () => Promise<void>;
};

export function useAsyncResource<T>(
  fetcher: () => Promise<T>,
  { enabled = true, initialData, fallbackMessage }: UseAsyncResourceOptions<T>,
): UseAsyncResourceReturn<T> {
  const [data, setData] = useState<T>(initialData);
  // enabled なら初回 effect で即取得が走るため、最初から loading 表示にしてちらつきを防ぐ。
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  // refresh が重なったとき、古い応答が新しい状態を上書きしないよう最新の seq だけ反映する。
  const requestSeqRef = useRef(0);
  // fetcher は呼び出し側でインライン定義されることが多く毎レンダー identity が変わる。
  // refresh / effect を安定させるため、実体は ref に逃がして常に最新を参照する。
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refresh = useCallback(async () => {
    const seq = ++requestSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current();
      if (seq === requestSeqRef.current) setData(result);
    } catch (e) {
      if (seq === requestSeqRef.current) {
        // Error でも message が空文字なら fallback を使う（message が無い場合は fallback という契約どおり）。
        const message = e instanceof Error ? e.message : "";
        setError(message || fallbackMessage);
      }
    } finally {
      if (seq === requestSeqRef.current) setLoading(false);
    }
  }, [fallbackMessage]);

  useEffect(() => {
    // 無効化された瞬間に進行中リクエストを stale 化し（seq を進める）、後追いで解決した応答が
    // state を上書きしないようにする。これで「enabled=false の間は取得しない」契約を
    // true→false 遷移でも守る。
    if (!enabled) {
      requestSeqRef.current += 1;
      setLoading(false);
      return;
    }
    void refresh();
  }, [enabled, refresh]);

  return { data, loading, error, refresh };
}
