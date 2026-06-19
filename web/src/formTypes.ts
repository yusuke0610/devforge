export type CareerTextFieldKey =
  | "full_name"
  | "email"
  | "github_url"
  | "career_summary"
  | "self_pr";
export type CareerExperienceFieldKey =
  | "company"
  | "business_description"
  | "start_date"
  | "end_date"
  | "is_current"
  | "employee_count"
  | "capital"
  | "capital_unit"
  | "is_it_company"
  | "description";
export type CareerClientFieldKey =
  | "name"
  | "vacation_start_date"
  | "vacation_end_date"
  | "vacation_description";
export type CareerProjectFieldKey = "name" | "role" | "description";
export type CareerProjectPeriodFieldKey = "start_date" | "end_date" | "is_current";

/**
 * 取引先（client）配下のミューテーションハンドラ群。
 * CareerExperienceEditor が ClientEditor へ素通しするため、両 Props 型で共有する
 * （片方だけ引数を足したときの取り違えを型で防ぐ）。
 */
export type ClientMutationHandlers = {
  /** 取引先フィールド変更ハンドラ */
  onUpdateClientField: (
    expIndex: number,
    clientIndex: number,
    key: CareerClientFieldKey,
    value: string,
  ) => void;
  /** 取引先「取引先なし」切替ハンドラ */
  onUpdateClientHasClient: (expIndex: number, clientIndex: number, value: boolean) => void;
  /** 取引先「休暇」切替ハンドラ */
  onUpdateClientIsVacation: (expIndex: number, clientIndex: number, value: boolean) => void;
  /** 休暇「継続中」切替ハンドラ */
  onUpdateClientVacationIsCurrent: (expIndex: number, clientIndex: number, value: boolean) => void;
  /** プロジェクト削除ハンドラ */
  onRemoveProject: (expIndex: number, clientIndex: number, projIndex: number) => void;
  /** プロジェクト編集モーダルを開くハンドラ */
  onOpenProjectModal: (expIndex: number, clientIndex: number, projIndex: number | null) => void;
  /** 取引先削除ハンドラ */
  onRemoveClient: (expIndex: number, clientIndex: number) => void;
};
