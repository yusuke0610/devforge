/**
 * 経歴書フォームの「保存済み（baseline）」と「編集中（form）」の差分を、
 * 変更点リスト（旧→新／追加・削除・修正＋項目別ロールバック）として算出する純関数群。
 *
 * 保存時の確認ダイアログ（`CareerSaveConfirmDialog`）が表示するモデルを生成する。
 *
 * ## 突合方針（index ベース）
 * `CareerFormState` の配列要素には安定 ID が無いため、`useCareerDirty` と同じく
 * **index による突合**で「追加 / 削除」を判定する。長さ差分の末尾を追加/削除とみなすため、
 * 配列途中の要素削除は「以降の要素がすべて修正＋末尾が削除」と近似表示される。
 * これは安定 ID が無い以上の制約であり、既存 dirty 判定と挙動を一致させている。
 * 突合戦略を差し替えたい場合は `diffArray` のマッチングだけ変更すればよい。
 *
 * 等価判定は `isDeepEqual`（`utils/deepEqual.ts`）に集約済みのものを再利用する。
 */
import { CAREER_DIFF_LABELS as L, DIFF_DIALOG_MESSAGES as D } from "../constants/messages";
import type {
  CareerClientForm,
  CareerExperienceForm,
  CareerFormState,
  CareerProjectForm,
  CareerProjectPeriodForm,
  TeamMemberForm,
} from "../payloadBuilders";
import type { ResumeQualificationItem, TechnologyStackItem } from "../api/types";
import { isDeepEqual } from "./deepEqual";
import { insertAtPath, removeAtPath, setAtPath } from "./setAtPath";

/** 変更の種別。 */
export type ChangeKind = "modified" | "added" | "removed";

/** 1 件の変更点。ダイアログ表示とロールバックの両方に必要な情報を持つ。 */
export type CareerChange = {
  /** form 上の対象パス（ロールバック適用・key 生成に使う）。 */
  path: (string | number)[];
  /** 人間可読ラベル（例: 「職歴1 ＞ 取引先2 ＞ 案件名」）。 */
  label: string;
  kind: ChangeKind;
  /** 表示用の旧値（modified / removed で意味を持つ）。 */
  oldValue: string;
  /** 表示用の新値（modified / added で意味を持つ）。 */
  newValue: string;
  /** この変更だけを baseline 値へ戻した form を返す純関数。 */
  rollback: (form: CareerFormState) => CareerFormState;
};

/** 表示用に値を文字列へ整形する。boolean は「あり / なし」、空値は代替テキスト。 */
function formatScalar(value: unknown): string {
  if (typeof value === "boolean") return value ? D.BOOL_TRUE : D.BOOL_FALSE;
  if (value === "" || value === null || value === undefined) return D.EMPTY_VALUE;
  return String(value);
}

/** ラベルセグメントを区切り文字で連結する。 */
function joinLabel(segments: string[]): string {
  return segments.join(D.PATH_SEPARATOR);
}

/**
 * スカラーフィールドの差分を 1 件 push する。等しければ何もしない。
 * rollback は当該パスを base 値へ書き戻す。
 */
function pushScalar(
  changes: CareerChange[],
  labelSegments: string[],
  fieldLabel: string,
  path: (string | number)[],
  current: unknown,
  base: unknown,
): void {
  if (isDeepEqual(current, base)) return;
  changes.push({
    path,
    label: joinLabel([...labelSegments, fieldLabel]),
    kind: "modified",
    oldValue: formatScalar(base),
    newValue: formatScalar(current),
    rollback: (form) => setAtPath(form, path, base),
  });
}

/**
 * 配列の差分を index 突合で算出する汎用ヘルパ。
 * - 片側にしか無い要素 → 追加 / 削除として 1 件 push（ロールバックは要素の除去 / 復元）
 * - 両側にある要素 → `diffItem` に委譲（中身のフィールド差分を再帰展開）
 */
