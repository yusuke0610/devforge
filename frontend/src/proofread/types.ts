/**
 * 文章校正（誤字脱字・表記ゆれ）機能の型 Single Source of Truth。
 *
 * メインスレッド（hook / コンポーネント）は textlint や kuromoji を一切知らず、
 * この `ProofreadIssue` 配列だけを介して worker とやり取りする。エンジンを差し替えても
 * この型が変わらなければ UI 側は影響を受けない（疎結合の境界）。
 */

/** 指摘の深刻度。textlint の severity 数値（0=info / 1=warning / 2=error）を文字列へ写像したもの。 */
export type ProofreadSeverity = "info" | "warning" | "error";

/** 校正対象となる 1 テキスト項目（フォームから平坦化したもの）。 */
export type CareerTextItem = {
  /** フォーム上のドット区切りパス（例: "experiences.0.description"）。careerDiff の path と揃える。 */
  id: string;
  /** 人間可読ラベル（パンくず。例: "職歴1 ＞ 詳細"）。 */
  label: string;
  /** 校正にかける本文。 */
  value: string;
};

/** 1 件の校正指摘。フィールド単位にグルーピングして表示する。 */
export type ProofreadIssue = {
  /** 指摘が属するフィールドの id（`CareerTextItem.id`）。 */
  fieldId: string;
  /** 指摘が属するフィールドのラベル（`CareerTextItem.label`）。 */
  fieldLabel: string;
  /** textlint のルール ID（例: "prh" / "ja-no-mixed-period"）。 */
  ruleId: string;
  /** 指摘メッセージ（textlint 由来の外部正本。そのまま表示してよい）。 */
  message: string;
  severity: ProofreadSeverity;
  /** フィールド本文内の行・列（1 始まり）。 */
  line: number;
  column: number;
  /** フィールド本文内の文字オフセット（0 始まり）。 */
  index: number;
  /** 指摘箇所の前後を抜き出した短い抜粋（UI のコンテキスト表示用）。 */
  excerpt: string;
};

/** メインスレッド → worker への校正リクエスト。 */
export type ProofreadRequest = {
  type: "proofread";
  requestId: number;
  items: CareerTextItem[];
};

/** worker → メインスレッドへの応答。 */
export type ProofreadResponse =
  | { type: "result"; requestId: number; issues: ProofreadIssue[] }
  | { type: "error"; requestId: number; message: string };
