import { describe, expect, it } from "vitest";

import {
  AGENT_MODEL_OPTIONS,
  getModelOption,
  getModelOptionsByProvider,
} from "./agentModels";

/**
 * agentModels の SSoT 整合テスト。
 *
 * モデルエイリアス集合の正本は backend `AgentModelAlias`（OpenAPI codegen 経由で
 * `generated.ts` に反映）。`AGENT_MODEL_META` を `Record<AgentModelAlias, ...>` で
 * 型付けしているため網羅性はコンパイル時に保証されるが、本テストは「プロバイダ列分け
 * の漏れ」「未知エイリアスのフォールバック」といった runtime 不変条件を固定する。
 */
describe("agentModels", () => {
  it("全 option の alias は一意", () => {
    const aliases = AGENT_MODEL_OPTIONS.map((o) => o.alias);
    expect(new Set(aliases).size).toBe(aliases.length);
  });

  it("getModelOption は既知 alias の表示メタを返す", () => {
    expect(getModelOption("sonnet").name).toBe("Sonnet 4.6");
    expect(getModelOption("gemini-pro").provider).toBe("google");
  });

  it("getModelOption は未知 alias を先頭（haiku）にフォールバックする", () => {
    // @ts-expect-error 型に無い値を渡して runtime フォールバックを検証する
    expect(getModelOption("unknown-model").alias).toBe("haiku");
  });

  it("getModelOptionsByProvider は全 option を漏れなくいずれかの列に含む", () => {
    // 新プロバイダのモデルが AGENT_PROVIDER_ORDER 漏れで列から落ちる drift を検知する
    const grouped = getModelOptionsByProvider()
      .flatMap((g) => g.options)
      .map((o) => o.alias)
      .sort();
    const all = AGENT_MODEL_OPTIONS.map((o) => o.alias).sort();
    expect(grouped).toEqual(all);
  });
});
