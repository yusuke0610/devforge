/**
 * スキル表示名の human-in-the-loop（ADR-0016 D11）用の純粋関数群。
 *
 * 表示名の解決順・グループ畳み込み・提案 → 確定ペイロード変換など、UI から切り離した
 * 決定論ロジックを集約する（テスト・ミューテーション対象 / .claude/rules/web/test.md）。
 */
import type {
  GitHubSkillItem,
  SkillDisplayDecisionInput,
  SkillIdentityRef,
} from "../api/types";

/**
 * スキルの実効表示名を返す。
 * 解決順は「人間の確定表示名 > 機械（Linguist）由来の表示補正 > canonical 名」（D11）。
 */
export function effectiveSkillName(skill: GitHubSkillItem): string {
  return skill.confirmed_display_name || skill.display_name || skill.canonical_name;
}

/** 表示用にグループ化したスキル（同一 group_id は 1 グループへ畳む）。 */
export interface DisplaySkillGroup {
  /** React key・グループ識別に使う安定キー */
  key: string;
  /** グループの表示ラベル（先頭スキルの実効表示名） */
  label: string;
  /** グループに属するスキル（単独確定・未確定は 1 件） */
  skills: GitHubSkillItem[];
}

/**
 * スキル一覧を表示用にグループ化する。
 * 確定済みで同一 ``group_id`` を持つスキルは 1 グループへ畳む。``group_id`` が無いスキルは
 * それぞれ単独グループになる（畳み込みは後段ビュー変換 / D8「保持は細かく」）。
 */
export function groupSkillsForDisplay(skills: GitHubSkillItem[]): DisplaySkillGroup[] {
  const groups: DisplaySkillGroup[] = [];
  const byGroupId = new Map<string, DisplaySkillGroup>();
  for (const skill of skills) {
    const label = effectiveSkillName(skill);
    if (skill.group_id) {
      const existing = byGroupId.get(skill.group_id);
      if (existing) {
        existing.skills.push(skill);
        continue;
      }
      const group: DisplaySkillGroup = { key: skill.group_id, label, skills: [skill] };
      byGroupId.set(skill.group_id, group);
      groups.push(group);
    } else {
      groups.push({
        key: `${skill.kind}:${skill.ecosystem ?? ""}:${skill.canonical_name}`,
        label,
        skills: [skill],
      });
    }
  }
  return groups;
}

/**
 * グループが確定済み（Layer 3 の確定行を持つ）で「解除」可能かを返す（#496）。
 * 確定表示名を持つメンバーがあれば true（畳み込みグループ・1:1 リネームの両方）。
 * 機械デフォルト（未確定）のみのグループは解除対象が無いので false。
 */
export function isResettableGroup(group: DisplaySkillGroup): boolean {
  return group.skills.some((s) => Boolean(s.confirmed_display_name));
}

/**
 * 解除（リセット）対象グループから、削除する identity 群を作る（#496）。
 * グループの全メンバーを返すため、N:1 の畳み込みはまとめてバラせる（機械デフォルトへ戻る）。
 * ``ecosystem`` は null（language）を空文字へ正規化して backend の identity と揃える。
 */
export function buildResetIdentities(group: DisplaySkillGroup): SkillIdentityRef[] {
  return group.skills.map((s) => ({
    kind: s.kind,
    ecosystem: s.ecosystem ?? "",
    canonical_name: s.canonical_name,
  }));
}

/** ユーザーがレビュー・編集した提案グループ（確定前の編集状態）。 */
export interface EditableProposalGroup {
  /** 現在の（編集後の）表示名 */
  displayName: string;
  /** agent が最初に提案した表示名（source 判定に使う） */
  originalDisplayName: string;
  /** このグループに畳むスキルの identity */
  members: SkillIdentityRef[];
}

/**
 * レビュー済みの提案グループを確定 API のペイロードへ変換する（D11）。
 *
 * - 表示名が空のグループは確定対象から除外する（切り詰めない / ADR-0010 踏襲）。
 * - メンバーが 2 件以上のグループには共通の ``group_id`` を割り当てて畳み込みを表す。
 *   単独グループ（1:1 リネーム）は ``group_id`` を null にする。
 * - ユーザーが表示名を編集していれば ``source="human"``、提案どおりなら ``source="agent"``。
 */
export function buildDisplayDecisions(
  groups: EditableProposalGroup[],
): SkillDisplayDecisionInput[] {
  const decisions: SkillDisplayDecisionInput[] = [];
  for (const group of groups) {
    const displayName = group.displayName.trim();
    if (!displayName || group.members.length === 0) {
      continue;
    }
    const groupId = group.members.length > 1 ? crypto.randomUUID() : null;
    const source = displayName === group.originalDisplayName.trim() ? "agent" : "human";
    for (const member of group.members) {
      decisions.push({
        kind: member.kind,
        ecosystem: member.ecosystem ?? "",
        canonical_name: member.canonical_name,
        display_name: displayName,
        group_id: groupId,
        source,
      });
    }
  }
  return decisions;
}
