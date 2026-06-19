/**
 * 保存確認ダイアログ右サイドバーの「変更点リスト」を組み立てる純関数。
 *
 * 変更点（差分）を**フィールド単位でまとめ**、PDF レイアウトと同じ縦順
 * （氏名 → 職務要約 → 職務経歴 → 資格 → 自己PR、各コンテナ内も PDF 準拠）に並べる。
 * これにより左右ペイン（PDF）とサイドバーの並びが一致し、上から順に突合できる。
 */
import type { CareerChange } from "./careerDiff";

/** 1 フィールド分のレビュー項目（フィールドの差分をまとめて持つ）。 */
export type ReviewEntry = {
  /** フィールドのドット区切りパス（スクロール・key 用）。 */
  path: string;
  /** 人間可読ラベル（パンくず）。 */
  label: string;
  /** このフィールドの差分（通常 0〜1 件）。 */
  changes: CareerChange[];
};

/** トップレベル項目の並び（PDF レイアウト順）。 */
const TOP_ORDER = ["full_name", "career_summary", "experiences", "qualifications", "self_pr"];

/** 配列コンテナごとのフィールド並び（careerDiff の走査順＝PDF 準拠）。 */
const CONTAINER_FIELD_ORDER: Record<string, string[]> = {
  experiences: [
    "company",
    "business_description",
    "start_date",
    "end_date",
    "is_current",
    "employee_count",
    "capital",
    "capital_unit",
    "is_it_company",
    "description",
    "clients",
  ],
  clients: [
    "name",
    "has_client",
    "is_vacation",
    "vacation_start_date",
    "vacation_end_date",
    "vacation_is_current",
    "vacation_description",
    "projects",
  ],
  projects: ["name", "role", "description", "team", "periods", "technology_stacks", "phases"],
  qualifications: ["name", "acquired_date"],
};

/** 未知のセグメントを既知フィールドより後ろへ寄せる基準値（文字コードで安定ソート）。 */
const UNKNOWN_FIELD_RANK_BASE = 400;
/** コンテナの並びが特定できない名前付きセグメントのランク（末尾側へ）。 */
const UNKNOWN_CONTAINER_FIELD_RANK = 500;

/** 既知の並びにあればその index、無ければ末尾側（文字コードで安定ソート）に寄せる。 */
function orderIndex(list: string[], seg: string): number {
  const i = list.indexOf(seg);
  return i >= 0 ? i : UNKNOWN_FIELD_RANK_BASE + (seg.charCodeAt(0) || 0);
}

/**
 * パスを「並び順を表す数値タプル」に変換する。
 * - 先頭セグメント: トップレベル順
 * - 数値セグメント: 配列 index
 * - 名前付きセグメント: 直近の配列名（2 つ前）から決まるコンテナのフィールド順
 */
function rankTuple(path: string): number[] {
  const segs = path.split(".");
  return segs.map((seg, i) => {
    if (i === 0) return orderIndex(TOP_ORDER, seg);
    if (/^\d+$/.test(seg)) return Number(seg);
    const containerName = i >= 2 && /^\d+$/.test(segs[i - 1]) ? segs[i - 2] : null;
    const order = containerName ? CONTAINER_FIELD_ORDER[containerName] : null;
    return order ? orderIndex(order, seg) : UNKNOWN_CONTAINER_FIELD_RANK;
  });
}

/** 2 つのパスを PDF レイアウト順で比較する（親は子より前）。 */
export function comparePaths(a: string, b: string): number {
  const ra = rankTuple(a);
  const rb = rankTuple(b);
  const len = Math.min(ra.length, rb.length);
  for (let i = 0; i < len; i++) {
    if (ra[i] !== rb[i]) return ra[i] - rb[i];
  }
  return ra.length - rb.length;
}

/**
 * 差分をフィールド単位にまとめ、PDF レイアウト順に並べたレビュー項目を返す。
 * 同一パスの差分は 1 エントリにまとまる。
 */
export function buildReviewEntries(changes: CareerChange[]): ReviewEntry[] {
  const byPath = new Map<string, ReviewEntry>();

  const getOrCreate = (path: string, label: string): ReviewEntry => {
    let entry = byPath.get(path);
    if (!entry) {
      entry = { path, label, changes: [] };
      byPath.set(path, entry);
    }
    return entry;
  };

  for (const change of changes) {
    getOrCreate(change.path.join("."), change.label).changes.push(change);
  }

  return [...byPath.values()].sort((a, b) => comparePaths(a.path, b.path));
}
