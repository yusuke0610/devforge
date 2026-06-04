import DOMPurify from "dompurify";

import { foldedSectionLabel, removedStubLabel } from "../constants/messages";
import type { CareerChange, ChangeKind } from "./careerDiff";

/** 種別 → 着色用 CSS クラス。 */
const KIND_CLASS: Record<ChangeKind, string> = {
  added: "diff-added",
  removed: "diff-removed",
  modified: "diff-modified",
};

/** 着色の優先度（左ほど優先）。追加/削除（要素まるごと）は配下の修正色より優先する。 */
const KIND_PRIORITY: ChangeKind[] = ["added", "removed", "modified"];

/**
 * 変更点リストを「form パス文字列 → 種別」の Map にする。
 * パス文字列は `change.path.join(".")`（= backend の data-fp と同じ規則）。
 */
export function buildPathKindMap(changes: CareerChange[]): Map<string, ChangeKind> {
  const map = new Map<string, ChangeKind>();
  for (const c of changes) {
    map.set(c.path.join("."), c.kind);
  }
  return map;
}

/**
 * data-fp ノードのパス（nodePath）と変更パス（changePath）の対応を判定し、最優先の種別を返す。
 *
 * 対応関係は双方向:
 * - `changePath === nodePath`: スカラー値そのものが修正された
 * - `changePath` が `nodePath` の子孫: コンテナノード（配列やブロック）配下で子が変わった
 * - `nodePath` が `changePath` の子孫: 追加/削除された要素の内側ノード（要素種別で着色）
 */
function matchKind(nodePath: string, map: Map<string, ChangeKind>): ChangeKind | null {
  let best: ChangeKind | null = null;
  for (const [changePath, kind] of map) {
    const matched =
      changePath === nodePath ||
      changePath.startsWith(`${nodePath}.`) ||
      nodePath.startsWith(`${changePath}.`);
    if (!matched) continue;
    if (best === null || KIND_PRIORITY.indexOf(kind) < KIND_PRIORITY.indexOf(best)) {
      best = kind;
    }
  }
  return best;
}

/**
 * プレビュー HTML（backend 生成・data-fp 付き）の変更ノードへ着色クラスを付与し、
 * sanitize 済み HTML 文字列を返す。
 *
 * 変更が無ければ sanitize のみ行う。`dangerouslySetInnerHTML` には渡さず、
 * iframe の `srcDoc` に埋め込む前提（呼び出し側で隔離）。
 */
export function annotateHtml(html: string, map: Map<string, ChangeKind>): string {
  if (map.size === 0) return DOMPurify.sanitize(html);

  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.body.querySelectorAll("[data-fp]").forEach((node) => {
    const fp = node.getAttribute("data-fp");
    if (!fp) return;
    const kind = matchKind(fp, map);
    if (kind) {
      node.classList.add("diff-mark", KIND_CLASS[kind]);
    }
  });
  // DOMPurify は既定で data-* 属性・class を保持する（ALLOW_DATA_ATTR=true）。
  return DOMPurify.sanitize(doc.body.innerHTML);
}

/** 項目（data-unit）配下に変更があるか（matchKind と同じ双方向ルール）。 */
function unitChanged(unitPath: string, map: Map<string, ChangeKind>): boolean {
  return matchKind(unitPath, map) !== null;
}

/** 削除プレースホルダ要素を作る（テーブル内なら tr、それ以外は div）。 */
function makeRemovedStub(doc: Document, anchor: Element, text: string, fp: string): Element {
  if (anchor.tagName === "TR") {
    const tr = doc.createElement("tr");
    tr.className = "diff-removed-stub";
    tr.setAttribute("data-removed", fp);
    const td = doc.createElement("td");
    td.colSpan = anchor.children.length || 1;
    td.textContent = text;
    tr.appendChild(td);
    return tr;
  }
  const div = doc.createElement("div");
  div.className = "diff-removed-stub";
  div.setAttribute("data-removed", fp);
  div.textContent = text;
  return div;
}

/**
 * 編集中（form）側の HTML に、削除された項目の跡を示すプレースホルダ（「（削除）…」）を挿入する。
 *
 * baseline では削除項目が赤で残るが、edited では消えて左右がずれる。そこで edited 側に
 * 同じ位置（直前の兄弟項目 data-unit の直後）へ赤いスタブを差し込み、削除を可視化する。
 * data-unit を持たない項目（非休暇の取引先など）はアンカーが取れず挿入をスキップする
 * （サイドバーの変更リストでは表示される）。edited 側専用。
 */