function diffArray<T>(
  changes: CareerChange[],
  current: T[],
  base: T[],
  path: (string | number)[],
  labelSegments: string[],
  itemLabel: string,
  summarize: (item: T) => string,
  diffItem: (
    changes: CareerChange[],
    cur: T,
    bas: T,
    itemPath: (string | number)[],
    itemLabelSegments: string[],
  ) => void,
): void {
  const maxLen = Math.max(current.length, base.length);
  for (let i = 0; i < maxLen; i++) {
    const cur = current[i];
    const bas = base[i];
    const itemPath = [...path, i];
    const itemLabelSegments = [...labelSegments, `${itemLabel}${i + 1}`];

    if (cur !== undefined && bas === undefined) {
      changes.push({
        path: itemPath,
        label: joinLabel(itemLabelSegments),
        kind: "added",
        oldValue: "",
        newValue: summarize(cur) || D.EMPTY_VALUE,
        rollback: (form) => removeAtPath(form, itemPath),
      });
    } else if (cur === undefined && bas !== undefined) {
      changes.push({
        path: itemPath,
        label: joinLabel(itemLabelSegments),
        kind: "removed",
        oldValue: summarize(bas) || D.EMPTY_VALUE,
        newValue: "",
        rollback: (form) => insertAtPath(form, itemPath, bas),
      });
    } else if (cur !== undefined && bas !== undefined) {
      diffItem(changes, cur, bas, itemPath, itemLabelSegments);
    }
  }
}

function diffTeamMember(
  changes: CareerChange[],
  cur: TeamMemberForm,
  bas: TeamMemberForm,
  path: (string | number)[],
  seg: string[],
): void {
  pushScalar(changes, seg, L.MEMBER_ROLE, [...path, "role"], cur.role, bas.role);
  pushScalar(changes, seg, L.MEMBER_COUNT, [...path, "count"], cur.count, bas.count);
}

function diffPeriod(
  changes: CareerChange[],
  cur: CareerProjectPeriodForm,
  bas: CareerProjectPeriodForm,
  path: (string | number)[],
  seg: string[],
): void {
  pushScalar(changes, seg, L.START_DATE, [...path, "start_date"], cur.start_date, bas.start_date);
  pushScalar(changes, seg, L.END_DATE, [...path, "end_date"], cur.end_date, bas.end_date);
  pushScalar(changes, seg, L.IS_CURRENT, [...path, "is_current"], cur.is_current, bas.is_current);
}

function diffTechStack(
  changes: CareerChange[],
  cur: TechnologyStackItem,
  bas: TechnologyStackItem,
  path: (string | number)[],
  seg: string[],
): void {
  pushScalar(changes, seg, L.TECH_CATEGORY, [...path, "category"], cur.category, bas.category);
  pushScalar(changes, seg, L.TECH_NAME, [...path, "name"], cur.name, bas.name);
}

/** phases は string[]。セグメント名（「フェーズN」）自体がラベルになるので直接 push する。 */
function diffPhase(
  changes: CareerChange[],
  cur: string,
  bas: string,
  path: (string | number)[],
  seg: string[],
): void {
  if (isDeepEqual(cur, bas)) return;
  changes.push({
    path,
    label: joinLabel(seg),
    kind: "modified",
    oldValue: formatScalar(bas),
    newValue: formatScalar(cur),
    rollback: (form) => setAtPath(form, path, bas),
  });
}

function diffProject(
  changes: CareerChange[],
  cur: CareerProjectForm,
  bas: CareerProjectForm,
  path: (string | number)[],
  seg: string[],
): void {
  pushScalar(changes, seg, L.PROJECT_NAME, [...path, "name"], cur.name, bas.name);
  pushScalar(changes, seg, L.ROLE, [...path, "role"], cur.role, bas.role);
  pushScalar(changes, seg, L.PROJECT_DESCRIPTION, [...path, "description"], cur.description, bas.description);
  pushScalar(changes, seg, L.TEAM_TOTAL, [...path, "team", "total"], cur.team.total, bas.team.total);

  diffArray(
    changes, cur.team.members, bas.team.members, [...path, "team", "members"], seg,
    L.TEAM_MEMBER, (m) => m.role, diffTeamMember,
  );
  diffArray(
    changes, cur.periods, bas.periods, [...path, "periods"], seg,
    L.PERIOD, (p) => p.start_date, diffPeriod,
  );
  diffArray(
    changes, cur.technology_stacks, bas.technology_stacks, [...path, "technology_stacks"], seg,
    L.TECH_STACK, (t) => t.name, diffTechStack,
  );
  diffArray(
    changes, cur.phases, bas.phases, [...path, "phases"], seg,
    L.PHASE, (p) => p, diffPhase,
  );
}

