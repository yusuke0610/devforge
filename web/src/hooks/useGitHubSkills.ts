import { useCallback, useEffect, useState } from "react";

import {
  confirmSkillDisplayDecisions,
  getGitHubSkills,
  proposeSkillDisplayNames,
} from "../api/githubLink";
import { toAppError, type AppErrorState } from "../api";
import type { AgentModelAlias, GitHubSkillItem } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";
import {
  buildDisplayDecisions,
  groupSkillsForDisplay,
  type DisplaySkillGroup,
  type EditableProposalGroup,
} from "../utils/skillDisplay";

/**
 * GitHub 連携スキルの一覧取得と、表示名の human-in-the-loop 確定フローを管理するフック
 * （ADR-0016 D11）。
 *
 * - 一覧: マウント時に取得（loading / error）。
 * - 提案: agent に表示名・畳み込みを提案させ、編集可能な状態（proposal）で保持する。
 * - 確定: 編集済みの提案を確定 API へ送り、返ってきた最新一覧で置き換える。
 *
 * 決定論的な変換（表示名解決・グループ化・提案→確定ペイロード）は utils/skillDisplay に
 * 切り出し、本フックは API 呼び出しと状態管理（loading / success / error）に専念する。
 *
 * @param model 提案に使う LLM モデル（ユーザーメニューのグローバル設定を渡す）
 */
export function useGitHubSkills(model: AgentModelAlias) {
  const [skills, setSkills] = useState<GitHubSkillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppErrorState | null>(null);
  const [proposal, setProposal] = useState<EditableProposalGroup[] | null>(null);
  const [proposing, setProposing] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    // 前回の失敗が残らないよう、再取得の成功でエラー表示が消えるようにする（propose/confirm と同様）
    setError(null);
    try {
      const res = await getGitHubSkills();
      setSkills(res.skills ?? []);
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.SKILL_FETCH));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  /** agent に表示名・畳み込みを提案させ、編集可能な状態で保持する。 */
  const propose = useCallback(async () => {
    setError(null);
    setProposing(true);
    try {
      const res = await proposeSkillDisplayNames({ model });
      setProposal(
        (res.groups ?? []).map((group) => ({
          displayName: group.display_name,
          originalDisplayName: group.display_name,
          members: group.members ?? [],
        })),
      );
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.SKILL_DISPLAY_PROPOSE));
    } finally {
      setProposing(false);
    }
  }, [model]);

  /** レビュー中の 1 グループの表示名を編集する。 */
  const updateProposalName = useCallback((index: number, displayName: string) => {
    setProposal((prev) =>
      prev ? prev.map((g, i) => (i === index ? { ...g, displayName } : g)) : prev,
    );
  }, []);

  /** 提案を破棄する（確定しない）。 */
  const discardProposal = useCallback(() => setProposal(null), []);

  /** 編集済みの提案を確定・永続化し、返ってきた最新一覧で置き換える。 */
  const confirm = useCallback(async () => {
    if (!proposal) return;
    setError(null);
    setConfirming(true);
    try {
      const decisions = buildDisplayDecisions(proposal);
      const res = await confirmSkillDisplayDecisions({ decisions });
      setSkills(res.skills ?? []);
      setProposal(null);
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.SKILL_DISPLAY_CONFIRM));
    } finally {
      setConfirming(false);
    }
  }, [proposal]);

  const groups: DisplaySkillGroup[] = groupSkillsForDisplay(skills);

  return {
    skills,
    groups,
    loading,
    error,
    proposal,
    proposing,
    confirming,
    propose,
    updateProposalName,
    discardProposal,
    confirm,
    reload,
  };
}
