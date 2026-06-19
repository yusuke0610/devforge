import { useCallback } from "react";

/**
 * バリデーション失敗時に対象入力へフォーカス＆スクロールするための ref コールバックを返す。
 *
 * `active` が true のときに要素がマウント（または ref が再アタッチ）されると、
 * その要素を画面中央へスクロールしてフォーカスする。`active` が false→true に変わると
 * useCallback の identity が変わるため React が ref を貼り直し、既存要素にも発火する。
 *
 * DOM id + querySelector 方式と違い「折りたたみ展開後」「モーダル mount 後」でも
 * 要素出現と同時にフォーカスされるため、タイミングずれが起きない。
 */
export function useFocusOnMatch<T extends HTMLElement>(active: boolean) {
  return useCallback(
    (el: T | null) => {
      if (el && active) {
        // scrollIntoView は jsdom 等では未実装のため存在チェックしてから呼ぶ。
        if (typeof el.scrollIntoView === "function") {
          el.scrollIntoView({ block: "center", behavior: "smooth" });
        }
        el.focus({ preventScroll: true });
      }
    },
    [active],
  );
}