function diffClient(
  changes: CareerChange[],
  cur: CareerClientForm,
  bas: CareerClientForm,
  path: (string | number)[],
  seg: string[],
): void {
  pushScalar(changes, seg, L.CLIENT_NAME, [...path, "name"], cur.name, bas.name);
  pushScalar(changes, seg, L.HAS_CLIENT, [...path, "has_client"], cur.has_client, bas.has_client);
  pushScalar(changes, seg, L.IS_VACATION, [...path, "is_vacation"], cur.is_vacation, bas.is_vacation);
  pushScalar(changes, seg, L.VACATION_START_DATE, [...path, "vacation_start_date"], cur.vacation_start_date, bas.vacation_start_date);
  pushScalar(changes, seg, L.VACATION_END_DATE, [...path, "vacation_end_date"], cur.vacation_end_date, bas.vacation_end_date);
  pushScalar(changes, seg, L.VACATION_IS_CURRENT, [...path, "vacation_is_current"], cur.vacation_is_current, bas.vacation_is_current);
  pushScalar(changes, seg, L.VACATION_DESCRIPTION, [...path, "vacation_description"], cur.vacation_description, bas.vacation_description);

  diffArray(
    changes, cur.projects, bas.projects, [...path, "projects"], seg,
    L.PROJECT, (p) => p.name, diffProject,
  );
}

function diffExperience(
  changes: CareerChange[],
  cur: CareerExperienceForm,
  bas: CareerExperienceForm,
  path: (string | number)[],
  seg: string[],
): void {
  pushScalar(changes, seg, L.COMPANY, [...path, "company"], cur.company, bas.company);
  pushScalar(changes, seg, L.BUSINESS_DESCRIPTION, [...path, "business_description"], cur.business_description, bas.business_description);
  pushScalar(changes, seg, L.START_DATE, [...path, "start_date"], cur.start_date, bas.start_date);
  pushScalar(changes, seg, L.END_DATE, [...path, "end_date"], cur.end_date, bas.end_date);
  pushScalar(changes, seg, L.IS_CURRENT, [...path, "is_current"], cur.is_current, bas.is_current);
  pushScalar(changes, seg, L.EMPLOYEE_COUNT, [...path, "employee_count"], cur.employee_count, bas.employee_count);
  pushScalar(changes, seg, L.CAPITAL, [...path, "capital"], cur.capital, bas.capital);
  pushScalar(changes, seg, L.CAPITAL_UNIT, [...path, "capital_unit"], cur.capital_unit, bas.capital_unit);
  pushScalar(changes, seg, L.IS_IT_COMPANY, [...path, "is_it_company"], cur.is_it_company, bas.is_it_company);
  pushScalar(changes, seg, L.DESCRIPTION, [...path, "description"], cur.description, bas.description);

  diffArray(
    changes, cur.clients, bas.clients, [...path, "clients"], seg,
    L.CLIENT, (c) => c.name, diffClient,
  );
}

function diffQualification(
  changes: CareerChange[],
  cur: ResumeQualificationItem,
  bas: ResumeQualificationItem,
  path: (string | number)[],
  seg: string[],
): void {
  pushScalar(changes, seg, L.QUALIFICATION_NAME, [...path, "name"], cur.name, bas.name);
  pushScalar(changes, seg, L.ACQUIRED_DATE, [...path, "acquired_date"], cur.acquired_date, bas.acquired_date);
}

/**
 * 編集中フォーム（form）と保存済みスナップショット（baseline）の差分を変更点リストにする。
 * 変更が無ければ空配列を返す。
 */
export function buildCareerChanges(
  form: CareerFormState,
  baseline: CareerFormState,
): CareerChange[] {
  const changes: CareerChange[] = [];

  // 並び順は PDF レイアウト（氏名 → 職務要約 → 職務経歴 → 資格 → 自己PR）に合わせる。
  // 左右ペインとサイドバー（変更点 / 校正）の縦順が一致し、突合しやすくなる。
  pushScalar(changes, [], L.FULL_NAME, ["full_name"], form.full_name, baseline.full_name);
  pushScalar(changes, [], L.CAREER_SUMMARY, ["career_summary"], form.career_summary, baseline.career_summary);

  diffArray(
    changes, form.experiences, baseline.experiences, ["experiences"], [],
    L.EXPERIENCE, (e) => e.company, diffExperience,
  );
  diffArray(
    changes, form.qualifications, baseline.qualifications, ["qualifications"], [],
    L.QUALIFICATION, (q) => q.name, diffQualification,
  );

  pushScalar(changes, [], L.SELF_PR, ["self_pr"], form.self_pr, baseline.self_pr);

  return changes;
}
