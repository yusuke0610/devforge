/**
 * 校正 worker のメインスレッド側サービス。
 *
 * - worker は初回呼び出し時にのみ遅延生成する（textlint / kuromoji 一式は worker チャンクへ
 *   分離され、初期バンドル・初回描画には載らない）。
 * - 各リクエストに連番 `requestId` を振り、応答を id で突合してレースを防ぐ。
 * - 収集テキストが 0 件なら worker を起動せず空配列を返す。
 */
import type { CareerFormState } from "../payloadBuilders";
import { collectCareerTexts } from "./collectCareerTexts";
import type { ProofreadIssue, ProofreadRequest, ProofreadResponse } from "./types";

let worker: Worker | null = null;
let nextRequestId = 1;

/** worker を遅延生成する（テストでは本モジュールごとモックするため、ここは実行されない）。 */
function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(new URL("./proofread.worker.ts", import.meta.url), { type: "module" });
  }
  return worker;
}

/**
 * 編集中フォームの全テキスト項目を校正する。
 * 収集 0 件なら即 `[]`。それ以外は worker へ投げ、当該 requestId の応答を待つ。
 */
export function proofreadCareerForm(form: CareerFormState): Promise<ProofreadIssue[]> {
  const items = collectCareerTexts(form);
  if (items.length === 0) return Promise.resolve([]);

  const activeWorker = getWorker();
  const requestId = nextRequestId;
  nextRequestId += 1;

  return new Promise<ProofreadIssue[]>((resolve, reject) => {
    const cleanup = () => {
      activeWorker.removeEventListener("message", onMessage);
      activeWorker.removeEventListener("error", onError);
    };
    const onMessage = (event: MessageEvent<ProofreadResponse>) => {
      const data = event.data;
      if (!data || data.requestId !== requestId) return;
      cleanup();
      if (data.type === "result") resolve(data.issues);
      else reject(new Error(data.message));
    };
    const onError = (event: ErrorEvent) => {
      cleanup();
      reject(event.error instanceof Error ? event.error : new Error(event.message));
    };
    activeWorker.addEventListener("message", onMessage);
    activeWorker.addEventListener("error", onError);

    const request: ProofreadRequest = { type: "proofread", requestId, items };
    activeWorker.postMessage(request);
  });
}
