/**
 * 校正 worker 用の最小グローバル補完。worker の **最初** に import して副作用を効かせる
 * （textlint / kuromoji 系の依存が評価・実行時に参照する node/ブラウザのグローバルを先に用意する）。
 *
 * - `process`: async / textlint 依存が `process.env` / `process.nextTick` を参照する。worker には無い。
 * - `window`: kuromojin は辞書パス解決で `typeof window !== "undefined"` を前提とする。worker には無い。
 * - `window.kuromojin.dicPath`: 静的配信した辞書（public/kuromoji-dict/）の URL を注入する。
 */
type MinimalProcess = {
  env: Record<string, string | undefined>;
  nextTick: (cb: (...args: unknown[]) => void, ...args: unknown[]) => void;
  cwd: () => string;
  platform: string;
  version: string;
  argv: string[];
};

const g = globalThis as unknown as {
  process?: Partial<MinimalProcess>;
  window?: unknown;
  kuromojin?: { dicPath: string };
};

if (typeof g.process === "undefined") {
  g.process = {};
}
// 一部の textlint 依存（prh 経由の ja-no-abusage 等）が参照する API を最小実装で補う。
const proc = g.process as Partial<MinimalProcess>;
proc.env ??= {};
proc.nextTick ??= (cb, ...args) => {
  void Promise.resolve().then(() => cb(...args));
};
proc.cwd ??= () => "/";
proc.platform ??= "browser";
proc.version ??= "";
proc.argv ??= [];

if (typeof g.window === "undefined") {
  g.window = globalThis;
}

// 辞書の静的配信パスを kuromojin に渡す。
// 注意: ルート相対パスにする（`http://…` のような絶対 URL を渡すと、kuromoji 内部の
// path.join（ブラウザでは path-browserify）が `://` を `:/` に潰して壊れる）。
// XHR はこのルート相対パスを worker の origin 基準で解決する。
g.kuromojin = { dicPath: "/kuromoji-dict" };
