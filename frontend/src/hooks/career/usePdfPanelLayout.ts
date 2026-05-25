import { useCallback, useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, RefObject } from "react";

/**
 * PDF 取り込みパネルのレイアウト（左右リサイズ + 最大化）を管理するフック。
 *
 * - リサイズ: フォームとパネルの間のスプリッターをドラッグして PDF カラム幅を変える。
 *   PDF は右カラムなので「幅 = コンテナ右端 - マウス X」。左にドラッグするほど広がる。
 * - 最大化: VSCode のタブをダブルクリックした時のように、PDF をフォームに覆い被せて全幅表示する
 *   （maximized=true）。再度トグルで元の 2 カラムに戻す。
 *
 * 幅は最小 PDF 幅とフォームの最小確保幅でクランプする。
 */

type Options = {
  /** PDF カラムの初期幅(px) */
  initialWidth?: number;
  /** PDF カラムの最小幅(px) */
  minWidth?: number;
  /** リサイズ時にフォーム側へ最低限残す幅(px) */
  minFormWidth?: number;
};

export type UsePdfPanelLayoutReturn = {
  /** PDF カラムの現在幅(px)。最大化中は無視される。 */
  width: number;
  /** 最大化（フォームに覆い被せて全幅表示）中か */
  maximized: boolean;
  /** スプリッターの mousedown で呼ぶ。ドラッグ中の幅追従を開始する。 */
  startResize: (e: ReactMouseEvent) => void;
  /** 最大化⇔元の 2 カラムをトグルする。 */
  toggleMaximize: () => void;
};

export function usePdfPanelLayout(
  containerRef: RefObject<HTMLElement | null>,
  options: Options = {},
): UsePdfPanelLayoutReturn {
  const { initialWidth = 360, minWidth = 280, minFormWidth = 360 } = options;

  const [width, setWidth] = useState(initialWidth);
  const [maximized, setMaximized] = useState(false);
  const resizingRef = useRef(false);

  // mousemove / mouseup は document 全体で拾う（スプリッター外へカーソルが出ても追従するため）。
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const container = containerRef.current;
      if (!resizingRef.current || !container) return;
      const rect = container.getBoundingClientRect();
      const maxWidth = Math.max(minWidth, rect.width - minFormWidth);
      const raw = rect.right - e.clientX;
      setWidth(Math.min(Math.max(raw, minWidth), maxWidth));
    };
    const onUp = () => {
      if (!resizingRef.current) return;
      resizingRef.current = false;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [containerRef, minWidth, minFormWidth]);

  const startResize = useCallback((e: ReactMouseEvent) => {
    e.preventDefault();
    resizingRef.current = true;
    // ドラッグ中はテキスト選択を抑止し、カーソルを列リサイズに固定する。
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  }, []);

  const toggleMaximize = useCallback(() => setMaximized((prev) => !prev), []);

  return { width, maximized, startResize, toggleMaximize };
}
