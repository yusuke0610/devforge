/**
 * Agent チャット（ADR-0010）のフォーム連携ユーティリティ。
 *
 * - `buildAgentResumeContext`: 編集中の `CareerFormState` を backend の
 *   `AgentResumeContext`（緩いコンテキスト型）へ変換する
 * - `applyAgentOperations`: レスポンスの operations をフォーム state に適用する
 *   （state のみ。保存は既存の保存 API をユーザーが明示的に実行する）
 */

import type { AgentOperation, AgentResumeContext, ProjectTarget } from "../api/types";
import type { CareerFormState } from "../payloadBuilders";

export type AgentScope = "project" | "career_summary" | "self_pr";

/** 編集中フォームを Agent のリクエストコンテキストへ変換する。 */
export function buildAgentResumeContext(form: CareerFormState): AgentResumeContext {
  return {
    career_summary: form.career_summary,
    self_pr: form.self_pr,
    experiences: form.experiences.map((exp) => ({
      company: exp.company,
      business_description: exp.business_description,
      clients: exp.clients.map((client) => ({
        name: client.name,
        projects: client.projects.map((project) => ({
          name: project.name,
          role: project.role,
          description: project.description,
          technology_stacks: project.technology_stacks,
          phases: project.phases,
        })),
      })),
    })),
  };
}

/**
 * operations をフォーム state に適用した新しい state を返す。
 *
 * project スコープの description / role は target が指す project にのみ反映する。
 * target が範囲外の場合は何も変更しない（backend 検証済みのため通常発生しない）。
 */
export function applyAgentOperations(
  form: CareerFormState,
  scope: AgentScope,
  target: ProjectTarget | null,
  operations: AgentOperation[],
): CareerFormState {
  let next = form;
  for (const op of operations) {
    if (scope === "career_summary" && op.field === "career_summary") {
      next = { ...next, career_summary: op.value };
    } else if (scope === "self_pr" && op.field === "self_pr") {
      next = { ...next, self_pr: op.value };
    } else if (scope === "project" && target && (op.field === "description" || op.field === "role")) {
      next = applyProjectField(next, target, op.field, op.value);
    }
  }
  return next;
}

function applyProjectField(
  form: CareerFormState,
  target: ProjectTarget,
  field: "description" | "role",
  value: string,
): CareerFormState {
  const project =
    form.experiences[target.experience_index]?.clients[target.client_index]?.projects[
      target.project_index
    ];
  if (!project) return form;
  return {
    ...form,
    experiences: form.experiences.map((exp, ei) =>
      ei !== target.experience_index
        ? exp
        : {
            ...exp,
            clients: exp.clients.map((client, ci) =>
              ci !== target.client_index
                ? client
                : {
                    ...client,
                    projects: client.projects.map((proj, pi) =>
                      pi !== target.project_index ? proj : { ...proj, [field]: value },
                    ),
                  },
            ),
          },
    ),
  };
}
