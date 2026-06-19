import { useEffect, useState } from "react";

import { getQualifications, getTechnologyStacks } from "../api";
import type { MasterItem, TechStackMasterItem } from "../api/types";

/** 汎用のキャッシュ付きデータ取得フック */
function useCachedFetch<T>(
  cache: { current: T[] | null },
  fetchFn: () => Promise<T[]>,
): { items: T[]; loading: boolean } {
  const [items, setItems] = useState<T[]>(cache.current ?? []);
  const [loading, setLoading] = useState(cache.current === null);

  useEffect(() => {
    if (cache.current !== null) {
      setItems(cache.current);
      setLoading(false);
      return;
    }

    let active = true;
    (async () => {
      try {
        const data = await fetchFn();
        cache.current = data;
        if (active) setItems(data);
      } catch {
        if (active) setItems([]);
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => { active = false; };
  }, [cache, fetchFn]);

  return { items, loading };
}

/** モジュールレベルのキャッシュ */
const qualificationsCache: { current: MasterItem[] | null } = { current: null };
const techStacksCache: { current: TechStackMasterItem[] | null } = { current: null };

/** 資格マスタを取得するフック */
export function useQualifications() {
  return useCachedFetch(qualificationsCache, getQualifications);
}

/** 技術スタックマスタを取得するフック */
export function useTechnologyStacks() {
  return useCachedFetch(techStacksCache, getTechnologyStacks);
}
