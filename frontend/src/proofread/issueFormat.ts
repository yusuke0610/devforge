/**
 * 校正結果（textlint メッセージ）を `ProofreadIssue` へ整形する純粋関数群。
 *
 * worker 本体（`proofread.worker.ts`）から呼ばれるが、textlint/kuromoji に依存しないため
 * 単体テスト可能。worker 経路をモックしても、ここはそのままテストできる。
 */
import type { ProofreadIssue, ProofreadSeverity } from "./types";

/** 抜粋に含める指摘箇所前後の文字数。 */
const EXCERPT_RADIUS = 12;

/** textlint の severity 数値（0=info / 1=warning / 2=error）を文字列へ写像する。 */
export function mapSeverity(severity: number): ProofreadSeverity {
  if (severity >= 2) return "error";
  if (severity === 1) return "warning";
  return "info";
}

/**
 * フィールド本文から指摘箇所の前後を抜き出す。
 * - index 周辺を `EXCERPT_RADIUS` 文字ずつ切り出し、端が途切れる場合は省略記号を付ける。
 * - 改行は空白に潰して 1 行で見せる。
 */
export function buildExcerpt(text: string, index: number, length = 1): string {
  if (!text) return "";
  const safeIndex = Math.max(0, Math.min(index, text.length));
  const start = Math.max(0, safeIndex - EXCERPT_RADIUS);
  const end = Math.min(text.length, safeIndex + Math.max(1, length) + EXCERPT_RADIUS);
  const slice = text.slice(start, end).replace(/\s+/g, " ").trim();
  const prefix = start > 0 ? "…" : "";
  const suffix = end < text.length ? "…" : "";
  return `${prefix}${slice}${suffix}`;
}

/** フィールド単位にグルーピングした指摘。サイドバー表示で使う。 */
export type ProofreadGroup = {
  fieldId: string;
  fieldLabel: string;
  issues: ProofreadIssue[];
};

/**
 * 指摘をフィールド単位へグルーピングする。
 * 入力順（= 収集順 = フォームの並び）を保ったままグループ化し、各グループ内も入力順を保つ。
 */
export function groupIssuesByField(issues: ProofreadIssue[]): ProofreadGroup[] {
  const groups: ProofreadGroup[] = [];
  const indexById = new Map<string, number>();
  for (const issue of issues) {
    let pos = indexById.get(issue.fieldId);
    if (pos === undefined) {
      pos = groups.length;
      indexById.set(issue.fieldId, pos);
      groups.push({ fieldId: issue.fieldId, fieldLabel: issue.fieldLabel, issues: [] });
    }
    groups[pos].issues.push(issue);
  }
  return groups;
}
