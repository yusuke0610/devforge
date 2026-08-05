/**
 * 経歴書ドラフトに載せるリポジトリ候補の選択ロジック（決定論・純関数 / ADR-0026 決定 2）。
 *
 * 「機械は候補を落とさず、デフォルト選択状態と理由だけを示す。採否は人間が決める」という
 * 責務分担を web 側で担保する部分。表示テキスト（理由ラベル・単位付きの数値）は
 * `constants/messages.ts` が正本なので、ここでは選択状態の計算だけを扱う。
 */
import type { ResumeDraftCandidateResponse } from "../api/types";

/**
 * 候補一覧から初期選択（デフォルトで採用状態にする full_name）を組み立てる。
 *
 * backend が `default_selected` で示したものだけを、提示順の上位から上限件数まで拾う。
 * 全件が非選択なら空配列を返す（機械が勝手に埋めない）。
 */
export function buildDefaultSelection(
  candidates: ResumeDraftCandidateResponse[],
  limit: number,
): string[] {
  return candidates
    .filter((candidate) => candidate.default_selected)
    .slice(0, limit)
    .map((candidate) => candidate.full_name);
}

/**
 * 候補の選択状態をトグルする。
 *
 * 選択済みなら外す（デフォルト選択を常に覆せる）。未選択なら追加するが、上限に達している
 * ときは何もしない（既存の選択を勝手に押し出さない）。選択解除は上限に関係なく行える。
 */
export function toggleCandidate(
  selected: string[],
  fullName: string,
  limit: number,
): string[] {
  if (selected.includes(fullName)) {
    return selected.filter((name) => name !== fullName);
  }
  if (isSelectionFull(selected, limit)) {
    return selected;
  }
  return [...selected, fullName];
}

/** 選択件数が上限に達しているか（未選択チェックボックスの抑止に使う）。 */
export function isSelectionFull(selected: string[], limit: number): boolean {
  return selected.length >= limit;
}
