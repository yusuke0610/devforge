/// <reference lib="webworker" />
/**
 * 文章校正 Web Worker。textlint kernel + 技術文書プリセット + prh をこの中で組み立て、
 * メインスレッドから渡されたテキスト項目を校正して `ProofreadIssue[]` を返す。
 *
 * ## ブラウザ統合のポイント（ハマりどころ）
 * - kuromoji（形態素解析）の辞書はブラウザに fs が無いため、`public/kuromoji-dict/` を
 *   静的配信し、kuromojin が参照する `globalThis.kuromojin.dicPath` に URL を注入する。
 *   kuromojin は `typeof window !== "undefined"` を前提とするため、worker では `window` も補う。
 * - kuromoji の辞書ロード（数 MB）に失敗しても機能停止させない。辞書を使うルール
 *   （二重助詞・冗長表現など）は preload 成功時のみ登録し、失敗時は prh + 形態素非依存
 *   ルールだけで動作させる（グレースフルデグラデーション）。
 * - prh ルールはファイル読み込み不可なので、YAML を `?raw` 文字列で読み込み `ruleContents` で渡す。
 */
// 最初に import すること（textlint/kuromoji 依存の評価前にグローバルを用意する）。
import "./worker-env-polyfill";

import { TextlintKernel } from "@textlint/kernel";
import type { TextlintKernelPlugin, TextlintKernelRule } from "@textlint/kernel";

import prhRule from "textlint-rule-prh";

import { buildExcerpt, mapSeverity } from "./issueFormat";
import prhYaml from "./prh-it-terms.yml?raw";
import type {
  CareerTextItem,
  ProofreadIssue,
  ProofreadRequest,
  ProofreadResponse,
} from "./types";

/**
 * textlint ルール / プラグインは CJS↔ESM 相互運用で `default` が多重ラップされることがある。
 * 本体（関数 もしくは `{ linter }` / `{ create }` を持つオブジェクト）まで掘り下げる。
 */
function unwrapModule<T = unknown>(mod: unknown): T {
  let current = mod as Record<string, unknown> | unknown;
  for (let i = 0; i < 5; i += 1) {
    if (typeof current === "function") return current as T;
    if (
      current &&
      typeof current === "object" &&
      ("linter" in current || "create" in current || "fixer" in current)
    ) {
      return current as T;
    }
    if (current && typeof current === "object" && "default" in current) {
      current = (current as { default: unknown }).default;
      continue;
    }
    break;
  }
  return current as T;
}

const kernel = new TextlintKernel();

/**
 * 技術文書プリセットのうち kuromoji（形態素解析）に依存するルール ID。
 * 辞書 preload に失敗した場合、これらを除外して機能停止を避ける。
 */
const KUROMOJI_RULE_IDS = new Set<string>([
  "max-ten",
  "no-double-negative-ja",
  "no-doubled-conjunction",
  "no-doubled-conjunctive-particle-ga",
  "no-doubled-joshi",
  "no-dropping-the-ra",
  "ja-no-weak-phrase",
  "ja-no-successive-word",
  "ja-no-abusage",
  "ja-no-redundant-expression",
  // 念のため漢数字ルールも辞書依存側に寄せる（誤検出より安全側）。
  "arabic-kanji-numbers",
]);

/** 技術文書プリセットの import 形（{ rules, rulesConfig }）。 */
type PresetModule = {
  rules: Record<string, unknown>;
  rulesConfig: Record<string, unknown>;
};

/**
 * プリセットから kernel 用のルール記述子を組み立てる。
 * `includeKuromoji=false` のときは形態素解析依存ルールを除外する。
 * prh（表記ゆれ）はプリセット外なので常に末尾へ足す。
 */
function buildRules(preset: PresetModule, includeKuromoji: boolean): TextlintKernelRule[] {
  const rules: TextlintKernelRule[] = [];
  for (const [ruleId, rule] of Object.entries(preset.rules)) {
    if (!includeKuromoji && KUROMOJI_RULE_IDS.has(ruleId)) continue;
    const options = preset.rulesConfig[ruleId];
    rules.push({
      ruleId,
      rule: unwrapModule(rule),
      // rulesConfig の値が false/true（無効/デフォルト）の場合は options を渡さない。
      ...(options && typeof options === "object" ? { options } : {}),
    });
  }
  rules.push({ ruleId: "prh", rule: unwrapModule(prhRule), options: { ruleContents: [prhYaml] } });
  return rules;
}

/** kernel.lintText に渡す構築済み設定。 */
type ProofreadConfig = {
  plugins: TextlintKernelPlugin[];
  rules: TextlintKernelRule[];
};

/** テキストプラグイン（.txt 解析）と全ルールを 1 回だけ構築してキャッシュする。 */
let setupPromise: Promise<ProofreadConfig> | null = null;

async function setup(): Promise<ProofreadConfig> {
  const [textPlugin, presetModule] = await Promise.all([
    import("@textlint/textlint-plugin-text"),
    import("textlint-rule-preset-ja-technical-writing"),
  ]);
  const preset = (("default" in presetModule ? presetModule.default : presetModule) ??
    presetModule) as PresetModule;
  const plugins: TextlintKernelPlugin[] = [
    { pluginId: "text", plugin: unwrapModule(textPlugin) },
  ];

  // 辞書を preload。成功時のみ kuromoji 依存ルールを含める。
  let includeKuromoji = false;
  try {
    const kuromojin = await import("kuromojin");
    await kuromojin.getTokenizer();
    includeKuromoji = true;
  } catch {
    // 辞書ロード失敗時は形態素非依存ルール + prh のみで継続（機能停止させない）。
    includeKuromoji = false;
  }

  return { plugins, rules: buildRules(preset, includeKuromoji) };
}

function ensureSetup() {
  if (!setupPromise) {
    // setup 失敗（依存ロード不能）も握りつぶさず、各リクエストで再試行できるよう null に戻す。
    setupPromise = setup().catch((err) => {
      setupPromise = null;
      throw err;
    });
  }
  return setupPromise;
}

/** 1 テキスト項目を校正し、ProofreadIssue 配列へ整形する。 */
async function proofreadItem(
  item: CareerTextItem,
  config: ProofreadConfig,
): Promise<ProofreadIssue[]> {
  const result = await kernel.lintText(item.value, {
    ext: ".txt",
    plugins: config.plugins,
    rules: config.rules,
  });
  return result.messages.map((message) => ({
    fieldId: item.id,
    fieldLabel: item.label,
    ruleId: message.ruleId,
    message: message.message,
    severity: mapSeverity(message.severity),
    line: message.line,
    column: message.column,
    index: message.index,
    excerpt: buildExcerpt(item.value, message.index),
  }));
}

self.onmessage = async (event: MessageEvent<ProofreadRequest>) => {
  const data = event.data;
  if (!data || data.type !== "proofread") return;
  const { requestId, items } = data;
  try {
    const config = await ensureSetup();
    const nested = await Promise.all(items.map((item) => proofreadItem(item, config)));
    const issues = nested.flat();
    const response: ProofreadResponse = { type: "result", requestId, issues };
    self.postMessage(response);
  } catch (err) {
    const response: ProofreadResponse = {
      type: "error",
      requestId,
      message: err instanceof Error ? err.message : String(err),
    };
    self.postMessage(response);
  }
};
