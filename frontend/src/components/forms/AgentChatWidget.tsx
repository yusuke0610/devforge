/**
 * Agent チャットウィジェット（ADR-0010）。
 *
 * 職務経歴書フォーム右下のフローティングボタンからチャットパネルを開き、
 * スコープ（職務要約 / 自己PR / プロジェクト）を選んで AI に改善を依頼する。
 * AI 応答の operations は「フォームに反映」でフォーム state にのみ適用され、
 * 保存は既存の保存ボタン（保存 API）をユーザーが明示的に実行する。
 */

import { useMemo, useState } from "react";

import type { ProjectTarget } from "../../api/types";
import { AGENT_MESSAGES } from "../../constants/messages";
import { useAgentChat, type AgentChatEntry } from "../../hooks/career/useAgentChat";
import type { CareerFormState } from "../../payloadBuilders";
import { useMessageToast, useToast } from "../ui/toast";
import { applyAgentOperations, type AgentScope } from "../../utils/agentOperations";
import styles from "./AgentChatWidget.module.css";

type Props = {
  form: CareerFormState;
  /** operations 適用用の setForm（CareerResumeForm の setFormAndClearFocus） */
  onApply: (updater: (prev: CareerFormState) => CareerFormState) => void;
  /** 未ログイン時はチャットを開かずログイン導線へ流す */
  isAuthenticated: boolean;
  requestLogin: () => void;
};

/** project スコープで選択できる候補（フォーム state の index で特定する）。 */
type ProjectOption = { label: string; target: ProjectTarget };

function buildProjectOptions(form: CareerFormState): ProjectOption[] {
  const options: ProjectOption[] = [];
  form.experiences.forEach((exp, ei) => {
    exp.clients.forEach((client, ci) => {
      client.projects.forEach((proj, pi) => {
        const name = proj.name || AGENT_MESSAGES.TARGET_UNNAMED;
        const company = exp.company || AGENT_MESSAGES.TARGET_UNNAMED;
        options.push({
          label: `${company} / ${name}`,
          target: { experience_index: ei, client_index: ci, project_index: pi },
        });
      });
    });
  });
  return options;
}

export function AgentChatWidget({ form, onApply, isAuthenticated, requestLogin }: Props) {
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<AgentScope>("career_summary");
  const [targetIndex, setTargetIndex] = useState(0);
  const [prompt, setPrompt] = useState("");
  const { entries, sending, error, send, markApplied, clearError } = useAgentChat();
  const { showSuccess } = useToast();
  useMessageToast(error, "error");

  const projectOptions = useMemo(() => buildProjectOptions(form), [form]);
  const selectedTarget = projectOptions[targetIndex]?.target ?? null;
  const canSend =
    !sending && prompt.trim().length > 0 && (scope !== "project" || selectedTarget !== null);

  const handleOpen = () => {
    if (!isAuthenticated) {
      requestLogin();
      return;
    }
    setOpen(true);
  };

  const handleSend = () => {
    if (!canSend) return;
    clearError();
    void send(form, scope, scope === "project" ? selectedTarget : null, prompt.trim());
    setPrompt("");
  };

  const handleApply = (entry: AgentChatEntry, index: number) => {
    if (!entry.operations) return;
    const { scope: entryScope, target, operations } = entry;
    onApply((prev) => applyAgentOperations(prev, entryScope, target, operations));
    markApplied(index);
    showSuccess(AGENT_MESSAGES.APPLIED_TOAST);
  };

  if (!open) {
    return (
      <button
        type="button"
        className={styles.fab}
        onClick={handleOpen}
        aria-label={AGENT_MESSAGES.OPEN_LABEL}
      >
        ✨ {AGENT_MESSAGES.OPEN_LABEL}
      </button>
    );
  }

  return (
    <section className={styles.panel} aria-label={AGENT_MESSAGES.TITLE}>
      <header className={styles.header}>
        <span className={styles.title}>✨ {AGENT_MESSAGES.TITLE}</span>
        <button
          type="button"
          className={styles.closeButton}
          onClick={() => setOpen(false)}
          aria-label={AGENT_MESSAGES.CLOSE_LABEL}
        >
          ×
        </button>
      </header>

      <div className={styles.scopeRow}>
        <label className={styles.scopeLabel}>
          {AGENT_MESSAGES.SCOPE_LABEL}
          <select
            className={styles.select}
            value={scope}
            onChange={(e) => setScope(e.target.value as AgentScope)}
            disabled={sending}
          >
            <option value="career_summary">{AGENT_MESSAGES.SCOPE_CAREER_SUMMARY}</option>
            <option value="self_pr">{AGENT_MESSAGES.SCOPE_SELF_PR}</option>
            <option value="project">{AGENT_MESSAGES.SCOPE_PROJECT}</option>
          </select>
        </label>
        {scope === "project" &&
          (projectOptions.length === 0 ? (
            <p className={styles.targetEmpty}>{AGENT_MESSAGES.TARGET_EMPTY}</p>
          ) : (
            <label className={styles.scopeLabel}>
              {AGENT_MESSAGES.TARGET_LABEL}
              <select
                className={styles.select}
                value={targetIndex}
                onChange={(e) => setTargetIndex(Number(e.target.value))}
                disabled={sending}
              >
                {projectOptions.map((option, i) => (
                  <option key={option.label + i} value={i}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
      </div>

      <div className={styles.messages}>
        {entries.length === 0 && <p className={styles.emptyState}>{AGENT_MESSAGES.EMPTY_STATE}</p>}
        {entries.map((entry, i) => (
          <div
            key={i}
            className={entry.role === "user" ? styles.userMessage : styles.assistantMessage}
          >
            <p className={styles.messageText}>{entry.text}</p>
            {entry.operations && (
              <div className={styles.operations}>
                {entry.operations.map((op, j) => (
                  <pre key={j} className={styles.operationPreview}>
                    {op.value}
                  </pre>
                ))}
                <button
                  type="button"
                  className={styles.applyButton}
                  onClick={() => handleApply(entry, i)}
                >
                  {AGENT_MESSAGES.APPLY}
                </button>
              </div>
            )}
          </div>
        ))}
        {sending && <p className={styles.sendingNote}>{AGENT_MESSAGES.SENDING}</p>}
      </div>

      <div className={styles.inputRow}>
        <textarea
          className={styles.promptInput}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={AGENT_MESSAGES.PROMPT_PLACEHOLDER}
          rows={2}
          maxLength={2000}
          disabled={sending}
        />
        <button
          type="button"
          className={styles.sendButton}
          onClick={handleSend}
          disabled={!canSend}
        >
          {AGENT_MESSAGES.SEND}
        </button>
      </div>
    </section>
  );
}
