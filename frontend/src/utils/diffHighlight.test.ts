import { describe, it, expect } from "vitest";

import type { CareerChange } from "./careerDiff";
import { annotateHtml, buildPathKindMap, foldUnchanged, injectRemovedPlaceholders } from "./diffHighlight";

/** テスト用の最小 CareerChange を作る（rollback は使わないのでダミー）。 */
function change(
  path: (string | number)[],
  kind: CareerChange["kind"],
  oldValue = "",
): CareerChange {
  return {
    path,
    label: path.join(" > "),
    kind,
    oldValue,
    newValue: "",
    rollback: (form) => form,
  };
}

describe("buildPathKindMap", () => {
  it("path を '.' 連結したキーで種別を引ける", () => {
    const map = buildPathKindMap([
      change(["full_name"], "modified"),
      change(["experiences", 0, "company"], "modified"),
    ]);
    expect(map.get("full_name")).toBe("modified");
    expect(map.get("experiences.0.company")).toBe("modified");
  });
});

describe("annotateHtml", () => {
  it("スカラー修正は該当 data-fp ノードに diff-modified を付ける", () => {
    const html = '<div data-fp="full_name">山田</div><div data-fp="self_pr">PR</div>';
    const map = buildPathKindMap([change(["full_name"], "modified")]);
    const out = annotateHtml(html, map);
    expect(out).toContain("diff-modified");
    // 変更のない self_pr には付かない
    const doc = new DOMParser().parseFromString(out, "text/html");
    expect(doc.querySelector('[data-fp="self_pr"]')?.className).toBe("");
  });

  it("コンテナノードは配下の子変更で着色される（子孫マッチ）", () => {
    const html =
      '<table><tbody><tr>' +
      '<td data-fp="experiences.0.clients.0.projects.0.technology_stacks">env</td>' +
      '</tr></tbody></table>';
    const map = buildPathKindMap([
      change(["experiences", 0, "clients", 0, "projects", 0, "technology_stacks", 1, "name"], "modified"),
    ]);
    const out = annotateHtml(html, map);
    expect(out).toContain("diff-modified");
  });

  it("追加要素の内側ノードは added で着色される（祖先マッチ）", () => {
    const html = '<span data-fp="experiences.2.company">新会社</span>';
    const map = buildPathKindMap([change(["experiences", 2], "added")]);
    const out = annotateHtml(html, map);
    expect(out).toContain("diff-added");
  });

  it("追加/削除は配下の修正より優先される", () => {
    const html = '<span data-fp="experiences.2.company">X</span>';
    const map = buildPathKindMap([
      change(["experiences", 2], "added"),
      change(["experiences", 2, "company"], "modified"),
    ]);
    const out = annotateHtml(html, map);
    expect(out).toContain("diff-added");
    expect(out).not.toContain("diff-modified");
  });

  it("変更が無ければ着色せず sanitize のみ（script 除去）", () => {
    const html = '<div data-fp="full_name">x</div><script>alert(1)</script>';
    const out = annotateHtml(html, buildPathKindMap([]));
    expect(out).not.toContain("diff-mark");
    expect(out).not.toContain("<script>");
  });
});

describe("foldUnchanged", () => {
  it("変更のない項目は <details> に畳まれ、変更のある項目は残る", () => {
    const html =
      '<div data-unit="experiences.0"><span data-fp="experiences.0.company">A</span></div>' +
      '<div data-unit="experiences.1"><span data-fp="experiences.1.company">B</span></div>';
    const map = buildPathKindMap([change(["experiences", 0, "company"], "modified")]);
    const out = foldUnchanged(html, map);
    expect(out).toContain("<details");
    expect(out).toContain("fold-summary");
    // 変更ありの experiences.0 は畳まれず残る
    expect(out).toContain('data-unit="experiences.0"');
    // 変更なしの experiences.1 は details の中に入る
    expect(out).toContain('data-unit="experiences.1"');
  });

  it("変更ありの親は残し、配下の変更なし項目だけ畳む", () => {
    const html =
      '<div data-unit="experiences.0"><div class="company-body">' +
      '<div data-unit="experiences.0.clients.0.projects.0">P0</div>' +
      '<div data-unit="experiences.0.clients.0.projects.1">P1</div>' +
      "</div></div>";
    const map = buildPathKindMap([
      change(["experiences", 0, "clients", 0, "projects", 0, "role"], "modified"),
    ]);
    const out = foldUnchanged(html, map);
    const doc = new DOMParser().parseFromString(out, "text/html");
    // 親（experiences.0）と変更ありの projects.0 は details の外
    expect(doc.querySelector('details [data-unit="experiences.0"]')).toBeNull();
    expect(doc.querySelector('details [data-unit="experiences.0.clients.0.projects.0"]')).toBeNull();
    // 変更なしの projects.1 は details の中
    expect(
      doc.querySelector('details [data-unit="experiences.0.clients.0.projects.1"]'),
    ).not.toBeNull();
  });

  it("変更なしの親は配下ごと丸ごと畳む（入れ子では畳まない）", () => {
    const html =
      '<div data-unit="experiences.0"><div class="company-body">' +
      '<div data-unit="experiences.0.clients.0.projects.0">P0</div>' +
      "</div></div>";
    const map = buildPathKindMap([change(["qualifications", 0, "name"], "modified")]);
    const out = foldUnchanged(html, map);
    const doc = new DOMParser().parseFromString(out, "text/html");
    const detailsList = doc.querySelectorAll("details");
    // experiences.0 が 1 つの details に丸ごと入り、内側の project は別 details にならない
    expect(detailsList).toHaveLength(1);
    expect(doc.querySelector('details [data-unit="experiences.0"]')).not.toBeNull();
  });

  it("連続する変更なし項目は 1 つの details にまとめ、件数を表示する", () => {
    const html =
      '<div data-unit="qualifications.0">a</div>' +
      '<div data-unit="qualifications.1">b</div>' +
      '<div data-unit="qualifications.2">c</div>';
    const map = buildPathKindMap([change(["full_name"], "modified")]);
    const out = foldUnchanged(html, map);
    const doc = new DOMParser().parseFromString(out, "text/html");
    expect(doc.querySelectorAll("details")).toHaveLength(1);
    expect(doc.querySelector(".fold-summary")?.textContent).toContain("3");
  });

  it("変更が無ければ（map 空）何もしない", () => {
    const html = '<div data-unit="experiences.0">a</div>';
    expect(foldUnchanged(html, buildPathKindMap([]))).toBe(html);
  });

  it("校正指摘のある項目は（差分が無くても）畳まずに残す", () => {
    const html =
      '<div data-unit="experiences.0"><span data-fp="experiences.0.company">A</span></div>' +
      '<div data-unit="experiences.1"><span data-fp="experiences.1.company">B</span></div>';
    // 差分は experiences.0 のみ。experiences.1 は校正指摘があるので畳まれない。
    const map = buildPathKindMap([change(["experiences", 0, "company"], "modified")]);
    const proofread = new Set(["experiences.1.company"]);
    const out = foldUnchanged(html, map, proofread);
    const doc = new DOMParser().parseFromString(out, "text/html");
    // 校正指摘のある experiences.1 は details の外に残る
    expect(doc.querySelector('details [data-unit="experiences.1"]')).toBeNull();
    expect(doc.querySelector('[data-unit="experiences.1"]')).not.toBeNull();
  });
});

