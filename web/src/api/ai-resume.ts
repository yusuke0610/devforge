import { request } from "./client";
import { downloadBlob } from "./download";
import { PATHS } from "./paths";

export interface SectionItem {
  original: string;
  ai: string;
  adopted: boolean;
}

export interface ProjectSectionItem {
  project_id: number;
  original: string;
  ai: string;
  adopted: boolean;
}

export interface SectionsJson {
  summary: SectionItem;
  skills: SectionItem;
  projects: ProjectSectionItem[];
  self_pr: SectionItem;
}

export interface AiResumeSnapshot {
  id: number;
  version: number;
  target_position: string;
  sections_json: SectionsJson;
  final_json: Record<string, unknown> | null;
  label: string | null;
  created_at: string;
  updated_at: string;
}

export interface AiResumeSnapshotUpdate {
  sections_json: SectionsJson;
  label?: string | null;
}

/** AI 強化版職務経歴書を生成する。 */
export function generateAiResume(targetPosition: string): Promise<AiResumeSnapshot> {
  return request<AiResumeSnapshot>(PATHS.aiResume.generate, {
    method: "POST",
    body: JSON.stringify({ target_position: targetPosition }),
  });
}

/** 全スナップショットを取得する。 */
export function listSnapshots(): Promise<AiResumeSnapshot[]> {
  return request<AiResumeSnapshot[]>(PATHS.aiResume.snapshots);
}

/** 指定 ID のスナップショットを取得する。 */
export function getSnapshot(id: number): Promise<AiResumeSnapshot> {
  return request<AiResumeSnapshot>(PATHS.aiResume.snapshotById(id));
}

/** セクション採用状態を更新する。 */
export function updateSnapshot(id: number, body: AiResumeSnapshotUpdate): Promise<AiResumeSnapshot> {
  return request<AiResumeSnapshot>(PATHS.aiResume.snapshotById(id), {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** バージョンを確定する。 */
export function finalizeSnapshot(id: number): Promise<AiResumeSnapshot> {
  return request<AiResumeSnapshot>(PATHS.aiResume.snapshotFinalize(id), {
    method: "POST",
  });
}

/** スナップショットを削除する。 */
export function deleteSnapshot(id: number): Promise<void> {
  return request<void>(PATHS.aiResume.snapshotById(id), {
    method: "DELETE",
  });
}

/** PDF をダウンロードする。 */
export function downloadPdf(id: number): Promise<void> {
  return downloadBlob(PATHS.aiResume.snapshotPdf(id), `ai_resume_${id}.pdf`);
}

/** Markdown をダウンロードする。 */
export function downloadMarkdown(id: number): Promise<void> {
  return downloadBlob(PATHS.aiResume.snapshotMarkdown(id), `ai_resume_${id}.md`);
}
