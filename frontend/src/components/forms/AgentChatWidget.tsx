/**
 * Agent チャットウィジェット（ADR-0010）。
 *
 * 職務経歴書フォーム右下のフローティングボタンからチャットパネルを開き、
 * スコープ（職務要約 / 自己PR / 職務経歴 / プロジェクト）を選んで AI に改善を依頼する。
 * AI 応答の operations は「フォームに反映」でフォーム state にのみ適用され、
 * 保存は既存の保存ボタン（保存 API）をユーザーが明示的に実行する。
 */

import { useCallback, useMemo, useState } from "react";

import type { ExperienceTarget, ProjectTarget } from "../../api/types";
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

/** experience スコープで選択できる候補（フォーム state の index で特定する）。 */
type ExperienceOption = { label: string; target: ExperienceTarget };

/** パネルのリサイズ範囲。右下固定のため左上方向にだけ広がる */
const PANEL_MIN_WIDTH = 320;
const PANEL_MIN_HEIGHT = 360;
const PANEL_VIEWPORT_MARGIN = 48;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** LLM が提示した「次の依頼文」候補のボタン列。押下でそのまま prompt として再送する。 */
function SuggestionButtons({
  items,
  disabled,
  onSelect,
}: {
  items: string[];
  disabled: boolean;
  onSelect: (suggestion: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className={styles.actionRow}>
      {items.map((item, index) => (
        <button
          key={index}
          type="button"
          className={styles.actionButton}
          disabled={disabled}
          onClick={() => onSelect(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}

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

function buildExperienceOptions(form: CareerFormState): ExperienceOption[] {
  return form.experiences.map((exp, ei) => ({
    label: exp.company || AGENT_MESSAGES.TARGET_UNNAMED,
    target: { experience_index: ei },
  }));
}

export function AgentChatWidget({ form, onApply, isAuthenticated, requestLogin }: Props) {
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<AgentScope>("career_summary");
  const [projectTargetIndex, setProjectTargetIndex] = useState(0);
  const [experienceTargetIndex, setExperienceTargetIndex] = useState(0);
  const [prompt, setPrompt] = useState("");
  /** ドラッグでリサイズされた寸法。null の間は CSS のデフォルトサイズに従う */
  const [panelSize, setPanelSize] = useState<{ width: number; height: number } | null>(null);
  const { entries, sending, error, send, markApplied, clearError } = useAgentChat();
  const { showSuccess } = useToast();
  useMessageToast(error, "error");

  const projectOptions = useMemo(() => buildProjectOptions(form), [form]);
  const experienceOptions = useMemo(() => buildExperienceOptions(form), [form]);

  const selectedProjectTarget = projectOptions[projectTargetIndex]?.target ?? null;
  const selectedExperienceTarget = experienceOptions[experienceTargetIndex]?.target ?? null;

  /** 送信時に渡す target（スコープに応じて選択） */
  function getTarget(): ProjectTarget | ExperienceTarget | null {
    if (scope === "project") return selectedProjectTarget;
    if (scope === "experience") return selectedExperienceTarget;
    return null;
  }

  const canSend =
    !sending &&
    prompt.trim().length > 0 &&
    (scope !== "project" || selectedProjectTarget !== null) &&
    (scope !== "experience" || selectedExperienceTarget !== null);

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
    void send(form, scope, getTarget(), prompt.trim());
    setPrompt("");
  };

  /** suggestions ボタンの送信可否（自由入力と違い入力テキストは不要） */
  const canSendSuggestion =
    !sending &&
    (scope !== "project" || selectedProjectTarget !== null) &&
    (scope !== "experience" || selectedExperienceTarget !== null);

  const handleSuggestion = (suggestion: string) => {
    if (!canSendSuggestion) return;
    clearError();
    void send(form, scope, getTarget(), suggestion);
  };

  // パネル左上のハンドルをドラッグしてリサイズする。パネルは右下固定なので
  // ポインタが左上に動くほど大きくなる（差分を加算）
  const handleResizeStart = useCallback((e: React.PointerEvent<HTMLButtonElement>) => {
    e.preventDefault();
    const panel = (e.currentTarget as HTMLElement).closest("section");
    if (!panel) return;
    const startX = e.clientX;
    const startY = e.clientY;
    const startRect = panel.getBoundingClientRect();
    const maxWidth = window.innerWidth - PANEL_VIEWPORT_MARGIN;
    const maxHeight = window.innerHeight - PANEL_VIEWPORT_MARGIN * 2;

    const onMove = (ev: PointerEvent) => {
      setPanelSize({
        width: clamp(startRect.width + (startX - ev.clientX), PANEL_MIN_WIDTH, maxWidth),
        height: clamp(startRect.height + (startY - ev.clientY), PANEL_MIN_HEIGHT, maxHeight),
      });
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }, []);

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
        {AGENT_MESSAGES.OPEN_LABEL}
      </button>
    );
  }

  return (
    <section
      className={styles.panel}
      aria-label={AGENT_MESSAGES.TITLE}
      style={panelSize ? { width: panelSize.width, height: panelSize.height } : undefined}
    >
      <button
        type="button"
        className={styles.resizeHandle}
        onPointerDown={handleResizeStart}
        aria-label={AGENT_MESSAGES.RESIZE_LABEL}
        title={AGENT_MESSAGES.RESIZE_LABEL}
      />
      <header className={styles.header}>
        <span className={styles.title}>{AGENT_MESSAGES.TITLE}</span>
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
            <option value="experience">{AGENT_MESSAGES.SCOPE_EXPERIENCE}</option>
            <option value="project">{AGENT_MESSAGES.SCOPE_PROJECT}</option>
          </select>
        </label>
        {scope === "experience" &&
          (experienceOptions.length === 0 ? (
            <p className={styles.targetEmpty}>{AGENT_MESSAGES.TARGET_EXPERIENCE_EMPTY}</p>
          ) : (
            <label className={styles.scopeLabel}>
              {AGENT_MESSAGES.TARGET_EXPERIENCE_LABEL}
              <select
                className={styles.select}
                value={experienceTargetIndex}
                onChange={(e) => setExperienceTargetIndex(Number(e.target.value))}
                disabled={sending}
              >
                {experienceOptions.map((option, i) => (
                  <option key={option.label + i} value={i}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
        {scope === "project" &&
          (projectOptions.length === 0 ? (
            <p className={styles.targetEmpty}>{AGENT_MESSAGES.TARGET_EMPTY}</p>
          ) : (
            <label className={styles.scopeLabel}>
              {AGENT_MESSAGES.TARGET_LABEL}
              <select
                className={styles.select}
                value={projectTargetIndex}
                onChange={(e) => setProjectTargetIndex(Number(e.target.value))}
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
            {entry.suggestions && (
              <SuggestionButtons
                items={entry.suggestions}
                disabled={!canSendSuggestion}
                onSelect={handleSuggestion}
              />
            )}
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
          onKeyDown={(e) => {
            // Enter で送信、Cmd/Ctrl+Enter で改行（IME 変換確定の Enter は除外）
            if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
            if (e.metaKey || e.ctrlKey) {
              e.preventDefault();
              const target = e.currentTarget;
              const { selectionStart, selectionEnd, value } = target;
              const next = `${value.slice(0, selectionStart)}\n${value.slice(selectionEnd)}`;
              setPrompt(next);
              requestAnimationFrame(() => {
                target.selectionStart = target.selectionEnd = selectionStart + 1;
              });
              return;
            }
            e.preventDefault();
            if (canSend) {
              void handleSend();
            }
          }}
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