describe("annotateHtml（校正マーク）", () => {
  it("校正指摘のある data-fp に diff-proofread を付ける", () => {
    const html =
      '<div data-fp="career_summary">要約</div><div data-fp="self_pr">PR</div>';
    const out = annotateHtml(html, buildPathKindMap([]), new Set(["self_pr"]));
    const doc = new DOMParser().parseFromString(out, "text/html");
    expect(doc.querySelector('[data-fp="self_pr"]')?.className).toContain("diff-proofread");
    // 指摘の無い career_summary には付かない
    expect(doc.querySelector('[data-fp="career_summary"]')?.className).toBe("");
  });

  it("差分（黄）と校正（青）は同じノードに併記される", () => {
    const html = '<div data-fp="self_pr">PR</div>';
    const out = annotateHtml(
      html,
      buildPathKindMap([change(["self_pr"], "modified")]),
      new Set(["self_pr"]),
    );
    const cls = new DOMParser().parseFromString(out, "text/html").querySelector('[data-fp="self_pr"]')
      ?.className;
    expect(cls).toContain("diff-modified");
    expect(cls).toContain("diff-proofread");
  });
});

describe("injectRemovedPlaceholders", () => {
  it("削除項目の直前の兄弟の後ろにスタブを挿入する", () => {
    const html = '<div data-unit="experiences.0">A社</div>';
    const out = injectRemovedPlaceholders(html, [change(["experiences", 1], "removed", "B社")]);
    const doc = new DOMParser().parseFromString(out, "text/html");
    const stub = doc.querySelector(".diff-removed-stub");
    expect(stub).not.toBeNull();
    expect(stub?.textContent).toContain("B社");
    expect(stub?.textContent).toContain("削除");
    // experiences.0 の直後に入る
    const prev = doc.querySelector('[data-unit="experiences.0"]');
    expect(prev?.nextElementSibling).toBe(stub);
  });

  it("テーブル行（tr）の削除は tr スタブで挿入する", () => {
    const html =
      '<table><tbody><tr data-unit="qualifications.0"><td>応用情報</td><td>2021</td></tr></tbody></table>';
    const out = injectRemovedPlaceholders(html, [
      change(["qualifications", 1], "removed", "AWS SAA"),
    ]);
    const doc = new DOMParser().parseFromString(out, "text/html");
    const stub = doc.querySelector("tr.diff-removed-stub");
    expect(stub).not.toBeNull();
    expect(stub?.querySelector("td")?.textContent).toContain("AWS SAA");
  });

  it("先頭削除(index=0)は後続の兄弟の直前にスタブを挿入する", () => {
    // index 0 が削除され、編集中 HTML には後続だった項目が残っている
    const html = '<div data-unit="experiences.0">B社</div>';
    const out = injectRemovedPlaceholders(html, [change(["experiences", 0], "removed", "A社")]);
    const doc = new DOMParser().parseFromString(out, "text/html");
    const stub = doc.querySelector(".diff-removed-stub");
    expect(stub).not.toBeNull();
    expect(stub?.textContent).toContain("A社");
    // 後続兄弟の直前（= 先頭）に入る
    const next = doc.querySelector('[data-unit="experiences.0"]');
    expect(next?.previousElementSibling).toBe(stub);
  });

  it("削除が無ければ何もしない", () => {
    const html = '<div data-unit="experiences.0">A</div>';
    expect(injectRemovedPlaceholders(html, [change(["full_name"], "modified")])).toBe(html);
  });

  it("アンカーが取れない（data-unit 不在）場合はスキップする", () => {
    const html = "<div>no units here</div>";
    const out = injectRemovedPlaceholders(html, [change(["experiences", 0], "removed", "X")]);
    expect(out).not.toContain("diff-removed-stub");
  });
});
