import { useCallback, useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, RefObject } from "react";

/**
 * 取り込み原本パネルのレイアウト（左右リサイズ）を管理するフック。
 *
 * - リサイズ: フォームとパネルの間のスプリッターをドラッグして原本カラム幅を変える。
 *   原本は右カラムなので「幅 = コンテナ右端 - マウス X」。左にドラッグするほど広がる。
 *
 * 幅は最小原本幅とフォームの最小確保幅でクランプする。
 */

type Options = {
  /** 原本カラムの初期幅(px) */
  initialWidth?: number;
  /** 原本カラムの最小幅(px) */
  minWidth?: number;
  /** リサイズ時にフォーム側へ最低限残す幅(px) */
  minFormWidth?: number;
  /**
   * カラム間に存在しフォームにも原本にも属さない固定幅(px)。
   * `.split` の gap(1rem×2=32px) + スプリッター(6px) ≒ 38px。
   * これを差し引いてクランプしないと、フォームの確保幅が gap 分だけ削られ
   * 入力欄が原本カラムに覆い被さって切れる。
   */
  reservedGap?: number;
};

export type UseImportPanelLayoutReturn = {
  /** 原本カラムの現在幅(px) */
  width: number;
  /** スプリッターの mousedown で呼ぶ。ドラッグ中の幅追従を開始する。 */
  startResize: (e: ReactMouseEvent) => void;
};

export function useImportPanelLayout(
  containerRef: RefObject<HTMLElement | null>,
  options: Options = {},
): UseImportPanelLayoutReturn {
  const { initialWidth = 360, minWidth = 280, minFormWidth = 360, reservedGap = 38 } = options;

  const [width, setWidth] = useState(initialWidth);
  const resizingRef = useRef(false);

  // mousemove / mouseup は document 全体で拾う（スプリッター外へカーソルが出ても追従するため）。
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const container = containerRef.current;
      if (!resizingRef.current || !container) return;
      const rect = container.getBoundingClientRect();
      const maxWidth = Math.max(minWidth, rect.width - minFormWidth - reservedGap);
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
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
  }, [containerRef, minWidth, minFormWidth, reservedGap]);

  const startResize = useCallback((e: ReactMouseEvent) => {
    e.preventDefault();
    resizingRef.current = true;
    // ドラッグ中はテキスト選択を抑止し、カーソルを列リサイズに固定する。
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  }, []);

  return { width, startResize };
}
