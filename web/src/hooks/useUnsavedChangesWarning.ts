import { useEffect } from "react";

/**
 * 未保存の変更があるとき、× 閉じ / リロード時にブラウザ標準の離脱確認ダイアログを出すフック。
 *
 * `when` が true の間だけ `beforeunload` リスナを登録し、`preventDefault()` で
 * ブラウザ標準の「このサイトを離れますか？」確認を発火させる。
 *
 * 注意:
 * - SPA 内のアプリ内ページ遷移では `beforeunload` は発火しない（ドキュメントの
 *   アンロード時＝× 閉じ・リロード・別 URL への遷移時のみ）。アプリ内遷移のガードには使えない。
 * - 表示文言はブラウザが管理しており JS から上書きできない（`returnValue` の文字列は無視される）。
 */
export function useUnsavedChangesWarning(when: boolean): void {
  useEffect(() => {
    if (!when) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // 一部の古いブラウザは preventDefault だけでは確認を出さないため returnValue も設定する。
      // 文字列の中身はブラウザ管理で表示には使われない（空文字で十分）。
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [when]);
}