export function injectRemovedPlaceholders(html: string, changes: CareerChange[]): string {
  const removed = changes.filter((c) => c.kind === "removed");
  if (removed.length === 0) return html;

  const doc = new DOMParser().parseFromString(html, "text/html");

  // 親パス（prefix）ごとに index 昇順で処理し、直前に挿入したスタブから連結する。
  const sorted = [...removed].sort((a, b) => {
    const pa = a.path.slice(0, -1).join(".");
    const pb = b.path.slice(0, -1).join(".");
    if (pa !== pb) return pa < pb ? -1 : 1;
    return (a.path[a.path.length - 1] as number) - (b.path[b.path.length - 1] as number);
  });
  const lastByPrefix = new Map<string, Element>();

  for (const change of sorted) {
    const index = change.path[change.path.length - 1];
    if (typeof index !== "number") continue;
    const prefix = change.path.slice(0, -1).join(".");

    let anchor: Element | null = lastByPrefix.get(prefix) ?? null;
    for (let k = index - 1; k >= 0 && !anchor; k--) {
      anchor = doc.querySelector(`[data-unit="${prefix}.${k}"]`);
    }
    if (!anchor || !anchor.parentElement) continue;

    const stub = makeRemovedStub(
      doc,
      anchor,
      removedStubLabel(change.oldValue || change.label),
      change.path.join("."),
    );
    anchor.parentElement.insertBefore(stub, anchor.nextSibling);
    lastByPrefix.set(prefix, stub);
  }

  return doc.body.innerHTML;
}

/**
 * 変更のない「項目（data-unit）」を畳んで `<details>` にまとめる（VSCode/GitHub 風の差分集中表示）。
 *
 * - 変更のある項目・見出し・氏名などの文脈ノードはそのまま残す。
 * - 変更が無く、かつ祖先の項目も変更が無い（＝丸ごと畳まれる）ものを「畳み根」とし、
 *   連続する畳み根を 1 つの `<details><summary>変更なし N 項目を表示</summary>…</details>` に置換する。
 * - `<details>` はネイティブの開閉なので、スクリプト無効の sandbox iframe 内でも展開できる。
 *
 * 変更が無ければ（map 空）何もしない。annotateHtml の後段に適用する前提。
 */
export function foldUnchanged(html: string, map: Map<string, ChangeKind>): string {
  if (map.size === 0) return html;

  const doc = new DOMParser().parseFromString(html, "text/html");
  const units = Array.from(doc.body.querySelectorAll<HTMLElement>("[data-unit]"));

  // 畳み根: 自身が未変更 かつ 最も近い祖先 unit が「変更あり or 不在」のもの。
  const collapseRoots = new Set<Element>();
  for (const u of units) {
    const path = u.getAttribute("data-unit");
    if (!path || unitChanged(path, map)) continue;
    const parentUnit = u.parentElement?.closest<HTMLElement>("[data-unit]");
    if (parentUnit) {
      const parentPath = parentUnit.getAttribute("data-unit");
      if (parentPath && !unitChanged(parentPath, map)) continue; // 祖先ごと畳まれる
    }
    collapseRoots.add(u);
  }
  if (collapseRoots.size === 0) return DOMPurify.sanitize(doc.body.innerHTML);

  // 親ごとに、連続する畳み根の run を 1 つの <details> に置換する。
  const parents = new Set<Element>();
  collapseRoots.forEach((el) => {
    if (el.parentElement) parents.add(el.parentElement);
  });

  parents.forEach((parent) => {
    const children = Array.from(parent.children);
    let i = 0;
    while (i < children.length) {
      if (!collapseRoots.has(children[i])) {
        i++;
        continue;
      }
      let j = i;
      while (j < children.length && collapseRoots.has(children[j])) j++;
      const run = children.slice(i, j);

      const details = doc.createElement("details");
      details.className = "fold";
      const summary = doc.createElement("summary");
      summary.className = "fold-summary";
      summary.textContent = foldedSectionLabel(run.length);
      const bodyDiv = doc.createElement("div");
      bodyDiv.className = "fold-body";

      parent.insertBefore(details, run[0]);
      run.forEach((el) => bodyDiv.appendChild(el));
      details.appendChild(summary);
      details.appendChild(bodyDiv);

      i = j;
    }
  });

  return DOMPurify.sanitize(doc.body.innerHTML);
}
