import { request } from "./client";
import { downloadBlob, getBlobUrl } from "./download";
import { PATHS } from "./paths";
import type { ResumeCreate, ResumeResponse } from "./types";

/**
 * 保存前プレビュー（左右 diff 表示）のレスポンス。
 * backend `schemas/resume.py:ResumePreviewResponse` のミラー（OpenAPI 生成物には未反映のため手書き）。
 */
export type ResumePreviewResponse = {
  /** PDF と同じレイアウトに整形した HTML（各値ノードに data-fp 付き） */
  html: string;
  /** 画面表示用 CSS（PDF 専用フォント定義を除いたもの） */
  css: string;
};

export function getLatestCareerResume(): Promise<ResumeResponse> {
  return request<ResumeResponse>(PATHS.resumes.latest);
}

export function createCareerResume(payload: ResumeCreate): Promise<ResumeResponse> {
  return request<ResumeResponse>(PATHS.resumes.base, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCareerResume(
  id: string,
  payload: ResumeCreate,
): Promise<ResumeResponse> {
  return request<ResumeResponse>(PATHS.resumes.byId(id), {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteCareerResume(): Promise<{ message: string }> {
  return request<{ message: string }>(PATHS.resumes.base, { method: "DELETE" });
}

export function downloadCareerResumePdf(id: string): Promise<void> {
  return downloadBlob(PATHS.resumes.pdf(id), `career-resume-${id}.pdf`);
}

export function downloadCareerResumeMarkdown(id: string): Promise<void> {
  return downloadBlob(PATHS.resumes.markdown(id), `career-resume-${id}.md`);
}

export function getCareerResumePdfBlobUrl(id: string): Promise<string> {
  return getBlobUrl(PATHS.resumes.pdf(id));
}

/**
 * 保存せずに、職務経歴書を整形した HTML（data-fp 付き）と画面用 CSS を取得する。
 * 左右 diff プレビュー（左=保存済み / 右=編集中）の描画に使う。
 */
export function getCareerResumePreview(
  payload: ResumeCreate,
): Promise<ResumePreviewResponse> {
  return request<ResumePreviewResponse>(PATHS.resumes.preview, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
