/**
 * 選択可能な AI モデルの表示メタデータ。
 *
 * エイリアスの正本は backend `services/agent/model_catalog.py`（実モデル ID）。
 * ここはフロントの表示用（製品名・説明）の SSoT で、プランカード UI と
 * サイドバーの使用モデル表示が参照する。ADR-0023 で課金を撤去したため、
 * 課金レート・有料/無料の区別は持たない（マルチプロバイダは #523 で縮退予定）。
 */

import type { AgentModelAlias } from "../api/types";
import { AGENT_MODEL_MESSAGES } from "./messages";

/** プロバイダ識別子（列見出し・グルーピングに使う。backend の provider と一致）。 */
export type AgentModelProvider = "anthropic" | "openai" | "google";

export type AgentModelOption = {
  alias: AgentModelAlias;
  /** 所属プロバイダ（モデル選択 UI の列分け） */
  provider: AgentModelProvider;
  /** 製品名（翻訳しない） */
  name: string;
  tagline: string;
};

/** プロバイダの列見出し表示名（製品名なので翻訳しない）。 */
export const AGENT_PROVIDER_LABELS: Record<AgentModelProvider, string> = {
  anthropic: "Claude",
  openai: "OpenAI",
  google: "Gemini",
};

/** モデル選択 UI の列の並び順（Claude → GPT → Gemini）。 */
export const AGENT_PROVIDER_ORDER: readonly AgentModelProvider[] = [
  "anthropic",
  "openai",
  "google",
];

/**
 * エイリアス → 表示メタデータ。`Record<AgentModelAlias, ...>` で型付けすることで、
 * backend が `AgentModelAlias`（OpenAPI codegen 経由で `generated.ts` に反映）へ
 * 新モデルを追加した瞬間、ここにメタ未定義のままだと**コンパイルエラー**になる。
 * これにより「モデル選択 UI に新モデルが出ない」同期忘れを型で防ぐ（BE 側の
 * model_catalog ↔ AgentModelAlias drift ガードと対になる FE 側ガード）。
 */
const AGENT_MODEL_META: Record<AgentModelAlias, AgentModelOption> = {
  haiku: {
    alias: "haiku",
    provider: "anthropic",
    name: "Haiku 4.5",
    tagline: AGENT_MODEL_MESSAGES.HAIKU_TAGLINE,
  },
  sonnet: {
    alias: "sonnet",
    provider: "anthropic",
    name: "Sonnet 4.6",
    tagline: AGENT_MODEL_MESSAGES.SONNET_TAGLINE,
  },
  "gpt-mini": {
    alias: "gpt-mini",
    provider: "openai",
    name: "GPT-4o mini",
    tagline: AGENT_MODEL_MESSAGES.GPT_MINI_TAGLINE,
  },
  gpt: {
    alias: "gpt",
    provider: "openai",
    name: "GPT-4.1",
    tagline: AGENT_MODEL_MESSAGES.GPT_TAGLINE,
  },
  "gemini-flash": {
    alias: "gemini-flash",
    provider: "google",
    name: "Gemini 2.5 Flash",
    tagline: AGENT_MODEL_MESSAGES.GEMINI_FLASH_TAGLINE,
  },
  "gemini-pro": {
    alias: "gemini-pro",
    provider: "google",
    name: "Gemini 2.5 Pro",
    tagline: AGENT_MODEL_MESSAGES.GEMINI_PRO_TAGLINE,
  },
};

// 表示順は Record の定義順。getModelOptionsByProvider が AGENT_PROVIDER_ORDER で列に振り分ける。
export const AGENT_MODEL_OPTIONS: readonly AgentModelOption[] = Object.values(AGENT_MODEL_META);

/** エイリアスから表示メタデータを引く。未知の値は先頭（haiku）にフォールバック。 */
export function getModelOption(alias: AgentModelAlias): AgentModelOption {
  return AGENT_MODEL_OPTIONS.find((option) => option.alias === alias) ?? AGENT_MODEL_OPTIONS[0];
}

/** プロバイダ列ごとにモデルをまとめる（モデル選択 UI の列表示用）。 */
export function getModelOptionsByProvider(): {
  provider: AgentModelProvider;
  label: string;
  options: AgentModelOption[];
}[] {
  return AGENT_PROVIDER_ORDER.map((provider) => ({
    provider,
    label: AGENT_PROVIDER_LABELS[provider],
    options: AGENT_MODEL_OPTIONS.filter((option) => option.provider === provider),
  }));
}
